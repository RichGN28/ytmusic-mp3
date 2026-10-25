import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from ytmusic_mp3.downloader import AudioDownloader, DownloadOptions
from ytmusic_mp3.models import Track


class FakeYoutubeDL:
    instances = []
    fail_for = set()

    def __init__(self, options):
        self.options = options
        self.urls = []
        self.__class__.instances.append(self)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def download(self, urls):
        self.urls = urls
        if any(video_id in urls[0] for video_id in self.fail_for):
            return 1
        return 0


class DownloaderTests(unittest.TestCase):
    def setUp(self):
        FakeYoutubeDL.instances = []
        FakeYoutubeDL.fail_for = set()
        self.temp = tempfile.TemporaryDirectory()
        self.output = Path(self.temp.name)
        self.track = Track("abc", "Canción", ("Artista",), position=1)

    def tearDown(self):
        self.temp.cleanup()

    def options(self, **changes):
        values = {"output": self.output}
        values.update(changes)
        return DownloadOptions(**values)

    def test_builds_mp3_options_and_browser_cookies(self):
        downloader = AudioDownloader(
            self.options(cookies_browser="firefox", cookies_profile="default", quality="320")
        )
        options = downloader._ydl_options(self.track, self.output)
        self.assertEqual(options["postprocessors"][0]["preferredcodec"], "mp3")
        self.assertEqual(options["postprocessors"][0]["preferredquality"], "320")
        self.assertEqual(options["cookiesfrombrowser"], ("firefox", "default", None, None))
        self.assertTrue(options["noplaylist"])
        self.assertIn("download_archive", options)

    def test_overwrite_disables_history(self):
        options = AudioDownloader(self.options(overwrite=True))._ydl_options(self.track, self.output)
        self.assertNotIn("download_archive", options)
        self.assertTrue(options["overwrites"])

    def test_dry_run_does_not_need_yt_dlp(self):
        summary = AudioDownloader(self.options(dry_run=True)).download([self.track], "Mix")
        self.assertEqual(summary.completed, 0)
        self.assertEqual(FakeYoutubeDL.instances, [])

    def test_download_continues_after_individual_failure(self):
        tracks = [self.track, Track("bad", "Fallo", position=2), Track("ok", "Bien", position=3)]
        FakeYoutubeDL.fail_for = {"bad"}
        fake_module = types.SimpleNamespace(YoutubeDL=FakeYoutubeDL)
        downloader = AudioDownloader(self.options())
        with patch.dict(sys.modules, {"yt_dlp": fake_module}), patch.object(
            downloader, "_validate_environment"
        ):
            summary = downloader.download(tracks, "Mix")
        self.assertEqual(summary.completed, 2)
        self.assertEqual(summary.failed, 1)
        self.assertEqual(summary.failures[0][0].video_id, "bad")
        self.assertEqual(len(FakeYoutubeDL.instances), 3)


if __name__ == "__main__":
    unittest.main()
