"""Unit tests for dynamic product catalog management and batch observations ingestion (ADR-165)."""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from ketrika.api.auth import get_current_user
from ketrika.api.main import app
from ketrika.core.db import get_db
from ketrika.core.models.db import Location, Product, ProductAlias, UserAccount
from ketrika.core.taxonomy import (
    append_aliases_to_yaml,
    append_product_to_yaml,
    load_products,
)


@pytest.fixture
def mock_user() -> UserAccount:
    """Mock authenticated analyst user."""
    return UserAccount(
        user_id=uuid.uuid4(),
        email="analyst@ketrika.local",
        role="analyst",
        disabled=False,
    )


@pytest.fixture
def test_client(mock_user: UserAccount) -> TestClient:
    """FastAPI TestClient with overridden auth."""
    app.dependency_overrides[get_current_user] = lambda: mock_user
    client = TestClient(app)
    yield client
    app.dependency_overrides.pop(get_current_user, None)


def test_list_products(test_client: TestClient) -> None:
    """Test GET /v1/products retrieves products."""
    mock_session = MagicMock()
    prod = Product(
        product_id=uuid.uuid4(),
        product_code="RICE_WHITE_LOCAL",
        canonical_name_fr="Riz blanc local",
        category="cereal",
        base_unit="kg",
        hs6_codes=["100630"],
        faostat_item_codes=[],
    )
    alias = ProductAlias(
        alias_id=uuid.uuid4(),
        alias_norm="vary gasy",
        alias_display="vary gasy",
        lang="mg",
        product_id=prod.product_id,
        confidence=0.95,
        origin="seed",
        human_reviewed=True,
    )
    mock_session.execute.return_value.scalars.return_value.all.side_effect = [
        [prod],
        [alias],
    ]

    app.dependency_overrides[get_db] = lambda: mock_session
    try:
        response = test_client.get("/v1/products")
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1
        assert data[0]["product_code"] == "RICE_WHITE_LOCAL"
        assert "vary gasy" in data[0]["aliases"]
    finally:
        app.dependency_overrides.pop(get_db, None)


def test_get_product_by_code_success(test_client: TestClient) -> None:
    """Test GET /v1/products/{product_code} with existing product."""
    mock_session = MagicMock()
    prod = Product(
        product_id=uuid.uuid4(),
        product_code="VANILLA",
        canonical_name_fr="Vanille naturelle",
        category="spice",
        base_unit="kg",
        hs6_codes=["090500"],
        faostat_item_codes=[],
    )
    mock_session.execute.return_value.scalar_one_or_none.return_value = prod
    mock_session.execute.return_value.scalars.return_value.all.return_value = []

    app.dependency_overrides[get_db] = lambda: mock_session
    try:
        response = test_client.get("/v1/products/VANILLA")
        assert response.status_code == 200
        data = response.json()
        assert data["product_code"] == "VANILLA"
        assert data["canonical_name_fr"] == "Vanille naturelle"
    finally:
        app.dependency_overrides.pop(get_db, None)


def test_get_product_by_code_not_found(test_client: TestClient) -> None:
    """Test GET /v1/products/{product_code} with unknown product returns 404."""
    mock_session = MagicMock()
    mock_session.execute.return_value.scalar_one_or_none.return_value = None

    app.dependency_overrides[get_db] = lambda: mock_session
    try:
        response = test_client.get("/v1/products/UNKNOWN_COMMODITY")
        assert response.status_code == 404
    finally:
        app.dependency_overrides.pop(get_db, None)


def test_create_product_success(test_client: TestClient) -> None:
    """Test POST /v1/products creates product, aliases and triggers YAML sync."""
    mock_session = MagicMock()
    mock_session.execute.return_value.scalar_one_or_none.return_value = None
    mock_session.scalars.return_value.all.return_value = []

    app.dependency_overrides[get_db] = lambda: mock_session
    try:
        with (
            patch("ketrika.api.routers.products.append_product_to_yaml") as mock_append_p,
            patch("ketrika.api.routers.products.append_aliases_to_yaml") as mock_append_a,
        ):
            payload = {
                "product_code": "CLOVE_SPICE",
                "canonical_name_fr": "Girofle de Madagascar",
                "category": "spice",
                "base_unit": "kg",
                "hs6_codes": ["090710"],
                "faostat_item_codes": [],
                "aliases": ["girofle", "clove", "karafo"],
                "notes": "Épice d'exportation majeure",
            }
            response = test_client.post("/v1/products", json=payload)
            assert response.status_code == 201
            data = response.json()
            assert data["product_code"] == "CLOVE_SPICE"
            assert data["canonical_name_fr"] == "Girofle de Madagascar"
            assert mock_session.add.call_count >= 2  # Product + aliases
            assert mock_session.commit.called
            assert mock_append_p.called
            assert mock_append_a.called
    finally:
        app.dependency_overrides.pop(get_db, None)


def test_create_product_duplicate_conflict(test_client: TestClient) -> None:
    """Test POST /v1/products returns 409 Conflict if product_code exists."""
    mock_session = MagicMock()
    mock_session.execute.return_value.scalar_one_or_none.return_value = Product(
        product_code="RICE_WHITE_LOCAL",
        canonical_name_fr="Riz blanc",
        category="cereal",
        base_unit="kg",
    )

    app.dependency_overrides[get_db] = lambda: mock_session
    try:
        payload = {
            "product_code": "RICE_WHITE_LOCAL",
            "canonical_name_fr": "Riz blanc",
            "category": "cereal",
            "base_unit": "kg",
        }
        response = test_client.post("/v1/products", json=payload)
        assert response.status_code == 409
        assert "existe déjà" in response.json()["detail"]
    finally:
        app.dependency_overrides.pop(get_db, None)


def test_create_observations_batch_success(test_client: TestClient) -> None:
    """Test POST /v1/products/{product_code}/observations with 100% Bronze provenance."""
    mock_session = MagicMock()
    prod = Product(
        product_id=uuid.uuid4(),
        product_code="VANILLA",
        canonical_name_fr="Vanille",
        category="spice",
        base_unit="kg",
    )
    loc = Location(
        location_id=uuid.uuid4(),
        pcode="MDG11",
        name="Analamanga",
        admin_level=1,
    )
    mock_session.execute.return_value.scalar_one_or_none.return_value = prod
    mock_session.get.return_value = None  # Source user_upload check
    mock_session.scalars.return_value.all.return_value = [loc]
    mock_session.scalars.return_value.first.return_value = None

    app.dependency_overrides[get_db] = lambda: mock_session
    try:
        with patch("ketrika.api.routers.products.BronzeStore") as mock_bronze_cls:
            mock_bronze = MagicMock()
            mock_bronze_cls.return_value = mock_bronze
            mock_artifact = MagicMock()
            mock_artifact.content_sha256 = "abcdef1234567890"
            mock_artifact.object_key = "user_upload/2026/11/abc.json"
            mock_bronze.put.return_value = mock_artifact

            payload = {
                "observations": [
                    {
                        "date": "2026-05-15",
                        "location_pcode": "MDG11",
                        "actor_level": "retail",
                        "price": 450000.0,
                        "currency": "MGA",
                        "unit": "kg",
                        "source_name": "Enquête SAVA 2026",
                    },
                    {
                        "date": "2026-06",
                        "location_pcode": "MDG11",
                        "actor_level": "retail",
                        "price": 460000.0,
                        "currency": "MGA",
                        "unit": "kg",
                        "source_name": "Enquête SAVA 2026",
                    },
                ],
                "notes": "Campagne vanille verte 2026",
            }
            response = test_client.post("/v1/products/VANILLA/observations", json=payload)
            assert response.status_code == 201
            data = response.json()
            assert data["product_code"] == "VANILLA"
            assert data["observations_created"] == 2
            assert data["bronze_content_hash"] == "abcdef1234567890"
            assert mock_bronze.put.called
            assert mock_session.commit.called
    finally:
        app.dependency_overrides.pop(get_db, None)


def test_append_product_and_aliases_to_yaml(tmp_path) -> None:
    """Test append_product_to_yaml and append_aliases_to_yaml persistence."""
    products_file = tmp_path / "products.yaml"
    aliases_file = tmp_path / "aliases.yaml"

    products_file.write_text("[]\n", encoding="utf-8")
    aliases_file.write_text("[]\n", encoding="utf-8")

    append_product_to_yaml(
        product_code="PEPPER_BLACK",
        canonical_name_fr="Poivre noir",
        category="spice",
        base_unit="kg",
        hs6_codes=["090411"],
        taxonomy_dir=tmp_path,
    )

    loaded = load_products(tmp_path)
    assert len(loaded) == 1
    assert loaded[0].product_code == "PEPPER_BLACK"
    assert loaded[0].canonical_name_fr == "Poivre noir"

    append_aliases_to_yaml(
        [
            {"alias": "poivre noir", "product_code": "PEPPER_BLACK", "lang": "fr"},
            {"alias": "dipoiny", "product_code": "PEPPER_BLACK", "lang": "mg"},
        ],
        taxonomy_dir=tmp_path,
    )

    from ketrika.core.taxonomy import load_aliases

    aliases_loaded = load_aliases(tmp_path)
    assert len(aliases_loaded) == 2
    assert any(a.alias == "dipoiny" for a in aliases_loaded)
