import unittest

from ytmusic_mp3.library import YouTubeMusicLibrary


class FakeClient:
    def get_library_playlists(self, limit=None):
        return [
            {"playlistId": "PL1", "title": "Una", "count": "2"},
            {"title": "Inválida"},
        ]

    def get_liked_songs(self, limit=None):
        return {
            "trackCount": 2,
            "tracks": [
                {"videoId": "a", "title": "A"},
                {"videoId": None, "title": "No disponible"},
            ],
        }

    def get_playlist(self, playlist_id, limit=None):
        return {
            "title": "Una",
            "trackCount": 1,
            "tracks": [{"videoId": "b", "title": "B"}],
        }


class LibraryTests(unittest.TestCase):
    def setUp(self):
        self.library = YouTubeMusicLibrary(FakeClient())

    def test_playlists_discards_invalid_entries(self):
        playlists = self.library.playlists()
        self.assertEqual(len(playlists), 1)
        self.assertEqual(playlists[0].count, 2)

    def test_liked_counts_unavailable_tracks(self):
        liked = self.library.liked()
        self.assertEqual(liked.playlist.playlist_id, "LM")
        self.assertEqual(len(liked.tracks), 1)
        self.assertEqual(liked.unavailable, 1)

    def test_playlist_preserves_title(self):
        playlist = self.library.playlist("PL1")
        self.assertEqual(playlist.playlist.title, "Una")
        self.assertEqual(playlist.tracks[0].video_id, "b")


if __name__ == "__main__":
    unittest.main()
