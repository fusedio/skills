#!/usr/bin/env python3
"""Regenerate workbench/skills/json-ui-schemas/reference.md from the live CLI or a directory of schema JSON files."""

import argparse
import json
import subprocess
import sys
from pathlib import Path

REFERENCE_PATH = Path(__file__).parent.parent / "skills/json-ui-schemas/reference.md"


def load_components(schema_dir):
    if schema_dir is not None:
        components = [
            json.loads(path.read_text(encoding="utf-8"))
            for path in sorted(schema_dir.glob("*.json"))
        ]
        if not components:
            sys.exit(f"No *.json schema files in {schema_dir}")
        return components

    result = subprocess.run(
        ["fused", "workbench", "json-ui", "schemas"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(result.stderr, file=sys.stderr)
        sys.exit(1)
    return json.loads(result.stdout)["components"]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--schema-dir",
        type=Path,
        help="read component schemas from the *.json files in this directory instead of `fused workbench json-ui schemas`",
    )
    args = parser.parse_args()

    components = sorted(load_components(args.schema_dir), key=lambda c: c["type"])

    lines = ["# JSON UI component schemas"]
    for comp in components:
        schema = comp.get("propsSchema", {})
        schema.pop("$schema", None)

        lines.append(f"\n## {comp['type']}\n")
        lines.append(comp.get("description", ""))
        lines.append("\n~~~json")
        lines.append(json.dumps(schema, indent=2))
        lines.append("~~~")

    REFERENCE_PATH.write_text("\n".join(lines) + "\n")
    print(f"Wrote {len(components)} components to {REFERENCE_PATH}")


if __name__ == "__main__":
    main()
