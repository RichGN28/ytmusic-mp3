import unittest

from ytmusic_mp3.cli import _download_options, _limit, build_parser


class CliTests(unittest.TestCase):
    def setUp(self):
        self.parser = build_parser()

    def test_limit_zero_means_unlimited(self):
        self.assertIsNone(_limit(0))
        self.assertEqual(_limit(25), 25)
        with self.assertRaises(ValueError):
            _limit(-1)

    def test_repeated_playlists_are_supported(self):
        args = self.parser.parse_args(["download", "--playlist", "A", "--playlist", "B", "--dry-run"])
        self.assertEqual(args.playlist, ["A", "B"])
        self.assertTrue(args.dry_run)

    def test_browser_profile_is_split(self):
        args = self.parser.parse_args(
            ["download", "--liked", "--cookies-from-browser", "chrome:Default"]
        )
        options = _download_options(args)
        self.assertEqual(options.cookies_browser, "chrome")
        self.assertEqual(options.cookies_profile, "Default")

    def test_source_is_required(self):
        with self.assertRaises(SystemExit):
            self.parser.parse_args(["download"])


if __name__ == "__main__":
    unittest.main()
