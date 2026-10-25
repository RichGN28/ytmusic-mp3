from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .models import Playlist, Track


@dataclass(frozen=True)
class PlaylistTracks:
    playlist: Playlist
    tracks: list[Track]
    unavailable: int = 0


class YouTubeMusicLibrary:
    """Operaciones de solo lectura sobre la biblioteca del usuario."""

    def __init__(self, client: Any):
        self.client = client

    def playlists(self, limit: int | None = None) -> list[Playlist]:
        result = self.client.get_library_playlists(limit=limit)
        return [playlist for raw in result if (playlist := Playlist.from_api(raw))]

    def liked(self, limit: int | None = None) -> PlaylistTracks:
        result = self.client.get_liked_songs(limit=limit)
        tracks, unavailable = self._parse_tracks(result.get("tracks", []))
        return PlaylistTracks(Playlist("LM", "Me gusta", result.get("trackCount")), tracks, unavailable)

    def playlist(self, playlist_id: str, limit: int | None = None) -> PlaylistTracks:
        result = self.client.get_playlist(playlist_id, limit=limit)
        tracks, unavailable = self._parse_tracks(result.get("tracks", []))
        info = Playlist(playlist_id, result.get("title") or playlist_id, result.get("trackCount"))
        return PlaylistTracks(info, tracks, unavailable)

    @staticmethod
    def _parse_tracks(items: list[dict[str, Any]]) -> tuple[list[Track], int]:
        tracks = []
        unavailable = 0
        for position, raw in enumerate(items, start=1):
            track = Track.from_api(raw, position)
            if track is None:
                unavailable += 1
            else:
                tracks.append(track)
        return tracks, unavailable
