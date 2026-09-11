# Upload Assistant (fork) — cross-tracker .torrent search
#
# Before falling back to mkbrr/torf hashing, search the trackers you are on
# (every tracker with an api_key configured, or an explicit allow-list) that
# support a native release search (UNIT3D `search_existing`) for the release
# being uploaded. Any candidate that exposes a downloadable .torrent is
# fetched and validated against the local files with the SAME gate used for
# client reuse (`Clients.is_valid_torrent` — relative file layout, sizes and
# piece-size sanity). The first candidate that validates is written into the
# release tmp dir and its path returned, so the caller can build BASE.torrent
# from it (`create_base_from_existing_torrent`) and skip hashing entirely.
#
# If nothing validates, None is returned and the caller proceeds to mkbrr.
#
# The candidate sources are pluggable: `_iter_tracker_candidates` yields matches
# from UNIT3D-style trackers today; an alternative backend (e.g. a Prowlarr
# `/api/v1/search` source) can be added as another async generator without
# touching the caller.
from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

import httpx
from torf import Torrent

from src.console import logger

if TYPE_CHECKING:
    from src.clients import Clients
    from src.meta import Meta

# Config keys (all under [DEFAULT]) — read defensively so the feature works even
# if the user's config predates it:
#   search_trackers_for_torrent : bool  (default True)  master on/off switch
#   search_torrent_trackers     : list  (default [])    explicit allow-list of
#                                                        tracker names to search;
#                                                        empty = every tracker you
#                                                        have an api_key configured
#                                                        for (the ones you're on)
#   search_torrent_size_tolerance : float (default 0.0) fraction the reported
#                                                        tracker size may differ
#                                                        from the local total
#                                                        before a candidate is
#                                                        downloaded (0 = exact)
_DEFAULT_TIMEOUT = 20.0
_MAX_CANDIDATE_BYTES = 5 * 1024 * 1024  # never write a >5 MiB "torrent" to disk


def _default_cfg(config: dict[str, Any]) -> dict[str, Any]:
    default = config.get("DEFAULT", {})
    return cast(dict[str, Any], default) if isinstance(default, dict) else {}


def feature_enabled(config: dict[str, Any]) -> bool:
    return bool(_default_cfg(config).get("search_trackers_for_torrent", True))


def _selected_tracker_names(meta: Meta, config: dict[str, Any]) -> list[str]:
    """Every tracker to search, de-duplicated and upper-cased.

    Defaults to the trackers you are actually ON — every tracker whose config
    stanza has a non-empty ``api_key`` — regardless of whether this particular
    upload targets them, so a release already on any of your own trackers can be
    reused. `search_torrent_trackers` is an explicit allow-list that overrides
    the default when you want a specific set.

    It deliberately does NOT fan out to every tracker UA ships support for —
    doing so fires search_existing (and its cookie/login flows) on sites you
    have no account on, which is slow and noisy for zero benefit. The native
    search is API-key based anyway, so a tracker without an api_key cannot be
    searched regardless.
    """
    default = _default_cfg(config)
    explicit = default.get("search_torrent_trackers") or []
    if isinstance(explicit, str):
        explicit = [part.strip() for part in explicit.split(",")]
    names: list[str] = [str(name).strip().upper() for name in explicit if str(name).strip()]

    if not names:
        trackers_cfg = config.get("TRACKERS", {})
        skip_keys = {"DEFAULT_TRACKERS", "DEFAULT", "MANUAL", "USENET"}
        if isinstance(trackers_cfg, dict):
            for tracker_name, tracker_conf in trackers_cfg.items():
                upper = str(tracker_name).strip().upper()
                if upper in skip_keys or not isinstance(tracker_conf, dict):
                    continue
                api_key = tracker_conf.get("api_key")
                if isinstance(api_key, str) and api_key.strip():
                    names.append(upper)

    # Preserve order, drop duplicates.
    seen: set[str] = set()
    ordered: list[str] = []
    for name in names:
        if name not in seen:
            seen.add(name)
            ordered.append(name)
    return ordered


def _local_total_size(meta: Meta) -> int:
    total = 0
    for path in cast("list[str]", meta.filelist or []):
        try:
            total += os.path.getsize(path)
        except OSError:
            return 0
    return total


def _size_is_plausible(candidate_size: Any, local_size: int, tolerance: float) -> bool:
    """Cheap pre-filter before downloading — the real check is is_valid_torrent."""
    if not local_size:
        return True  # unknown local size; let the layout check decide
    try:
        size = int(candidate_size)
    except (TypeError, ValueError):
        return True  # tracker did not report a usable size; don't exclude it
    if size <= 0:
        return True
    if tolerance <= 0:
        # Allow small container/metadata differences even in "exact" mode.
        tolerance = 0.02
    return abs(size - local_size) <= local_size * tolerance


def _instantiate_tracker(name: str, config: dict[str, Any]) -> Any | None:
    from src.trackersetup import tracker_class_map

    try:
        factory = tracker_class_map[name]
    except Exception:
        logger.debug(f"[torrentsearch] {name} not registered in tracker_class_map; skipping")
        return None
    if factory is None:
        return None
    try:
        return factory(config=config)
    except Exception as error:
        logger.debug(f"[torrentsearch] Could not instantiate {name}: {error}")
        return None


async def _search_one_tracker(name: str, meta: Meta, config: dict[str, Any]) -> list[dict[str, Any]]:
    """Return this tracker's search results that carry a download link."""
    instance = _instantiate_tracker(name, config)
    if instance is None:
        return []
    search = getattr(instance, "search_existing", None)
    if search is None or not callable(search):
        logger.debug(f"[torrentsearch] {name} has no search_existing; skipping")
        return []
    try:
        raw = await search(meta)
    except asyncio.CancelledError:
        raise
    except Exception as error:
        logger.debug(f"[torrentsearch] {name} search failed: {error}")
        return []
    results: list[dict[str, Any]] = []
    for item in raw or []:
        if isinstance(item, dict) and item.get("download"):
            entry = dict(item)
            entry.setdefault("_tracker", name)
            results.append(entry)
    if results:
        logger.debug(f"[torrentsearch] {name}: {len(results)} candidate(s) with a downloadable .torrent")
    return results


async def _download_candidate(client_http: httpx.AsyncClient, url: str, dest: Path) -> bool:
    try:
        response = await client_http.get(url)
        response.raise_for_status()
    except asyncio.CancelledError:
        raise
    except Exception as error:
        logger.debug(f"[torrentsearch] download failed ({url.split('?')[0]}): {error}")
        return False
    content = response.content
    if not content or len(content) > _MAX_CANDIDATE_BYTES or not content.lstrip().startswith(b"d"):
        logger.debug("[torrentsearch] download did not look like a .torrent; discarding")
        return False
    try:
        dest.write_bytes(content)
    except OSError as error:
        logger.debug(f"[torrentsearch] could not write candidate: {error}")
        return False
    return True


async def find_torrent_on_trackers(meta: Meta, config: dict[str, Any], client: Clients) -> str | None:
    """Search configured trackers for the release; return a reusable .torrent path.

    Returns the path to a downloaded, validated .torrent that matches the local
    files, or None when nothing usable is found (caller then falls back to
    mkbrr). Never raises for expected network/tracker failures.
    """
    if not feature_enabled(config):
        return None

    filelist = cast("list[str]", meta.filelist or [])
    if not filelist or meta.path is None:
        logger.debug("[torrentsearch] no local filelist yet; leaving torrent creation to mkbrr")
        return None

    tracker_names = _selected_tracker_names(meta, config)
    if not tracker_names:
        return None

    default = _default_cfg(config)
    try:
        tolerance = float(default.get("search_torrent_size_tolerance", 0.0) or 0.0)
    except (TypeError, ValueError):
        tolerance = 0.0
    local_size = _local_total_size(meta)
    local_count = len(filelist) + len(cast("list[str]", meta.subtitle_files or []))

    search_dir = Path(meta.base_dir) / "tmp" / meta.uuid / "tracker_search"
    search_dir.mkdir(parents=True, exist_ok=True)

    logger.info(f"[cyan]Searching {len(tracker_names)} tracker(s) for an existing .torrent before hashing: {', '.join(tracker_names)}[/cyan]")

    async with httpx.AsyncClient(timeout=_DEFAULT_TIMEOUT, follow_redirects=True) as http_client:
        for name in tracker_names:
            candidates = await _search_one_tracker(name, meta, config)
            if not candidates:
                continue

            # Prefer candidates whose reported file_count and size line up with
            # the local content, so the most likely match is tried first and
            # obvious mismatches are skipped without a download.
            def _rank(entry: dict[str, Any]) -> tuple[int, int]:
                file_count = entry.get("file_count") or 0
                count_penalty = 0 if (local_count and file_count == local_count) else 1
                try:
                    size_gap = abs(int(entry.get("size") or 0) - local_size)
                except (TypeError, ValueError):
                    size_gap = local_size or 0
                return (count_penalty, size_gap)

            for index, entry in enumerate(sorted(candidates, key=_rank)):
                if not _size_is_plausible(entry.get("size"), local_size, tolerance):
                    logger.debug(f"[torrentsearch] {name}: skipping '{entry.get('name')}' on size mismatch")
                    continue

                torrent_id = entry.get("id") or index
                dest = search_dir / f"{name}_{torrent_id}.torrent"
                if not await _download_candidate(http_client, str(entry.get("download")), dest):
                    continue

                try:
                    infohash = Torrent.read(str(dest)).infohash
                except Exception as error:
                    logger.debug(f"[torrentsearch] unreadable candidate from {name}: {error}")
                    dest.unlink(missing_ok=True)
                    continue

                # Reuse UA's own reuse gate. torrent_client="" avoids the qbit/
                # rtorrent hash-case path rewriting; the check itself compares
                # relative file layout, sizes and piece-size sanity.
                try:
                    valid, resolved = await client.is_valid_torrent(meta, str(dest), infohash, "", {})
                except asyncio.CancelledError:
                    raise
                except Exception as error:
                    logger.debug(f"[torrentsearch] validation error for {name} candidate: {error}")
                    dest.unlink(missing_ok=True)
                    continue

                if valid:
                    logger.info(f"[bold green]Found a reusable .torrent on {name} — skipping mkbrr hashing (infohash {infohash}).[/bold green]")
                    return str(resolved)

                logger.debug(f"[torrentsearch] {name} candidate '{entry.get('name')}' did not match local files")
                dest.unlink(missing_ok=True)

    logger.info("[yellow]No matching .torrent found on any tracker; creating it with mkbrr.[/yellow]")
    return None
