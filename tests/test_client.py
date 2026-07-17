"""Checks for request encoding that must match ASP.NET AJAX."""

import unittest
from urllib.parse import parse_qsl, urlencode


class LoginEncodingTest(unittest.TestCase):
    def test_utf8_urlencoding_round_trip(self) -> None:
        fields = (("username", "reader"), ("password", "päss&=+%"))
        body = urlencode(fields).encode("utf-8")

        self.assertEqual(fields, tuple(parse_qsl(body.decode("ascii"))))


if __name__ == "__main__":
    unittest.main()
