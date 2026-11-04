import unittest

import httpx

from wb_archive_policy import Bounded, permitted_request


class ArchivePolicyTests(unittest.TestCase):
    def test_official_anonymous_metadata_get_only(self):
        for path in (
            "/robots.txt",
            "/catalog/8240/data-api",
            "/metadata/export/8240/json",
        ):
            self.assertTrue(
                permitted_request("GET", "https://microdata.worldbank.org" + path, {})
            )

    def test_official_listing_query_only(self):
        listing = (
            "https://microdata.worldbank.org/api/downloads/MDG_2021_RTFP_v02_M/files"
        )
        self.assertTrue(permitted_request("GET", listing + "?type=data", {}))
        self.assertFalse(permitted_request("GET", listing + "?type=private", {}))

    def test_only_the_two_listed_original_archives_are_permitted(self):
        prefix = "https://microdata.worldbank.org/api/downloads/download/MDG_2021_RTFP_v02_M/"
        self.assertTrue(
            permitted_request(
                "GET", prefix + "360505?filename=MDG_RTFP_mkt_2007_2026-09-28.zip", {}
            )
        )
        self.assertTrue(
            permitted_request(
                "GET", prefix + "360780?filename=MDG_RTFP_mkt_2007_2026-10-05.zip", {}
            )
        )
        self.assertFalse(
            permitted_request("GET", prefix + "360505?filename=other.zip", {})
        )
        self.assertFalse(
            permitted_request(
                "GET",
                prefix
                + "360780?filename=MDG_RTFP_mkt_2007_2026-10-05.zip&token=synthetic",
                {},
            )
        )

    def test_response_size_bound_preserves_or_refuses_bytes(self):
        self.assertEqual(b"".join(Bounded(httpx.ByteStream(b"1234"), 4)), b"1234")
        with self.assertRaisesRegex(ValueError, "archive_response_too_large"):
            b"".join(Bounded(httpx.ByteStream(b"12345"), 4))

    def test_other_origin_path_auth_or_method_is_refused(self):
        base = "https://microdata.worldbank.org/catalog/8240/data-api"
        for method, url, headers in (
            ("POST", base, {}),
            ("GET", base.replace("https:", "http:"), {}),
            ("GET", base.replace(".org", ".org.example.invalid"), {}),
            ("GET", base.replace("/catalog/8240/data-api", "/private"), {}),
            ("GET", base + "?token=synthetic", {}),
            ("GET", base.replace("https://", "https://synthetic@"), {}),
            ("GET", base, {"Cookie": "synthetic"}),
            ("GET", base, {"Authorization": "synthetic"}),
        ):
            self.assertFalse(permitted_request(method, url, headers))


if __name__ == "__main__":
    unittest.main()
