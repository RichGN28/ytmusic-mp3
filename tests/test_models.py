import unittest
from pathlib import Path

from ytmusic_mp3.models import Playlist, Track, playlist_id, safe_filename


class ModelTests(unittest.TestCase):
    def test_safe_filename_removes_unsafe_characters(self):
        self.assertEqual(safe_filename(' AC/DC: "TNT"? '), "AC_DC_ _TNT_")

    def test_safe_filename_handles_empty_and_reserved_names(self):
        self.assertEqual(safe_filename("..."), "sin_titulo")
        self.assertEqual(safe_filename("CON"), "_CON")

    def test_playlist_id_accepts_id_and_url(self):
        self.assertEqual(playlist_id("PL123"), "PL123")
        self.assertEqual(
            playlist_id("https://music.youtube.com/playlist?list=PL123&si=abc"),
            "PL123",
        )
        with self.assertRaises(ValueError):
            playlist_id("https://music.youtube.com/watch?v=abc")

    def test_track_parses_metadata_and_output(self):
        track = Track.from_api(
            {
                "videoId": "abc123",
                "title": "Canción",
                "artists": [{"name": "Uno"}, {"name": "Dos"}],
                "album": {"name": "Álbum"},
                "duration_seconds": 125,
            },
            position=7,
        )
        self.assertIsNotNone(track)
        self.assertEqual(track.artist, "Uno, Dos")
        self.assertEqual(track.album, "Álbum")
        self.assertEqual(track.duration, "2:05")
        self.assertIn("watch?v=abc123", track.url)
        self.assertTrue(track.output_template(Path("/tmp")).endswith(".%(ext)s"))
        self.assertEqual(track.as_dict()["position"], 7)

    def test_unavailable_track_is_ignored(self):
        self.assertIsNone(Track.from_api({"title": "Borrada"}))
        self.assertIsNone(Playlist.from_api({"title": "Sin ID"}))


if __name__ == "__main__":
    unittest.main()
