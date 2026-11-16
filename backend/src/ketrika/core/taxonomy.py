"""Product taxonomy, alias resolution and rice varieties manager."""

import unicodedata
from pathlib import Path
from typing import Any

import yaml

from ketrika.core.models.taxonomy import (
    ProductAlias,
    ProductDefinition,
    RiceVariety,
)
from ketrika.core.registry import find_repo_root


def get_default_taxonomy_dir() -> Path:
    """Return default path to taxonomy directory."""
    root = find_repo_root()
    return root / "taxonomy"


def normalize_string(text: str) -> str:
    """Normalize text for fuzzy or case-insensitive matching."""
    if not text:
        return ""
    text = text.strip().lower()
    for q in ("’", "‘", "ʼ", "ʻ", "`", "´"):
        text = text.replace(q, "'")
    for d in ("–", "—", "−"):
        text = text.replace(d, "-")
    text = "".join(c for c in unicodedata.normalize("NFD", text) if unicodedata.category(c) != "Mn")
    return " ".join(text.split())


def load_products(taxonomy_dir: Path | str | None = None) -> list[ProductDefinition]:
    """Load and validate all products from taxonomy/products.yaml."""
    t_dir = Path(taxonomy_dir) if taxonomy_dir else get_default_taxonomy_dir()
    path = t_dir / "products.yaml"
    if not path.exists():
        raise FileNotFoundError(f"Products file not found: {path}")

    with open(path, encoding="utf-8") as f:
        data: Any = yaml.safe_load(f)

    if not isinstance(data, list):
        raise ValueError(f"Expected YAML list in {path}, got {type(data).__name__}")

    return [ProductDefinition.model_validate(item) for item in data]


def load_aliases(taxonomy_dir: Path | str | None = None) -> list[ProductAlias]:
    """Load and validate all product aliases from taxonomy/aliases.yaml."""
    t_dir = Path(taxonomy_dir) if taxonomy_dir else get_default_taxonomy_dir()
    path = t_dir / "aliases.yaml"
    if not path.exists():
        raise FileNotFoundError(f"Aliases file not found: {path}")

    with open(path, encoding="utf-8") as f:
        data: Any = yaml.safe_load(f)

    if not isinstance(data, list):
        raise ValueError(f"Expected YAML list in {path}, got {type(data).__name__}")

    return [ProductAlias.model_validate(item) for item in data]


def load_rice_varieties(taxonomy_dir: Path | str | None = None) -> list[RiceVariety]:
    """Load and validate all rice varieties from taxonomy/rice_varieties.yaml."""
    t_dir = Path(taxonomy_dir) if taxonomy_dir else get_default_taxonomy_dir()
    path = t_dir / "rice_varieties.yaml"
    if not path.exists():
        raise FileNotFoundError(f"Rice varieties file not found: {path}")

    with open(path, encoding="utf-8") as f:
        data: Any = yaml.safe_load(f)

    if not isinstance(data, list):
        raise ValueError(f"Expected YAML list in {path}, got {type(data).__name__}")

    return [RiceVariety.model_validate(item) for item in data]


def get_product(product_code: str, taxonomy_dir: Path | str | None = None) -> ProductDefinition:
    """Retrieve product definition by canonical code."""
    products = load_products(taxonomy_dir)
    for p in products:
        if p.product_code == product_code:
            return p
    raise KeyError(f"Product '{product_code}' not found in taxonomy")


def append_product_to_yaml(
    product_code: str,
    canonical_name_fr: str,
    category: str,
    base_unit: str = "kg",
    hs6_codes: list[str] | None = None,
    faostat_item_codes: list[int] | None = None,
    notes: str = "",
    taxonomy_dir: Path | str | None = None,
) -> None:
    """Safely append a new product definition to taxonomy/products.yaml (ADR-165)."""
    t_dir = Path(taxonomy_dir) if taxonomy_dir else get_default_taxonomy_dir()
    path = t_dir / "products.yaml"
    data: list[Any] = []
    if path.exists():
        with open(path, encoding="utf-8") as f:
            loaded = yaml.safe_load(f)
            if isinstance(loaded, list):
                data = loaded

    if any(item.get("product_code") == product_code for item in data if isinstance(item, dict)):
        return

    entry = {
        "product_code": product_code,
        "canonical_name_fr": canonical_name_fr,
        "category": category,
        "base_unit": base_unit,
        "hs6_codes": hs6_codes or [],
        "faostat_item_codes": faostat_item_codes or [],
        "verified": True,
        "notes": notes or f"Ajouté via l'application ({canonical_name_fr})",
    }
    data.append(entry)
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, allow_unicode=True, sort_keys=False)


def append_aliases_to_yaml(
    aliases: list[dict[str, Any]],
    taxonomy_dir: Path | str | None = None,
) -> None:
    """Safely append new alias definitions to taxonomy/aliases.yaml (ADR-165)."""
    if not aliases:
        return
    t_dir = Path(taxonomy_dir) if taxonomy_dir else get_default_taxonomy_dir()
    path = t_dir / "aliases.yaml"
    data: list[Any] = []
    if path.exists():
        with open(path, encoding="utf-8") as f:
            loaded = yaml.safe_load(f)
            if isinstance(loaded, list):
                data = loaded

    existing_norms = {
        normalize_string(item.get("alias", ""))
        for item in data
        if isinstance(item, dict) and item.get("alias")
    }

    added = False
    for a in aliases:
        raw_text = a.get("alias", "").strip()
        norm = normalize_string(raw_text)
        if norm and norm not in existing_norms:
            existing_norms.add(norm)
            data.append(
                {
                    "alias": raw_text,
                    "lang": a.get("lang", "fr"),
                    "product_code": a["product_code"],
                    "confidence": float(a.get("confidence", 0.95)),
                    "evidence": a.get("evidence", "Création utilisateur via application"),
                }
            )
            added = True

    if added:
        with open(path, "w", encoding="utf-8") as f:
            yaml.safe_dump(data, f, allow_unicode=True, sort_keys=False)


def resolve_product(
    raw_label: str,
    aliases: list[ProductAlias] | None = None,
    products: list[ProductDefinition] | None = None,
    min_confidence: float = 0.8,
) -> tuple[str, float] | None:
    """Resolve a raw commodity label to a canonical product_code.

    Returns (product_code, confidence) or None if unresolved or confidence is below threshold.
    """
    if not raw_label or not raw_label.strip():
        return None

    if aliases is None:
        aliases = load_aliases()

    norm_query = normalize_string(raw_label)
    if not norm_query:
        return None

    # 1. Exact match against canonical product codes or canonical names
    if products is None:
        try:
            products = load_products()
        except Exception:
            products = []

    for p in products:
        if (
            normalize_string(p.product_code) == norm_query
            or normalize_string(p.canonical_name_fr) == norm_query
        ):
            return (p.product_code, 1.0)

    # 2. Exact match on normalized alias
    best_match: tuple[str, float] | None = None
    for a in aliases:
        if normalize_string(a.alias) == norm_query:
            if a.confidence >= min_confidence:
                if best_match is None or a.confidence > best_match[1]:
                    best_match = (a.product_code, a.confidence)

    return best_match


def validate_taxonomy(taxonomy_dir: Path | str | None = None) -> list[str]:
    """Validate completeness, uniqueness, and cross-reference integrity of taxonomy."""
    errors: list[str] = []
    t_dir = Path(taxonomy_dir) if taxonomy_dir else get_default_taxonomy_dir()

    try:
        products = load_products(t_dir)
    except Exception as e:
        return [f"Failed to load products: {e}"]

    try:
        aliases = load_aliases(t_dir)
    except Exception as e:
        return [f"Failed to load aliases: {e}"]

    try:
        varieties = load_rice_varieties(t_dir)
    except Exception as e:
        return [f"Failed to load rice varieties: {e}"]

    product_codes: set[str] = set()
    for p in products:
        if p.product_code in product_codes:
            errors.append(f"Duplicate product_code in products.yaml: '{p.product_code}'")
        product_codes.add(p.product_code)

        if p.base_unit not in {"kg", "l"}:
            errors.append(
                f"Product '{p.product_code}' has invalid base_unit '{p.base_unit}' (must be kg or l)"
            )

        for hs in p.hs6_codes:
            if not (isinstance(hs, str) and len(hs) == 6 and hs.isdigit()):
                errors.append(
                    f"Product '{p.product_code}' has invalid HS6 code: '{hs}' (must be 6 digits)"
                )

        for fao in p.faostat_item_codes:
            if not (isinstance(fao, int) and fao > 0):
                errors.append(f"Product '{p.product_code}' has invalid FAOSTAT item code: '{fao}'")

    # Strict separation of rice products
    core_rice = {"RICE_PADDY", "RICE_WHITE_LOCAL", "RICE_WHITE_IMPORTED"}
    for r_code in core_rice:
        if r_code not in product_codes:
            errors.append(f"Core rice product '{r_code}' missing from products.yaml")

    normalized_aliases: set[str] = set()
    for a in aliases:
        if a.product_code not in product_codes:
            errors.append(
                f"Alias '{a.alias}' references non-existent product_code: '{a.product_code}'"
            )

        norm = normalize_string(a.alias)
        if norm in normalized_aliases:
            errors.append(f"Duplicate normalized alias in aliases.yaml: '{a.alias}' ({norm})")
        normalized_aliases.add(norm)

        # Rule R2.2: Aliases >= 0.9 MUST have verifiable evidence
        if a.confidence >= 0.9:
            if not a.evidence or len(a.evidence.strip()) < 5:
                errors.append(
                    f"Alias '{a.alias}' has confidence {a.confidence} >= 0.9 but missing or insufficient evidence"
                )
        else:
            # Rule R2.2: Aliases < 0.9 must have explanatory note for review rationale
            if not a.note or len(a.note.strip()) < 3:
                errors.append(
                    f"Alias '{a.alias}' has confidence {a.confidence} < 0.9 but missing disambiguation note"
                )

        # R2.2 Rice vs Paddy distinction
        norm_alias = norm.lower()
        if a.product_code == "RICE_PADDY" and any(
            k in norm_alias for k in ("blanc", "white", "blanchi")
        ):
            errors.append(
                f"Paddy alias '{a.alias}' mistakenly references milled white rice characteristics"
            )
        if a.product_code in {"RICE_WHITE_LOCAL", "RICE_WHITE_IMPORTED"} and any(
            k in norm_alias for k in ("paddy", "akotry")
        ):
            errors.append(
                f"Milled rice alias '{a.alias}' mistakenly references unmilled paddy characteristics"
            )

    variety_codes: set[str] = set()
    for v in varieties:
        if v.variety_code in variety_codes:
            errors.append(f"Duplicate variety_code in rice_varieties.yaml: '{v.variety_code}'")
        variety_codes.add(v.variety_code)

        if v.variety_code in product_codes:
            errors.append(
                f"Rice variety '{v.variety_code}' must not collide with product_code '{v.variety_code}'"
            )

        if v.rice_type not in {"local", "imported", "paddy"}:
            errors.append(f"Rice variety '{v.variety_code}' has invalid rice_type: '{v.rice_type}'")

    return errors
