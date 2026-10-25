import tempfile
import unittest
from pathlib import Path

from ytmusic_mp3.auth import AuthError, normalize_headers, save_browser_auth


CURL = r"""curl 'https://music.youtube.com/youtubei/v1/browse' \
  -H 'authorization: SAPISIDHASH 1234567890_abcdef' \
  -H 'cookie: SID=fake; HSID=fake; SSID=fake; APISID=fake; SAPISID=fake; __Secure-3PAPISID=fake' \
  -H 'x-goog-authuser: 0' \
  -H 'x-origin: https://music.youtube.com' """


class AuthTests(unittest.TestCase):
    def test_curl_is_converted_to_raw_headers(self):
        headers = normalize_headers(CURL)
        self.assertIn("cookie: SID=fake", headers)
        self.assertIn("x-goog-authuser: 0", headers)
        self.assertNotIn("curl", headers)

    def test_plain_headers_are_preserved(self):
        raw = "cookie: a=b\nx-goog-authuser: 0"
        self.assertEqual(normalize_headers(raw), raw)

    def test_invalid_curl_has_friendly_error(self):
        with self.assertRaises(AuthError):
            normalize_headers("curl 'https://music.youtube.com")

    def test_unclosed_data_raw_does_not_invalidate_headers(self):
        raw = CURL + " \\\n  --data-raw '{\"query\":\"it's unclosed}"
        headers = normalize_headers(raw)
        self.assertIn("cookie: SID=fake", headers)
        self.assertIn("x-goog-authuser: 0", headers)
        self.assertNotIn("data-raw", headers)

    def test_current_ytmusicapi_accepts_converted_curl(self):
        with tempfile.TemporaryDirectory() as folder:
            destination = Path(folder) / "browser.json"
            save_browser_auth(CURL, destination)
            self.assertTrue(destination.is_file())
            self.assertIn("cookie", destination.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
