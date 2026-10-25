# YTMusic MP3

Aplicación de terminal para leer **tus propias playlists y canciones con “Me gusta”** de YouTube Music, exportar el catálogo a JSON y descargar el audio como MP3.

Usa `ytmusicapi` para la biblioteca y `yt-dlp` + FFmpeg para el audio. No modifica playlists ni valoraciones: las operaciones sobre YouTube Music son de solo lectura.

> Úsala únicamente con contenido que tengas derecho a descargar y respeta los derechos de autor y las condiciones del servicio. La disponibilidad de una canción no implica permiso para redistribuirla.

## Funciones

- Lista playlists y “Me gusta”, incluyendo artista, duración e ID de vídeo.
- Exporta toda la biblioteca a un JSON con las canciones de cada playlist.
- Descarga “Me gusta”, una o varias playlists, o toda la biblioteca.
- MP3 a 128, 192, 256 o 320 kbps, con metadatos y portada incrustada.
- Una carpeta por playlist y nombres `001 - Artista - Título [ID].mp3`.
- Historial compartido para no repetir canciones ya descargadas.
- Reintentos, continuación tras errores individuales y modo simulación.
- Cookies opcionales para contenido privado o que requiera la sesión de YouTube.
- Comandos directos y menú interactivo.

## Requisitos

- Python 3.10 o superior.
- FFmpeg disponible en el `PATH`.
- Una cuenta de YouTube Music con acceso a la biblioteca.

Instalación de FFmpeg:

```bash
# macOS
brew install ffmpeg

# Debian / Ubuntu
sudo apt install ffmpeg

# Windows con winget
winget install Gyan.FFmpeg
```

## Instalación

Desde esta carpeta:

```bash
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
python -m pip install --upgrade pip
python -m pip install -e .
```

Comprueba la instalación:

```bash
ytmusic-mp3 --help
ffmpeg -version
```

## 1. Configurar tu sesión

La sesión usa una petición de tu propio navegador. El archivo resultante contiene cookies: **no lo compartas ni lo subas a Git**.

1. Abre `https://music.youtube.com` e inicia sesión.
2. Abre las herramientas de desarrollo (`F12` u `Option+Command+I`) y entra en **Network / Red**.
3. Filtra por `browse` y navega a **Biblioteca** para generar una petición.
4. Haz clic derecho sobre una petición `browse` → **Copy / Copiar** → **Copy as cURL (bash)**.
5. Guarda el texto en `headers.txt` y ejecuta:

```bash
ytmusic-mp3 auth headers.txt
rm headers.txt                      # Windows: del headers.txt
```

También puedes pegar el texto directamente:

```bash
ytmusic-mp3 auth
# Pega el cURL y termina con Ctrl+D (Ctrl+Z+Enter en Windows).
```

La sesión se guarda de forma predeterminada en:

- macOS / Linux: `~/.config/ytmusic-mp3/browser.json`.
- Windows: `%APPDATA%\ytmusic-mp3\browser.json`.

Para usar otra ruta, pon `--auth RUTA` **antes** del comando o define `YTMUSIC_MP3_AUTH`.

## 2. Consultar y exportar

```bash
# Menú interactivo
ytmusic-mp3

# Listar playlists
ytmusic-mp3 playlists

# Ver las primeras 100 canciones con “Me gusta”
ytmusic-mp3 liked

# Sin límite
ytmusic-mp3 liked --limit 0

# Ver una playlist mediante ID o URL
ytmusic-mp3 tracks PLxxxxxxxx
ytmusic-mp3 tracks "https://music.youtube.com/playlist?list=PLxxxxxxxx"

# Exportar “Me gusta” y todas las playlists con sus pistas
ytmusic-mp3 export --output biblioteca.json
```

`export` recupera todas las canciones; puede tardar en bibliotecas grandes.

## 3. Descargar MP3

```bash
# Simular sin descargar
ytmusic-mp3 download --liked --dry-run

# “Me gusta” a 192 kbps en ./descargas
ytmusic-mp3 download --liked

# Una playlist a 320 kbps
ytmusic-mp3 download --playlist PLxxxxxxxx --quality 320

# Varias playlists en otro directorio
ytmusic-mp3 download --playlist PLxxx --playlist PLyyy --output ~/Music/YTMusic

# “Me gusta” y todas las playlists
ytmusic-mp3 download --all

# Como máximo 50 canciones por colección
ytmusic-mp3 download --all --limit 50
```

Si el vídeo requiere las cookies de YouTube, usa **una** de estas opciones:

```bash
ytmusic-mp3 download --liked --cookies-from-browser firefox
ytmusic-mp3 download --liked --cookies-from-browser chrome:Default
ytmusic-mp3 download --playlist PLxxx --cookies cookies.txt
```

Cierra el navegador si bloquea su base de datos de cookies. Extraer cookies otorga acceso a tu sesión; hazlo solo en tu propio equipo.

### Historial y repeticiones

El archivo `descargas/.ytmusic-mp3-history.txt` evita volver a bajar el mismo ID, incluso si aparece en varias playlists. Si borras un MP3 pero quieres recuperarlo, utiliza `--overwrite` (vuelve a procesar todo lo seleccionado) o retira su línea del historial.

```bash
ytmusic-mp3 download --playlist PLxxx --overwrite
```

## Problemas frecuentes

- **401 / sesión caducada:** repite `ytmusic-mp3 auth` con una petición `browse` nueva.
- **403 / formato no disponible:** actualiza `yt-dlp` con `python -m pip install -U yt-dlp`; añade cookies si el contenido requiere cuenta.
- **FFmpeg no encontrado:** instálalo o usa `--ffmpeg-location /ruta/a/ffmpeg`.
- **Playlist privada:** la sesión permite leerla; para el audio puede hacer falta también `--cookies-from-browser`.
- **Canciones grises o eliminadas:** se omiten si ya no tienen ID de vídeo; otros fallos se muestran sin detener el resto.
- **La API deja de responder tras un cambio de YouTube:** actualiza `ytmusicapi`. Es una biblioteca no oficial y puede requerir mantenimiento.

## Desarrollo y pruebas

```bash
python -m unittest discover -s tests -v
python -m compileall ytmusic_mp3
```

Las pruebas usan clientes y descargadores simulados: no necesitan credenciales ni descargan música.
