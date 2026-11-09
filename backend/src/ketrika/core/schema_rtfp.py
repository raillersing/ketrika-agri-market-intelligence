"""Declared WB v2 API/data-context shapes from the archived official packet."""

from ketrika.core.schema_json import JSONSchemaAlternatives, JSONSchemaContract, JSONShape

TEXT = JSONShape("string")
DECIMAL = JSONShape("decimal")

DATA_ROW = JSONShape(
    "object",
    properties=(
        ("ISO3", TEXT, True),
        ("country", TEXT, True),
        ("adm1_name", TEXT, False),
        ("adm2_name", TEXT, False),
        ("mkt_name", TEXT, True),
        ("price_date", TEXT, True),
        ("currency", TEXT, True),
        ("data_coverage", DECIMAL, False),
        ("spatially_interpolated", DECIMAL, False),
        ("c_rice", DECIMAL, False),
        ("c_sugar", DECIMAL, False),
        ("c_wheat_flour", DECIMAL, False),
    ),
)
CONTEXT_ROW = JSONShape(
    "object",
    properties=tuple(
        (key, TEXT, True)
        for key in (
            "iso3",
            "country",
            "ticker",
            "full_name",
            "units",
            "food_index_weight",
            "data_coverage",
            "r2_imputation",
        )
    ),
)

WB_RTFP_JSON = JSONSchemaAlternatives(
    "wb-rtfp-json-2.0.0",
    (
        JSONSchemaContract("wb-rtfp-data-v1", JSONShape("array", items=DATA_ROW), ("data",)),
        JSONSchemaContract(
            "wb-rtfp-context-v1",
            JSONShape("array", items=CONTEXT_ROW),
            ("additional", "ticker_info"),
        ),
    ),
)
