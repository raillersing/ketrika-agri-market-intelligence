"""Bounded public metadata discovery, never an arbitrary publisher URL fetch."""

from collections.abc import Iterator
from urllib.parse import urlsplit

import httpx

PATHS = {"/robots.txt", "/catalog/8240/data-api", "/metadata/export/8240/json"}
PATHS |= {
    "/api/downloads/info/MDG_2021_RTFP_v02_M/360505",
    "/api/downloads/info/MDG_2021_RTFP_v02_M/360780",
}
LIST_PATH = "/api/downloads/MDG_2021_RTFP_v02_M/files"
DOWNLOADS = {
    "/api/downloads/download/MDG_2021_RTFP_v02_M/360505": "filename=MDG_RTFP_mkt_2007_2026-09-28.zip",
    "/api/downloads/download/MDG_2021_RTFP_v02_M/360780": "filename=MDG_RTFP_mkt_2007_2026-10-05.zip",
}


class Bounded(httpx.SyncByteStream):
    def __init__(self, stream: httpx.SyncByteStream, maximum: int):
        self.stream, self.maximum = stream, maximum

    def __iter__(self) -> Iterator[bytes]:
        total = 0
        for chunk in self.stream:
            total += len(chunk)
            if total > self.maximum:
                raise ValueError("archive_response_too_large")
            yield chunk

    def close(self) -> None:
        self.stream.close()


def permitted_request(method: str, url: str, headers) -> bool:
    parsed = urlsplit(url)
    return (
        method == "GET"
        and parsed.scheme == "https"
        and parsed.hostname == "microdata.worldbank.org"
        and parsed.port in (None, 443)
        and parsed.username is None
        and parsed.password is None
        and (
            parsed.path in PATHS
            and not parsed.query
            or parsed.path == LIST_PATH
            and parsed.query == "type=data"
            or parsed.path in DOWNLOADS
            and parsed.query == DOWNLOADS[parsed.path]
        )
        and not parsed.fragment
        and not {str(key).lower() for key in headers} & {"authorization", "cookie"}
    )
