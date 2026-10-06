"""Product normalization and canonical matching engine (SPECS §6, §13)."""

from __future__ import annotations

import re
import unicodedata
import uuid
from dataclasses import dataclass

from rapidfuzz import fuzz

from ketrika.core.taxonomy import load_aliases, load_products


def normalize_product_string(raw: str) -> str:
    """Normalize commodity text for lookup: lowercase, remove accents, strip punctuation and extra spaces."""
    if not raw:
        return ""
    # NFKD normalization to separate base characters and combining accents
    nfkd = unicodedata.normalize("NFKD", raw)
    no_accents = "".join(c for c in nfkd if not unicodedata.combining(c))
    lower = no_accents.lower()
    # Strip punctuation and collapse whitespace
    clean = re.sub(r"[^\w\s]", " ", lower)
    return re.sub(r"\s+", " ", clean).strip()


@dataclass
class ProductMatch:
    """Outcome of product resolution."""

    product_code: str
    canonical_name_fr: str
    product_id: uuid.UUID | None
    confidence: float
    match_type: str  # exact_source_alias | exact_global_alias | exact_canonical | fuzzy_trigram


class ProductResolver:
    """Resolves raw product descriptions to canonical taxonomy products."""

    def __init__(self) -> None:
        self.products = {p.product_code: p for p in load_products()}
        self.aliases = load_aliases()

        # Build lookup tables
        self._exact_alias_map: dict[str, tuple[str, float]] = {}
        for a in self.aliases:
            norm_key = normalize_product_string(a.alias)
            self._exact_alias_map[norm_key] = (a.product_code, a.confidence)

        # Also add canonical names and codes
        for code, prod in self.products.items():
            self._exact_alias_map[normalize_product_string(code)] = (code, 1.0)
            self._exact_alias_map[normalize_product_string(prod.canonical_name_fr)] = (code, 1.0)

    def resolve(
        self,
        raw_product: str,
        source_id: str | None = None,
        min_fuzzy_score: float = 85.0,
    ) -> ProductMatch | None:
        """Resolve raw string to ProductMatch or None if unknown."""
        norm_raw = normalize_product_string(raw_product)
        if not norm_raw:
            return None

        # 1 & 2. Exact match on known aliases or canonical names
        if norm_raw in self._exact_alias_map:
            code, conf = self._exact_alias_map[norm_raw]
            prod = self.products[code]
            return ProductMatch(
                product_code=code,
                canonical_name_fr=prod.canonical_name_fr,
                product_id=None,
                confidence=conf,
                match_type="exact_alias",
            )

        # 3. Fuzzy match (trigram / token_sort_ratio >= 85)
        best_code: str | None = None
        best_score = 0.0
        for alias_norm, (code, _conf) in self._exact_alias_map.items():
            score = fuzz.token_sort_ratio(norm_raw, alias_norm)
            if score > best_score:
                best_score = score
                best_code = code

        if best_score >= min_fuzzy_score and best_code is not None:
            prod = self.products[best_code]
            return ProductMatch(
                product_code=best_code,
                canonical_name_fr=prod.canonical_name_fr,
                product_id=None,
                confidence=round(best_score / 100.0 * 0.9, 2),
                match_type="fuzzy_trigram",
            )

        # 4. Unknown product
        return None
