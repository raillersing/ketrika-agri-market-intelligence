"""Local HTTP fixtures get their own identity, never a disabled public source's."""

import os
import uuid

from ketrika.connectors.registry import _CONNECTOR_REGISTRY
from ketrika.core.qualification import validate_environment


def local_connector(connector_class, monkeypatch):
    validate_environment(os.environ)
    source_id = f"fixture_{connector_class.source_id}_{uuid.uuid4().hex}"
    local_class = type("LocalFixtureConnector", (connector_class,), {"source_id": source_id})
    monkeypatch.setitem(_CONNECTOR_REGISTRY, source_id, local_class)
    return local_class()
