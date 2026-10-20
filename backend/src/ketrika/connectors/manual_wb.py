"""Bounded publisher API already archived with evidence; no invented CSV URL."""

from collections.abc import Iterable
from typing import ClassVar

from ketrika.connectors.base import DiscoveredItem, RunContext
from ketrika.connectors.wb_rtfp_mdg import WbRtfpMdgConnector

# Verified acquisitions: tests/corpus-evidence/world_bank_rtfp/*-acquisition.json.
STUDY_URL = "https://microdata.worldbank.org/metadata/export/8240/json"
DATA_URL = (
    "https://microdata.worldbank.org/api/tables/data/fcv/wld_2021_rtfp_v02_m?limit=15"
    "&c%5BISO3%5D=MDG&fields=ISO3%2Ccountry%2Cadm1_name%2Cadm2_name%2Cmkt_name"
    "%2Cprice_date%2Ccurrency%2Cc_rice%2Cdata_coverage%2Cspatially_interpolated"
    "&c%5Bc_rice%5D=%3E0"
)


class ManualWbConnector(WbRtfpMdgConnector):
    parser_version: ClassVar[str] = "2.0.0"

    def discover(self, ctx: RunContext) -> Iterable[DiscoveredItem]:
        for url in (STUDY_URL, DATA_URL):
            yield DiscoveredItem(url=url)
