"""Offline transport witnesses; no source requests or budget changes."""

import json
import unittest

import httpx

from transport_witness import TransportWitness


class BrokenBody(httpx.SyncByteStream):
    def __iter__(self):
        yield b"partial"
        raise httpx.ReadError("secret-token-and-cookie")


class WitnessTests(unittest.TestCase):
    def test_request_errors_propagate_without_sensitive_messages(self):
        for kind in (httpx.ConnectError, httpx.ConnectTimeout, httpx.ReadTimeout):
            with self.subTest(kind=kind):
                error = kind("secret-token-and-cookie")

                def fail(request, error=error):
                    raise error

                witness = TransportWitness(httpx.MockTransport(fail))
                with self.assertRaises(kind) as caught:
                    witness.handle_request(
                        httpx.Request(
                            "GET", "https://user:password@example.org/?token=secret"
                        )
                    )
                self.assertIs(caught.exception, error)
                self.assertEqual(witness.attempts[0]["error_class"], kind.__name__)
                self.assertEqual(witness.attempts[0]["phase"], "request_failed")
                serialized = json.dumps(witness.attempts)
                for secret in ("secret", "password", "cookie", "example.org"):
                    self.assertNotIn(secret, serialized)

    def test_partial_stream_retains_failure(self):
        witness = TransportWitness(
            httpx.MockTransport(lambda _: httpx.Response(200, stream=BrokenBody()))
        )
        with (
            httpx.Client(transport=witness) as client,
            self.assertRaises(httpx.ReadError),
        ):
            client.get("https://example.org")
        self.assertEqual(witness.attempts[0]["phase"], "body_failed")
        self.assertEqual(witness.attempts[0]["error_class"], "ReadError")
        self.assertNotIn("secret", json.dumps(witness.attempts))

    def test_success_preserves_bytes_and_status(self):
        witness = TransportWitness(
            httpx.MockTransport(lambda _: httpx.Response(200, content=b"original"))
        )
        with httpx.Client(transport=witness) as client:
            self.assertEqual(client.get("https://example.org").content, b"original")
        self.assertEqual(witness.attempts[0]["phase"], "body_complete")
        self.assertEqual(witness.attempts[0]["status"], 200)

    def test_limit_refuses_before_inner_transport(self):
        calls = []

        def respond(request):
            calls.append(request)
            return httpx.Response(200)

        witness = TransportWitness(httpx.MockTransport(respond), maximum=1)
        request = httpx.Request("GET", "https://example.org")
        witness.handle_request(request).close()
        with self.assertRaisesRegex(ValueError, "witness_limit_exhausted"):
            witness.handle_request(request)
        self.assertEqual(len(calls), 1)

    def test_invalid_bounds(self):
        for maximum in (0, -1, 101):
            with self.assertRaises(ValueError):
                TransportWitness(
                    httpx.MockTransport(lambda _: httpx.Response(200)), maximum
                )


if __name__ == "__main__":
    unittest.main()
