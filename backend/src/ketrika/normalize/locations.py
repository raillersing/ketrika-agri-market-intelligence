"""Geographic location normalization and entity resolution (SPECS §5.4, §13)."""

from __future__ import annotations

import re
import unicodedata
import uuid
from dataclasses import dataclass
from typing import Any

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
    match_type: str  # exact_pcode | exact_alias | exact_geo_id | fuzzy_trigram | historical_composite | fuzzy_candidate
    note: str | None = None


# Known provider market identifier mappings (WB RTFP, WFP HDX)
GEO_ID_MAP: dict[str, tuple[str, str, int, float, str]] = {
    "gid_mdg_national_average": ("MDG", "Madagascar", 0, 1.0, "exact_geo_id"),
    "mkt_mdg_analakely": ("MKT_ANALAKELY", "Analakely", 9, 1.0, "exact_geo_id"),
    "mkt_mdg_alakamisy": ("MKT_ALAKAMISY", "Alakamisy", 9, 1.0, "exact_geo_id"),
    "mkt_mdg_anosibe": ("MKT_ANOSIBE", "Anosibe", 9, 1.0, "exact_geo_id"),
    "mkt_mdg_isotry": ("MKT_ISOTRY", "Isotry", 9, 1.0, "exact_geo_id"),
    "mkt_mdg_bazar_be": ("MKT_BAZAR_BE", "Bazar Be", 9, 1.0, "exact_geo_id"),
    "mkt_mdg_asabotsy": ("MKT_ASABOTSY", "Asabotsy", 9, 1.0, "exact_geo_id"),
}


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
        # Stores (pcode, name, admin_level_int, base_confidence, note)
        self._alias_details: dict[str, tuple[str, str, int, float, str]] = {}

        # Add canonical names to alias map
        for e in self.entities:
            lvl_int = parse_admin_level(e.admin_level)
            norm_fr = normalize_location_string(e.name_fr)
            if norm_fr:
                self._exact_alias_map[norm_fr] = (e.pcode, 1.0)
                self._alias_details[norm_fr] = (
                    e.pcode,
                    e.name_fr,
                    lvl_int,
                    1.0,
                    "Nom canonique FR",
                )
            if e.name_mg:
                norm_mg = normalize_location_string(e.name_mg)
                if norm_mg:
                    self._exact_alias_map[norm_mg] = (e.pcode, 1.0)
                    self._alias_details[norm_mg] = (
                        e.pcode,
                        e.name_mg,
                        lvl_int,
                        1.0,
                        "Nom canonique MG",
                    )
            pcode_norm = normalize_location_string(e.pcode)
            self._exact_alias_map[pcode_norm] = (e.pcode, 1.0)
            self._alias_details[pcode_norm] = (e.pcode, e.name_fr, lvl_int, 1.0, "P-Code")

        # Add official aliases
        for a in self.aliases:
            norm_alias = normalize_location_string(a.alias)
            if norm_alias:
                lvl_int = parse_admin_level(a.admin_level)
                self._exact_alias_map[norm_alias] = (a.pcode, a.confidence)
                self._alias_details[norm_alias] = (a.pcode, a.alias, lvl_int, a.confidence, a.note)

    def resolve(
        self,
        raw_location: str | None,
        target_admin_level: int | None = None,
        min_fuzzy_score: float = 85.0,
        geo_id: str | None = None,
        date_reference: Any | None = None,
    ) -> LocationMatch | None:
        """Resolve raw string or provider geo_id to LocationMatch or None if unknown (no arbitrary default)."""
        # 0. Provider Geo ID match (e.g. World Bank RTFP or WFP HDX)
        if geo_id:
            geo_id_clean = geo_id.strip().lower()
            if geo_id_clean in GEO_ID_MAP:
                pcode, name, lvl, conf, match_t = GEO_ID_MAP[geo_id_clean]
                return LocationMatch(
                    pcode=pcode,
                    name=name,
                    admin_level=lvl,
                    location_id=None,
                    confidence=conf,
                    match_type=match_t,
                    note=f"Resolved via provider geo_id '{geo_id}'",
                )

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

        # 2. Historical composite region check (e.g. Vatovavy-Fitovinany before 2021)
        if norm_raw in ("vatovavy fitovinany", "vatovavyfitovinany"):
            note = "Région historique composite Vatovavy-Fitovinany rattachée à Vatovavy (MDG23)"
            if date_reference is not None:
                note += f" (période observée: {date_reference})"
            return LocationMatch(
                pcode="MDG23",
                name="Vatovavy-Fitovinany",
                admin_level=1,
                location_id=None,
                confidence=0.85,
                match_type="historical_composite",
                note=note,
            )

        # 3. Exact alias match (supporting both administrative entities and markets)
        if norm_raw in self._exact_alias_map:
            pcode, conf = self._exact_alias_map[norm_raw]
            details = self._alias_details.get(norm_raw)
            if details:
                _, name, lvl_int, _, note = details
                return LocationMatch(
                    pcode=pcode,
                    name=name,
                    admin_level=lvl_int,
                    location_id=None,
                    confidence=conf,
                    match_type="exact_alias",
                    note=note,
                )
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

        # 4. Fuzzy match (filter by admin_level if requested)
        best_pcode: str | None = None
        best_score = 0.0
        best_alias_norm: str | None = None
        for alias_norm, (pcode, _conf) in self._exact_alias_map.items():
            details = self._alias_details.get(alias_norm)
            lvl_int: int | None = details[2] if details else None
            if lvl_int is None:
                ent_fuzzy = self._pcode_map.get(pcode)
                if ent_fuzzy:
                    lvl_int = parse_admin_level(ent_fuzzy.admin_level)

            if target_admin_level is not None and lvl_int != target_admin_level:
                continue

            score = fuzz.token_sort_ratio(norm_raw, alias_norm)
            if score > best_score:
                best_score = score
                best_pcode = pcode
                best_alias_norm = alias_norm

        if best_score >= min_fuzzy_score and best_pcode is not None and best_alias_norm is not None:
            details = self._alias_details.get(best_alias_norm)
            name = details[1] if details else best_pcode
            lvl_int = details[2] if details else 1
            return LocationMatch(
                pcode=best_pcode,
                name=name,
                admin_level=lvl_int,
                location_id=None,
                confidence=round(best_score / 100.0 * 0.9, 2),
                match_type="fuzzy_trigram",
                note=f"Fuzzy match similarity score {best_score}% with alias '{best_alias_norm}'",
            )

        return None

    def propose_alias_candidates(
        self,
        raw_location: str | None,
        min_fuzzy_score: float = 70.0,
        limit: int = 5,
    ) -> list[LocationMatch]:
        """Propose candidate matches for human review (Gate H5), never auto-accepted into Gold."""
        if not raw_location or not raw_location.strip():
            return []
        clean_raw = raw_location.strip()
        norm_raw = normalize_location_string(clean_raw)
        if not norm_raw:
            return []

        candidates: list[tuple[float, LocationMatch]] = []
        seen_pcodes: set[str] = set()

        for alias_norm, details in self._alias_details.items():
            pcode, name, admin_level, base_conf, note = details
            if pcode in seen_pcodes:
                continue
            score = fuzz.token_sort_ratio(norm_raw, alias_norm)
            if score >= min_fuzzy_score:
                cand_conf = round((score / 100.0) * base_conf, 2)
                cand = LocationMatch(
                    pcode=pcode,
                    name=name,
                    admin_level=admin_level,
                    location_id=None,
                    confidence=cand_conf,
                    match_type="fuzzy_candidate",
                    note=f"Similarity score {score}% with alias '{alias_norm}' ({note})",
                )
                candidates.append((cand_conf, cand))
                seen_pcodes.add(pcode)

        candidates.sort(key=lambda x: x[0], reverse=True)
        return [c for _, c in candidates[:limit]]
