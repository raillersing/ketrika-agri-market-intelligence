"""Actual external refusals stop acquisition; local quotas never reactivate it."""

import unittest

from odr_live_policy import source_must_stop


class StopPolicyTests(unittest.TestCase):
    def test_external_refusals_stop_source(self):
        for reason in (
            "Fetching disallowed by robots.txt: https://example.invalid/",
            "http_access_refused",
            "Challenge, CAPTCHA or forbidden status detected",
        ):
            with self.subTest(reason=reason):
                self.assertTrue(source_must_stop(reason))

    def test_local_configuration_and_quotas_do_not_disable_source(self):
        for reason in (
            "http_daily_budget_exhausted",
            "http_source_disabled",
            "http_budget_storage_unavailable",
            "HTTP_OFFLINE enabled",
        ):
            with self.subTest(reason=reason):
                self.assertFalse(source_must_stop(reason))
