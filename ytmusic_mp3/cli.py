from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

from .auth import AuthError, default_auth_path, save_browser_auth
from .downloader import (
    AudioDownloader,
    DownloadConfigurationError,
    DownloadOptions,
)
from .library import PlaylistTracks, YouTubeMusicLibrary
from .models import playlist_id


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ytmusic-mp3",
        description="Cataloga tus playlists y 'Me gusta' de YouTube Music y descarga audio MP3.",
    )
    parser.add_argument("--auth", type=Path, default=default_auth_path(), help="archivo de sesión JSON")
    parser.add_argument("--debug", action="store_true", help="muestra la traza completa de errores")
    subparsers = parser.add_subparsers(dest="command")

    auth = subparsers.add_parser("auth", help="guarda la sesión copiada desde el navegador")
    auth.add_argument("headers", nargs="?", type=Path, help="archivo con la petición cURL; si no, lee stdin")

    playlists = subparsers.add_parser("playlists", help="lista tus playlists")
    playlists.add_argument("--limit", type=int, default=100, help="máximo de playlists; 0 = todas")

    liked = subparsers.add_parser("liked", help="lista canciones con 'Me gusta'")
    liked.add_argument("--limit", type=int, default=100, help="máximo de canciones; 0 = todas")

    tracks = subparsers.add_parser("tracks", help="lista las canciones de una playlist")
    tracks.add_argument("playlist", help="ID o URL de la playlist")
    tracks.add_argument("--limit", type=int, default=100, help="máximo de canciones; 0 = todas")

    export = subparsers.add_parser("export", help="exporta todo el catálogo a JSON")
    export.add_argument("--output", type=Path, default=Path("biblioteca.json"))
    export.add_argument("--no-liked", action="store_true", help="omite las canciones con 'Me gusta'")

    download = subparsers.add_parser("download", help="descarga canciones y las convierte a MP3")
    source = download.add_mutually_exclusive_group(required=True)
    source.add_argument("--liked", action="store_true", help="descarga 'Me gusta'")
    source.add_argument("--all", action="store_true", help="descarga 'Me gusta' y todas tus playlists")
    source.add_argument("--playlist", action="append", help="ID o URL; se puede repetir")
    download.add_argument("--output", type=Path, default=Path("descargas"), help="carpeta de salida")
    download.add_argument("--limit", type=int, default=0, help="máximo por colección; 0 = todas")
    download.add_argument("--quality", choices=["128", "192", "256", "320"], default="192")
    cookies = download.add_mutually_exclusive_group()
    cookies.add_argument("--cookies", type=Path, help="archivo cookies.txt para yt-dlp")
    cookies.add_argument(
        "--cookies-from-browser",
        metavar="NAVEGADOR[:PERFIL]",
        help="usa cookies de chrome, firefox, edge, safari, brave, etc.",
    )
    download.add_argument("--ffmpeg-location", help="ruta al ejecutable o carpeta de FFmpeg")
    download.add_argument("--no-cover", action="store_true", help="no incrusta la portada")
    download.add_argument("--overwrite", action="store_true", help="re-descarga e ignora el historial")
    download.add_argument("--dry-run", action="store_true", help="muestra qué descargaría sin conectar")
    return parser


def _limit(value: int) -> int | None:
    if value < 0:
        raise ValueError("--limit no puede ser negativo.")
    return value or None


def _library(auth_path: Path) -> YouTubeMusicLibrary:
    path = auth_path.expanduser()
    if not path.is_file():
        raise AuthError(
            f"No existe la sesión '{path}'. Ejecuta primero: ytmusic-mp3 auth\n"
            "Consulta README.md para copiar la petición 'browse' de tu navegador."
        )
    try:
        from ytmusicapi import YTMusic

        return YouTubeMusicLibrary(YTMusic(str(path)))
    except ImportError as exc:
        raise AuthError("Falta ytmusicapi. Instala el proyecto con 'pip install -e .'.") from exc
    except Exception as exc:
        raise AuthError(f"No se pudo abrir la sesión '{path}': {exc}") from exc


def _print_collection(collection: PlaylistTracks) -> None:
    print(f"\n{collection.playlist.title} ({len(collection.tracks)} canciones disponibles)")
    for track in collection.tracks:
        duration = f" [{track.duration}]" if track.duration else ""
        print(f"{track.position:>4}. {track.artist} — {track.title}{duration}  ({track.video_id})")
    if collection.unavailable:
        print(f"{collection.unavailable} elemento(s) no disponible(s) se omitieron.")


def _download_options(args: argparse.Namespace) -> DownloadOptions:
    browser = profile = None
    if args.cookies_from_browser:
        browser, separator, profile = args.cookies_from_browser.partition(":")
        if not browser:
            raise ValueError("El navegador no puede estar vacío.")
        profile = profile if separator and profile else None
    return DownloadOptions(
        output=args.output,
        quality=args.quality,
        cookies_file=args.cookies,
        cookies_browser=browser,
        cookies_profile=profile,
        ffmpeg_location=args.ffmpeg_location,
        cover=not args.no_cover,
        overwrite=args.overwrite,
        dry_run=args.dry_run,
    )


def _export(args: argparse.Namespace, library: YouTubeMusicLibrary) -> int:
    document = {
        "exportedAt": datetime.now(timezone.utc).isoformat(),
        "liked": None if args.no_liked else library.liked().tracks,
        "playlists": [],
    }
    if document["liked"] is not None:
        document["liked"] = [track.as_dict() for track in document["liked"]]

    playlists = library.playlists()
    for index, playlist in enumerate(playlists, start=1):
        print(f"Exportando [{index}/{len(playlists)}] {playlist.title}")
        collection = library.playlist(playlist.playlist_id)
        document["playlists"].append(
            {
                "playlistId": playlist.playlist_id,
                "title": collection.playlist.title,
                "unavailable": collection.unavailable,
                "tracks": [track.as_dict() for track in collection.tracks],
            }
        )

    output = args.output.expanduser()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(document, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Catálogo guardado en {output.resolve()}")
    return 0


def _download(args: argparse.Namespace, library: YouTubeMusicLibrary) -> int:
    limit = _limit(args.limit)
    collections: list[tuple[str | None, str]] = []
    if args.all:
        collections.append((None, "Me gusta"))
        collections.extend((item.playlist_id, item.title) for item in library.playlists())
    elif args.liked:
        collections.append((None, "Me gusta"))
    else:
        collections.extend((playlist_id(value), value) for value in args.playlist or [])

    downloader = AudioDownloader(_download_options(args))
    failed = 0
    for source_id, label in collections:
        try:
            collection = library.liked(limit) if source_id is None else library.playlist(source_id, limit)
        except Exception as exc:
            failed += 1
            print(f"\nERROR al leer '{label}': {exc}")
            continue
        print(f"\n=== {collection.playlist.title} ===")
        if collection.unavailable:
            print(f"Se omiten {collection.unavailable} elemento(s) sin ID de vídeo.")
        summary = downloader.download(collection.tracks, collection.playlist.title)
        failed += summary.failed
        print(f"Resumen: {summary.completed} completadas/ya existentes; {summary.failed} con error.")

    if failed:
        print(f"\nTerminado con {failed} error(es). Revisa los mensajes anteriores.")
        return 1
    print("\nDescarga terminada.")
    return 0


def dispatch(args: argparse.Namespace) -> int:
    if args.command == "auth":
        if args.headers:
            raw_headers = args.headers.expanduser().read_text(encoding="utf-8")
        else:
            print("Pega la petición 'browse' copiada como cURL y termina con Ctrl+D (Ctrl+Z+Enter en Windows):")
            raw_headers = sys.stdin.read()
        save_browser_auth(raw_headers, args.auth)
        print(f"Sesión guardada en {args.auth.expanduser()}. No compartas este archivo.")
        return 0

    library = _library(args.auth)
    if args.command == "playlists":
        playlists = library.playlists(_limit(args.limit))
        for item in playlists:
            count = f" ({item.count} canciones)" if item.count is not None else ""
            print(f"{item.playlist_id}\t{item.title}{count}")
        print(f"\nTotal: {len(playlists)} playlists")
    elif args.command == "liked":
        _print_collection(library.liked(_limit(args.limit)))
    elif args.command == "tracks":
        _print_collection(library.playlist(playlist_id(args.playlist), _limit(args.limit)))
    elif args.command == "export":
        return _export(args, library)
    elif args.command == "download":
        return _download(args, library)
    return 0


def interactive_menu(parser: argparse.ArgumentParser, auth_path: Path, debug: bool) -> int:
    actions = {
        "1": ["playlists"],
        "2": ["liked"],
        "4": ["download", "--liked"],
        "5": ["download", "--all"],
        "6": ["export"],
    }
    while True:
        print(
            "\nYTMusic MP3\n"
            "1. Ver playlists\n2. Ver 'Me gusta'\n3. Descargar una playlist\n"
            "4. Descargar 'Me gusta'\n5. Descargar todo\n6. Exportar catálogo JSON\n"
            "7. Configurar sesión\n0. Salir"
        )
        choice = input("Elige una opción: ").strip()
        if choice == "0":
            return 0
        try:
            if choice == "3":
                value = input("ID o URL de la playlist: ").strip()
                argv = ["download", "--playlist", value]
            elif choice == "7":
                print("Copia una petición 'browse' como cURL (bash) en YouTube Music.")
                print("Pégala aquí; admite varias líneas. Pulsa Enter dos veces para terminar:")
                lines = []
                while line := input():
                    lines.append(line)
                raw_headers = "\n".join(lines)
                save_browser_auth(raw_headers, auth_path)
                print("Sesión guardada. No compartas el archivo de autenticación.")
                continue
            elif choice in actions:
                argv = actions[choice]
            else:
                print("Opción no válida.")
                continue
            args = parser.parse_args(["--auth", str(auth_path), *(["--debug"] if debug else []), *argv])
            dispatch(args)
        except (AuthError, DownloadConfigurationError, ValueError, OSError) as exc:
            print(f"Error: {exc}")
        except KeyboardInterrupt:
            print("\nOperación cancelada.")
        except Exception as exc:
            if debug:
                raise
            print(f"Error: {exc}")


def main(argv: Sequence[str] | None = None) -> int:
    arguments = list(argv) if argv is not None else sys.argv[1:]
    parser = build_parser()
    if not arguments and sys.stdin.isatty():
        args = parser.parse_args(arguments)
        return interactive_menu(parser, args.auth, args.debug)
    if not arguments:
        parser.print_help()
        return 0

    args = parser.parse_args(arguments)
    if not args.command:
        parser.print_help()
        return 0
    try:
        return dispatch(args)
    except KeyboardInterrupt:
        print("\nOperación cancelada.", file=sys.stderr)
        return 130
    except Exception as exc:
        if args.debug or os.environ.get("YTMUSIC_MP3_DEBUG"):
            raise
        print(f"Error: {exc}", file=sys.stderr)
        return 1
