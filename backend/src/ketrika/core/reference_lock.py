"""Prepared transaction-held references; not a wired normalization snapshot."""

from sqlalchemy import text
from sqlalchemy.orm import Session

from ketrika.core.reference_manifest import ReferenceManifest, read_reference_manifest

_LOCK = "LOCK TABLE ref.location, ref.location_alias, ref.product, ref.product_alias, ref.unit_conversion IN SHARE MODE"


def lock_reference_manifest(session: Session) -> ReferenceManifest:
    session.execute(text("SET LOCAL lock_timeout = '5s'"))
    session.execute(text(_LOCK))
    return read_reference_manifest(session)
