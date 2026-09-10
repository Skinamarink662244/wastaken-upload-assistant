# Upload Assistant © 2025 Audionut & wastaken7 — Licensed under UAPL v1.0
import re
from typing import Any, cast

import httpx
import pycountry

from src.console import logger
from src.languages import languages_manager
from src.meta import Meta
from src.tmdb import get_tmdb_localized_data
from src.trackers.common import Common
from src.trackers.UNIT3D import UNIT3D

Config = dict[str, Any]


class InfinityHD(UNIT3D):
    """
    INFINITYHD is a Private Torrent Tracker for MOVIES / TV / ANIME
    """

    tracker = "INFINITYHD"
    display_name = "InfinityHD"
    allows_bloated_audio = True
    base_url = "https://infinityhd.net"
    banned_groups = (
        "1000",
        "24xHD",
        "41RGB",
        "4K4U",
        "AG",
        "AOC",
        "AROMA",
        "aXXo",
        "AZAZE",
        "BARC0DE",
        "BAUCKLEY",
        "BdC",
        "beAst",
        "BONE",
        "BRiNK",
        "BRrip",
        "BTM",
        "C1NEM4",
        "C4K",
        "CDDHD",
        "CHAOS",
        "CHD",
        "CHX",
        "CiNE",
        "COLLECTiVE",
        "CREATiVE24",
        "CrEwSaDe",
        "CTFOH",
        "d3g",
        "DDR",
        "DepraveD",
        "DNL",
        "DRX",
        "EDITH",
        "EPiC",
        "EuReKA",
        "EVO",
        "FaNGDiNG0",
        "Feranki1980",
        "FGT",
        "FiSTER",
        "FMD",
        "FRDS",
        "FZHD",
        "GalaxyRG",
        "GalaxyTV",
        "GHD",
        "GHOSTS",
        "GPTHD",
        "GRACE",
        "HDHUB4U",
        "HDS",
        "HDT",
        "HDTime",
        "HDWinG",
        "HiQVE",
        "iHYTECH",
        "in",
        "iNTENSO",
        "iPlanet",
        "ION10",
        "iVy",
        "jennaortegaUHD",
        "JFF",
        "KC",
        "KiNGDOM",
        "KIRA",
        "L0SERNIGHT",
        "LAMA",
        "Leffe",
        "Liber8",
        "LiGaS",
        "LT",
        "LUCY",
        "MarkII",
        "MeGusta",
        "Mesc",
        "mHD",
        "MTeam",
        "mSD",
        "MT",
        "MySiLU",
        "NaNi",
        "NhaNc3",
        "nHD",
        "nikt0",
        "nSD",
        "OFT",
        "Paheph",
        "PATOMiEL",
        "POKE",
        "PRODJi",
        "PSA",
        "PTNK",
        "RARBG",
        "RDN",
        "Rifftrax",
        "RU4HD",
        "SANTi",
        "SasukeducK",
        "Scene",
        "SHD",
        "ShieldBearer",
        "SM737",
        "STUTTERSHIT",
        "SUNSCREEN",
        "TBS",
        "TEKNO3D",
        "TG",
        "TGx",
        "Tigole",
        "TIKO",
        "TORRENTGALAXY",
        "UNiON",
        "VIDEOHOLE",
        "VISIONPLUSHDR-X",
        "VXT",
        "WAF",
        "WiKi",
        "WKS",
        "worldmkv",
        "x0r",
        "XLF",
        "YIFY",
        "YTSMX",
        "Zero00",
        "Zeus",
    )
    id_url = f"{base_url}/api/torrents/"
    upload_url = f"{base_url}/api/torrents/upload"
    search_url = f"{base_url}/api/torrents/filter"
    requests_url = f"{base_url}/api/requests/filter"
    torrent_url = f"{base_url}/torrents/"
    supported_categories = ("TV", "MOVIE")
    tracker_urls = ("https://infinityhd.net",)

    def __init__(self, config: Config) -> None:
        super().__init__(config, tracker_name="INFINITYHD")
        self.config: Config = config
        self.common = Common(config)

    async def get_category_id(self, meta: Meta, category: str | None = None, reverse: bool = False, mapping_only: bool = False) -> dict[str, str]:
        category_name = meta.category
        anime = meta.anime
        category_id = {
            "MOVIE": "1",
            "TV": "2",
            "ANIME": "3",
            "ANIME MOVIE": "4",
        }

        is_anime_movie = False
        is_anime = False

        if category_name == "MOVIE" and anime is True:
            is_anime_movie = True

        if category_name == "TV" and anime is True:
            is_anime = True

        if is_anime:
            return {"category_id": "3"}
        if is_anime_movie:
            return {"category_id": "4"}

        if mapping_only:
            return category_id
        if reverse:
            return {v: k for k, v in category_id.items()}
        if category is not None:
            return {"category_id": category_id.get(category, "0")}
        meta_category = meta.category
        resolved_id = category_id.get(meta_category, "0")
        return {"category_id": resolved_id}

    async def get_resolution_id(self, meta: Meta, resolution: str | None = None, reverse: bool = False, mapping_only: bool = False) -> dict[str, str]:
        resolution_id = {"4320p": "1", "2160p": "2", "1440p": "3", "1080p": "3", "1080i": "4"}
        if mapping_only:
            return resolution_id
        if reverse:
            return {v: k for k, v in resolution_id.items()}
        if resolution is not None:
            return {"resolution_id": resolution_id.get(resolution, "10")}
        meta_resolution = meta.resolution
        resolved_id = resolution_id.get(meta_resolution, "10")
        return {"resolution_id": resolved_id}

    def _get_language_code(self, track_or_string: Any) -> str:
        """Extract and normalize language to ISO alpha-2 code"""
        if isinstance(track_or_string, dict):
            track_map = cast(dict[str, Any], track_or_string)
            lang_value = track_map.get("Language", "")
            if isinstance(lang_value, dict):
                lang_map = cast(dict[str, Any], lang_value)
                lang = str(lang_map.get("String", ""))
            else:
                lang = str(lang_value)
        else:
            lang = str(track_or_string)
        if not lang:
            return ""
        lang_str = lang.lower()

        # Strip country code if present (e.g., "en-US" → "en")
        if "-" in lang_str:
            lang_str = lang_str.split("-")[0]

        if len(lang_str) == 2:
            return lang_str
        try:
            lang_obj = pycountry.languages.get(name=lang_str.title()) or pycountry.languages.get(alpha_2=lang_str) or pycountry.languages.get(alpha_3=lang_str)
            return lang_obj.alpha_2.lower() if lang_obj else lang_str
        except (AttributeError, KeyError, LookupError):
            return lang_str

    def original_language_check(self, meta: Meta) -> bool:
        if "mediainfo" not in meta:
            return False

        original_languages = {lang.lower() for lang in (meta.original_language or []) if isinstance(lang, str) and lang.strip()}
        if not original_languages:
            return False

        tracks_value = meta.mediainfo.get("media", {}).get("track", [])
        tracks_list = cast(list[Any], tracks_value) if isinstance(tracks_value, list) else []
        for track in tracks_list:
            if not isinstance(track, dict):
                continue
            track_map = cast(dict[str, Any], track)
            if track_map.get("@type") != "Audio":
                continue
            if "commentary" in str(track_map.get("Title", "")).lower():
                continue
            lang_code = self._get_language_code(track_map)
            if lang_code and lang_code.lower() in original_languages:
                return True
        return False

    async def get_name(self, meta: Meta) -> dict[str, str]:
        ihd_name = meta.name
        resolution = meta.resolution

        if meta.category == "TV":
            ihd_name = await self._tv_name(meta, ihd_name)

        if not meta.language_checked:
            await languages_manager.process_desc_language(meta, tracker=self.tracker)
        audio_languages_value = meta.audio_languages
        audio_languages: list[str] = []
        if isinstance(audio_languages_value, list):
            audio_languages_list = audio_languages_value
            audio_languages = [str(item) for item in audio_languages_list]
        if audio_languages and not await languages_manager.has_english_language(audio_languages):
            foreign_lang = audio_languages[0].upper()
            ihd_name = ihd_name.replace(resolution, f"{foreign_lang} {resolution}", 1)

        return {"name": ihd_name}

    async def _tv_name(self, meta: Meta, name: str) -> str:
        tmdb_title = await self._tmdb_en_title(meta)
        marker = f"{meta.season or ''}{meta.episode or ''}".strip()
        if not marker or marker not in name:
            return " ".join(name.split())

        # Rebuild the head as title -> AKA -> year, leaving the marker and everything after it intact.
        aka = "" if meta.no_aka else self._localized_aka(meta, tmdb_title)
        year = str(meta.year or "").strip() if (not meta.no_year and await self._tv_title_needs_year(meta, tmdb_title)) else ""
        tail = name.partition(marker)[2]
        lead = " ".join(part for part in (tmdb_title, aka, year) if part)
        return " ".join(f"{lead} {marker}{tail}".split())

    async def _tmdb_en_title(self, meta: Meta) -> str:
        """Canonical TMDB (en-US) title.

        The core replaces meta.title with the TVDB series name for non-English-origin TV;
        this site wants the TMDB title, matching what its metadata panel displays.
        """
        try:
            tmdb_main = await get_tmdb_localized_data(meta, data_type="main", language="en-US", append_to_response="")
        except Exception:  # noqa: BLE001 - a naming lookup must never abort the upload
            tmdb_main = {}
        data = tmdb_main if isinstance(tmdb_main, dict) else {}
        title = str(data.get("name") or data.get("title") or "").strip()
        return title or str(meta.title or "").strip()

    @staticmethod
    def _localized_aka(meta: Meta, tmdb_title: str) -> str:
        """AKA sourced from IMDb.

        English-origin shows use IMDb's display title (when it differs from the TMDB title);
        every other origin uses IMDb's romanized original title (its ``aka``), never TMDB's
        native-language alternate. Suppressed when it just echoes the title.
        """
        imdb_info = meta.imdb_info if isinstance(meta.imdb_info, dict) else {}
        original_language = str(meta.original_language or "").strip().lower()
        original_language = original_language.split("-")[0].split("(")[0].strip()
        is_english = original_language in ("en", "eng", "english")
        aka_source = imdb_info.get("title") if is_english else imdb_info.get("aka")
        aka = str(aka_source or "").strip()
        if not aka:
            return ""
        if aka.lower() == tmdb_title.lower() or aka.lower() in tmdb_title.lower():
            return ""
        return f"AKA {aka}"

    async def _tv_title_needs_year(self, meta: Meta, title: str | None = None) -> bool:
        title = str(title if title is not None else (meta.title or "")).strip()
        api_key = str(self.config.get("DEFAULT", {}).get("tmdb_api", "")).strip()
        if not title or not api_key:
            return False
        try:
            logger.info(f"{self.tracker}: Checking if TMDb has multiple shows with the title '{title}'...")
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    "https://api.themoviedb.org/3/search/tv",
                    params={"api_key": api_key, "query": title, "language": "en-US", "include_adult": "true"},
                )
                response.raise_for_status()
                payload_raw: Any = response.json()
        except (httpx.HTTPError, ValueError, TypeError):
            return False

        title_key = " ".join(title.casefold().split())
        current_id = str(meta.tmdb_id or "")
        payload = cast(dict[str, Any], payload_raw) if isinstance(payload_raw, dict) else {}
        results_raw: Any = payload.get("results", [])
        results = cast(list[Any], results_raw) if isinstance(results_raw, list) else []
        matching_ids: set[str] = set()
        for result_raw in results:
            if not isinstance(result_raw, dict):
                continue
            result = cast(dict[str, Any], result_raw)
            names = (result.get("name"), result.get("original_name"))
            if any(" ".join(str(candidate or "").casefold().split()) == title_key for candidate in names):
                matching_ids.add(str(result.get("id", "")))
        matching_ids.discard("")
        return bool(matching_ids - {current_id}) if current_id else len(matching_ids) > 1

    async def get_additional_checks(self, meta: Meta) -> bool:
        if meta.resolution not in ["4320p", "2160p", "1440p", "1080p", "1080i"]:
            if not meta.unattended or meta.debug:
                logger.info(f"{self.tracker}: [bold red]Uploads must be at least 1080 resolution for {self.tracker}.[/bold red]")
            return False

        if not meta.valid_mi_settings:
            if not meta.unattended or meta.debug:
                logger.info(f"{self.tracker}: [bold red]No encoding settings in mediainfo, skipping {self.tracker} upload.[/bold red]")
            return False

        if meta.is_disc != "BDMV":
            if not meta.language_checked:
                await languages_manager.process_desc_language(meta, tracker=self.tracker)
            original_language = self.original_language_check(meta)
            audio_languages_value = meta.audio_languages
            subtitle_languages_value = meta.subtitle_languages
            audio_languages: list[str] = []
            subtitle_languages: list[str] = []
            if isinstance(audio_languages_value, list):
                audio_languages_list = audio_languages_value
                audio_languages = [str(item) for item in audio_languages_list]
            else:
                audio_languages = []
            if isinstance(subtitle_languages_value, list):
                subtitle_languages_list = subtitle_languages_value
                subtitle_languages = [str(item) for item in subtitle_languages_list]
            else:
                subtitle_languages = []
            has_eng_audio = await languages_manager.has_english_language(audio_languages if audio_languages else "")
            has_eng_subs = await languages_manager.has_english_language(subtitle_languages if subtitle_languages else "")
            # Require at least one English audio/subtitle track or an original language audio track
            if not (original_language or has_eng_audio or has_eng_subs):
                if not meta.unattended or meta.debug:
                    logger.info(f"{self.tracker}: [bold red]requires at least one English audio or subtitle track or an original language audio track.")
                return False

        return self.common.check_and_confirm_adult_media_upload(meta, self.tracker)
