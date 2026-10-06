"""Geographic location normalization and entity resolution (SPECS §5.4, §13)."""

from __future__ import annotations

import re
import unicodedata
import uuid
from dataclasses import dataclass

from rapidfuzz import fuzz

from ketrika.core.geo import load_geographic_entities, load_location_aliases


def normalize_location_string(raw: str) -> str:
    """Normalize location name: lowercase, strip accents, collapse spaces."""
    if not raw:
        return ""
    nfkd = unicodedata.normalize("NFKD", raw)
    no_accents = "".join(c for c in nfkd if not unicodedata.combining(c))
    lower = no_accents.lower()
    clean = re.sub(r"[^\w\s]", " ", lower)
    return re.sub(r"\s+", " ", clean).strip()


def parse_admin_level(level: str | int) -> int:
    """Convert admin level string (admin0..admin3, market) to integer (0..3, 9)."""
    if isinstance(level, int):
        return level
    lvl = str(level).strip().lower()
    if lvl == "admin0":
        return 0
    elif lvl == "admin1":
        return 1
    elif lvl == "admin2":
        return 2
    elif lvl == "admin3":
        return 3
    elif lvl in ("market", "admin9", "9"):
        return 9
    elif lvl.isdigit():
        return int(lvl)
    return 1


@dataclass
class LocationMatch:
    """Outcome of geographic location resolution."""

    pcode: str
    name: str
    admin_level: int
    location_id: uuid.UUID | None
    confidence: float
    match_type: str  # exact_pcode | exact_alias | fuzzy_trigram


class LocationResolver:
    """Resolves raw location strings to canonical administrative entities (OCHA COD-AB)."""

    def __init__(self) -> None:
        self.entities = []
        for lvl in ["admin0", "admin1", "admin2", "admin3"]:
            try:
                self.entities.extend(load_geographic_entities(lvl))
            except Exception:
                pass

        self.aliases = load_location_aliases()

        self._pcode_map = {e.pcode: e for e in self.entities}
        self._exact_alias_map: dict[str, tuple[str, float]] = {}

        # Add canonical names to alias map
        for e in self.entities:
            norm_fr = normalize_location_string(e.name_fr)
            if norm_fr:
                self._exact_alias_map[norm_fr] = (e.pcode, 1.0)
            if e.name_mg:
                norm_mg = normalize_location_string(e.name_mg)
                if norm_mg:
                    self._exact_alias_map[norm_mg] = (e.pcode, 1.0)
            self._exact_alias_map[normalize_location_string(e.pcode)] = (e.pcode, 1.0)

        # Add official aliases
        for a in self.aliases:
            norm_alias = normalize_location_string(a.alias)
            if norm_alias:
                self._exact_alias_map[norm_alias] = (a.pcode, a.confidence)

    def resolve(
        self,
        raw_location: str | None,
        target_admin_level: int | None = None,
        min_fuzzy_score: float = 85.0,
    ) -> LocationMatch | None:
        """Resolve raw string to LocationMatch or None if unknown."""
        if not raw_location:
            return None

        clean_raw = raw_location.strip()
        norm_raw = normalize_location_string(clean_raw)
        if not norm_raw:
            return None

        # 1. Direct P-Code match
        upper_raw = clean_raw.upper()
        if upper_raw in self._pcode_map:
            ent = self._pcode_map[upper_raw]
            lvl_int = parse_admin_level(ent.admin_level)
            return LocationMatch(
                pcode=ent.pcode,
                name=ent.name_fr,
                admin_level=lvl_int,
                location_id=None,
                confidence=1.0,
                match_type="exact_pcode",
            )

        # 2. Exact alias match
        if norm_raw in self._exact_alias_map:
            pcode, conf = self._exact_alias_map[norm_raw]
            ent_alias = self._pcode_map.get(pcode)
            if ent_alias:
                lvl_int = parse_admin_level(ent_alias.admin_level)
                return LocationMatch(
                    pcode=ent_alias.pcode,
                    name=ent_alias.name_fr,
                    admin_level=lvl_int,
                    location_id=None,
                    confidence=conf,
                    match_type="exact_alias",
                )

        # 3. Fuzzy match (filter by admin_level if requested)
        best_pcode: str | None = None
        best_score = 0.0
        for alias_norm, (pcode, _conf) in self._exact_alias_map.items():
            ent_fuzzy = self._pcode_map.get(pcode)
            if not ent_fuzzy:
                continue
            lvl_int = parse_admin_level(ent_fuzzy.admin_level)
            if target_admin_level is not None and lvl_int != target_admin_level:
                continue

            score = fuzz.token_sort_ratio(norm_raw, alias_norm)
            if score > best_score:
                best_score = score
                best_pcode = pcode

        if best_score >= min_fuzzy_score and best_pcode is not None:
            ent_match = self._pcode_map[best_pcode]
            lvl_int = parse_admin_level(ent_match.admin_level)
            return LocationMatch(
                pcode=ent_match.pcode,
                name=ent_match.name_fr,
                admin_level=lvl_int,
                location_id=None,
                confidence=round(best_score / 100.0 * 0.9, 2),
                match_type="fuzzy_trigram",
            )

        return None
