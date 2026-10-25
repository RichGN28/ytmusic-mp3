from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

_INVALID_FILENAME = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_WINDOWS_RESERVED = {
    "CON", "PRN", "AUX", "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}


def safe_filename(value: str, max_length: int = 150) -> str:
    """Convierte un título en un nombre portable sin perder Unicode legible."""
    value = unicodedata.normalize("NFKC", value)
    value = _INVALID_FILENAME.sub("_", value)
    value = re.sub(r"_+", "_", value)
    value = re.sub(r"\s+", " ", value).strip(" .")
    if not value:
        value = "sin_titulo"
    if value.upper() in _WINDOWS_RESERVED:
        value = f"_{value}"
    return value[:max_length].rstrip(" .") or "sin_titulo"


def playlist_id(value: str) -> str:
    """Acepta un ID o una URL de YouTube/YouTube Music y devuelve el ID."""
    value = value.strip()
    if "://" not in value:
        return value
    query = parse_qs(urlparse(value).query)
    playlist = query.get("list", [""])[0]
    if not playlist:
        raise ValueError("La URL no contiene un parámetro 'list' de playlist.")
    return playlist


@dataclass(frozen=True)
class Track:
    video_id: str
    title: str
    artists: tuple[str, ...] = ()
    album: str | None = None
    duration: str | None = None
    position: int = 0

    @classmethod
    def from_api(cls, raw: dict[str, Any], position: int = 0) -> Track | None:
        video_id = raw.get("videoId")
        if not video_id:
            return None

        artists = tuple(
            str(artist.get("name", "")).strip() if isinstance(artist, dict) else str(artist).strip()
            for artist in raw.get("artists") or []
        )
        artists = tuple(artist for artist in artists if artist)
        album = raw.get("album")
        if isinstance(album, dict):
            album = album.get("name")
        duration = raw.get("duration")
        if not duration and raw.get("duration_seconds") is not None:
            seconds = int(raw["duration_seconds"])
            duration = f"{seconds // 60}:{seconds % 60:02d}"

        return cls(
            video_id=str(video_id),
            title=str(raw.get("title") or "Sin título"),
            artists=artists,
            album=str(album) if album else None,
            duration=str(duration) if duration else None,
            position=position,
        )

    @property
    def artist(self) -> str:
        return ", ".join(self.artists) if self.artists else "Artista desconocido"

    @property
    def url(self) -> str:
        return f"https://music.youtube.com/watch?v={self.video_id}"

    def output_template(self, directory: Path) -> str:
        stem = safe_filename(f"{self.position:03d} - {self.artist} - {self.title} [{self.video_id}]")
        return str(directory / f"{stem}.%(ext)s")

    def as_dict(self) -> dict[str, Any]:
        return {
            "videoId": self.video_id,
            "title": self.title,
            "artists": list(self.artists),
            "album": self.album,
            "duration": self.duration,
            "position": self.position,
            "url": self.url,
        }


@dataclass(frozen=True)
class Playlist:
    playlist_id: str
    title: str
    count: int | None = None

    @classmethod
    def from_api(cls, raw: dict[str, Any]) -> Playlist | None:
        playlist_id = raw.get("playlistId")
        if not playlist_id:
            return None
        count = raw.get("count", raw.get("trackCount"))
        try:
            count = int(count) if count is not None else None
        except (TypeError, ValueError):
            count = None
        return cls(str(playlist_id), str(raw.get("title") or "Sin título"), count)
