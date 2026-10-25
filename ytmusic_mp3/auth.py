from __future__ import annotations

import os
import re
import sys
import tempfile
from pathlib import Path


class AuthError(RuntimeError):
    pass


def default_auth_path() -> Path:
    if override := os.environ.get("YTMUSIC_MP3_AUTH"):
        return Path(override).expanduser()
    if sys.platform == "win32" and os.environ.get("APPDATA"):
        base = Path(os.environ["APPDATA"])
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return base / "ytmusic-mp3" / "browser.json"


_CURL_HEADER = re.compile(
    r"(?:^|\s)(?P<option>-H|--header|-b|--cookie)(?:\s+|=)"
    r"(?:'(?P<single>[^']*)'|\"(?P<double>[^\"]*)\"|(?P<bare>[^\s]+))",
    flags=re.MULTILINE,
)


def normalize_headers(raw: str) -> str:
    """Extrae solo los encabezados; ignora el cuerpo aunque tenga comillas irregulares."""
    if not re.match(r"^\s*curl(?:\.exe)?\s", raw, flags=re.IGNORECASE):
        return raw

    headers: list[str] = []
    for match in _CURL_HEADER.finditer(raw):
        value = next(
            item for item in (match.group("single"), match.group("double"), match.group("bare"))
            if item is not None
        )
        if match.group("option") in ("-b", "--cookie"):
            value = f"cookie: {value}"
        headers.append(value)
    if not headers:
        raise AuthError("No encontré encabezados '-H' en el comando cURL.")
    return "\n".join(headers)


def save_browser_auth(raw_headers: str, destination: Path) -> None:
    if not raw_headers.strip():
        raise AuthError("No se recibieron encabezados. Copia una petición 'browse' como cURL.")
    raw_headers = normalize_headers(raw_headers)

    try:
        from ytmusicapi.auth.browser import setup_browser
    except ImportError as exc:
        raise AuthError("Falta ytmusicapi. Instala el proyecto con 'pip install -e .'.") from exc

    destination = destination.expanduser().resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(destination.parent, 0o700)
    except OSError:
        pass

    temporary_name = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=destination.parent, delete=False
        ) as temporary:
            temporary_name = temporary.name
        setup_browser(temporary_name, raw_headers)

        # Comprueba que el archivo se puede cargar antes de sustituir una sesión válida.
        from ytmusicapi import YTMusic

        YTMusic(temporary_name)
        os.replace(temporary_name, destination)
        temporary_name = None
        try:
            os.chmod(destination, 0o600)
        except OSError:
            pass
    except Exception as exc:
        raise AuthError(f"No se pudo validar la autenticación: {exc}") from exc
    finally:
        if temporary_name:
            Path(temporary_name).unlink(missing_ok=True)
