"""Mechanically inventory corpus bytes; never infer authenticity from a filename.

Run only in Docker. Outputs JSON to stdout for review; no source file is rewritten.
Acquired documents must subsequently receive reviewed acquisition references.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


def inventory(base: Path) -> dict:
    replay_generators: dict[str, str] = {}
    for folder, prefix, pages, generator in (
        ("miasa_odr", "odr_bulletin_", (1, 2), "scripts/generate_odr_fixtures.py"),
        ("mincc_ppn", "mincc_pub_", (1,), "scripts/generate_mincc_fixtures.py"),
    ):
        for document in (base / "tests/fixtures" / folder).glob(f"{prefix}*"):
            if folder == "miasa_odr" and document.suffix != ".pdf":
                continue
            if folder == "mincc_ppn" and not document.name.startswith(
                tuple(f"mincc_pub_{i:02}_" for i in range(7, 11))
            ):
                continue
            # Generator hashes written text, not Windows CRLF physical bytes.
            data = (
                document.read_bytes()
                if document.suffix == ".pdf"
                else document.read_text().encode()
            )
            content_sha = hashlib.sha256(data).hexdigest()
            for page in pages:
                prompt = "miasa_odr_extract" if folder == "miasa_odr" else "mincc_ppn_extract"
                key = hashlib.sha256(
                    f"replay|replay-fixture|{prompt}|v1|{content_sha}|{page}".encode()
                ).hexdigest()
                replay_generators[f"{key}.json"] = generator
    files = set(base.glob("scripts/generate_*_fixtures.py"))
    for folder in ("tests/fixtures", "tests/golden", "tests/e2e_data"):
        files.update(p for p in (base / folder).rglob("*") if p.is_file())
    entries = []
    for path in sorted(files):
        if "__pycache__" in path.parts or path.suffix == ".pyc":
            continue
        relative = path.relative_to(base).as_posix()
        generator = None
        if path.parent.name == "llm" and path.name in replay_generators:
            generator = replay_generators[path.name]
        elif "mincc_pub_" in path.name:
            generator = "scripts/generate_mincc_fixtures.py"
        elif path.name.startswith("odr_bulletin_") and path.suffix in (".pdf", ".json"):
            generator = "scripts/generate_odr_fixtures.py"
        elif path.name.startswith(("douanes_stats_2024", "douanes_snapshot_")):
            generator = "scripts/generate_douanes_fixtures.py"
        elif relative == "tests/e2e_data/synthetic_gold_dataset.py":
            generator = relative
        elif relative.startswith("scripts/generate_"):
            generator = relative
        synthetic = generator is not None
        data = path.read_bytes()
        entries.append(
            {
                "path": relative,
                "sha256": hashlib.sha256(data).hexdigest(),
                "size_bytes": len(data),
                "artifact_type": path.suffix.lstrip("."),
                "authenticity": "synthetic" if synthetic else "unverified",
                "origin": {
                    "kind": "repository_generator" if synthetic else "unknown_legacy",
                    "reference": generator,
                    "limitations": "Not evidence of official acquisition or market accuracy.",
                },
                "rights": {
                    "status": "internal_test_only" if synthetic else "unknown",
                    "licence": None,
                    "evidence": None,
                    "redistribution_allowed": False,
                },
                "annotator": "agent",
                "human_reviewed": False,
            }
        )
    return {"version": 1, "entries": entries}


if __name__ == "__main__":
    result = inventory(Path("/workspace/backend"))
    output = Path("/tmp/ketrika-r04-corpus-manifest.json")
    output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(output), "files": len(result["entries"])}))
