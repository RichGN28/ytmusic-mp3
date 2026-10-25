from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .models import Track, safe_filename


class DownloadConfigurationError(RuntimeError):
    pass


@dataclass
class DownloadSummary:
    completed: int = 0
    failed: int = 0
    failures: list[tuple[Track, str]] = field(default_factory=list)


@dataclass(frozen=True)
class DownloadOptions:
    output: Path
    quality: str = "192"
    cookies_file: Path | None = None
    cookies_browser: str | None = None
    cookies_profile: str | None = None
    ffmpeg_location: str | None = None
    cover: bool = True
    overwrite: bool = False
    dry_run: bool = False


class AudioDownloader:
    def __init__(self, options: DownloadOptions):
        self.options = options

    def download(self, tracks: list[Track], collection: str) -> DownloadSummary:
        if not tracks:
            print("No hay canciones disponibles para descargar.")
            return DownloadSummary()

        directory = self.options.output.expanduser().resolve() / safe_filename(collection)
        if self.options.dry_run:
            for track in tracks:
                print(f"[simulación] {track.artist} — {track.title} -> {directory}")
            return DownloadSummary()

        directory.mkdir(parents=True, exist_ok=True)
        self._validate_environment()
        summary = DownloadSummary()

        for index, track in enumerate(tracks, start=1):
            print(f"\n[{index}/{len(tracks)}] {track.artist} — {track.title}")
            try:
                self._download_one(track, directory)
                summary.completed += 1
            except Exception as exc:
                summary.failed += 1
                message = str(exc).strip().splitlines()[-1] if str(exc).strip() else type(exc).__name__
                summary.failures.append((track, message))
                print(f"  ERROR: {message}")

        return summary

    def _validate_environment(self) -> None:
        if not self.options.ffmpeg_location and not shutil.which("ffmpeg"):
            raise DownloadConfigurationError(
                "No se encontró FFmpeg. Instálalo o indica su ruta con --ffmpeg-location."
            )
        try:
            import yt_dlp  # noqa: F401
        except ImportError as exc:
            raise DownloadConfigurationError(
                "Falta yt-dlp. Instala el proyecto con 'pip install -e .'."
            ) from exc

    def _ydl_options(self, track: Track, directory: Path) -> dict[str, Any]:
        postprocessors = [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": self.options.quality,
            },
            {"key": "FFmpegMetadata", "add_metadata": True},
        ]
        if self.options.cover:
            postprocessors.append({"key": "EmbedThumbnail"})

        options: dict[str, Any] = {
            "format": "bestaudio/best",
            "outtmpl": {"default": track.output_template(directory)},
            "noplaylist": True,
            "postprocessors": postprocessors,
            "writethumbnail": self.options.cover,
            "overwrites": self.options.overwrite,
            "continuedl": True,
            "retries": 3,
            "fragment_retries": 3,
            "windowsfilenames": True,
            "restrictfilenames": False,
        }
        archive = self.options.output.expanduser().resolve() / ".ytmusic-mp3-history.txt"
        if not self.options.overwrite:
            options["download_archive"] = str(archive)
        if self.options.cookies_file:
            options["cookiefile"] = str(self.options.cookies_file.expanduser().resolve())
        if self.options.cookies_browser:
            options["cookiesfrombrowser"] = (
                self.options.cookies_browser,
                self.options.cookies_profile,
                None,
                None,
            )
        if self.options.ffmpeg_location:
            options["ffmpeg_location"] = self.options.ffmpeg_location
        return options

    def _download_one(self, track: Track, directory: Path) -> None:
        from yt_dlp import YoutubeDL

        with YoutubeDL(self._ydl_options(track, directory)) as ydl:
            result = ydl.download([track.url])
            if result != 0:
                raise RuntimeError(f"yt-dlp terminó con código {result}")
