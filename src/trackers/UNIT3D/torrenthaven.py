# Upload Assistant © 2025 Audionut & wastaken7 — Licensed under UAPL v1.0
from typing import Any

from src.meta import Meta
from src.trackers.common import Common
from src.trackers.UNIT3D import UNIT3D

Config = dict[str, Any]


class TorrentHaven(UNIT3D):
    """
    TorrentHaven (THN) — UNIT3D private tracker.
    """

    tracker = "TORRENTHAVEN"
    display_name = "TorrentHaven"
    base_url = "https://torrenthaven.org"
    banned_groups = ()
    id_url = f"{base_url}/api/torrents/"
    upload_url = f"{base_url}/api/torrents/upload"
    requests_url = f"{base_url}/api/requests/filter"
    search_url = f"{base_url}/api/torrents/filter"
    torrent_url = f"{base_url}/torrents/"
    supported_categories = ("MOVIE", "TV")

    def __init__(self, config: Config) -> None:
        super().__init__(config, tracker_name="TORRENTHAVEN")
        self.config = config
        self.common = Common(config)

    # Categories (Movies=1, TV EP=2) and resolutions (1-9, Other=10) match the
    # UNIT3D defaults, so those overrides are intentionally omitted.
    # Only the TYPE ids differ on TorrentHaven: DVDRIP is 19 (default is 3).
    async def get_type_id(
        self,
        meta: Meta,
        type: str | None = None,
        reverse: bool = False,
        mapping_only: bool = False,
    ) -> dict[str, str]:
        type_id = {
            "DISC": "1",
            "REMUX": "2",
            "ENCODE": "3",
            "WEBDL": "4",
            "WEBRIP": "5",
            "HDTV": "6",
            "DVDRIP": "19",
        }
        if mapping_only:
            return type_id
        if reverse:
            return {
                "1": "DISC",
                "2": "REMUX",
                "3": "ENCODE",
                "4": "WEBDL",
                "5": "WEBRIP",
                "6": "HDTV",
                "19": "DVDRIP",
            }
        type_value = type if type is not None and type != "" else meta.type or ""
        return {"type_id": type_id.get(type_value, "0")}
