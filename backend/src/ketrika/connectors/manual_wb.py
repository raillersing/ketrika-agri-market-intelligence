"""Bounded publisher API already archived with evidence; no invented CSV URL."""

from collections.abc import Iterable
from datetime import UTC, date, datetime
from typing import ClassVar
from urllib.parse import urlencode

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


def recent_rice_history_url(as_of: date) -> str:
    """Select explicit months: publisher comparisons only support numeric values."""
    months = [
        date(year, month, 1).isoformat()
        for year in range(as_of.year - 6, as_of.year + 1)
        for month in range(1, 13)
        if (year, month) <= (as_of.year, as_of.month)
    ]
    return "https://microdata.worldbank.org/api/tables/data/fcv/wld_2021_rtfp_v02_m?" + urlencode(
        {
            "limit": 120,
            "c[ISO3]": "MDG",
            "c[c_rice]": ">0",
            "c[price_date]": ",".join(months),
            "fields": "ISO3,country,adm1_name,adm2_name,mkt_name,price_date,currency,"
            "c_rice,data_coverage,spatially_interpolated",
        }
    )


class ManualWbConnector(WbRtfpMdgConnector):
    parser_version: ClassVar[str] = "2.0.0"

    def discover(self, ctx: RunContext) -> Iterable[DiscoveredItem]:
        for url in (STUDY_URL, recent_rice_history_url(datetime.now(UTC).date())):
            yield DiscoveredItem(url=url)
