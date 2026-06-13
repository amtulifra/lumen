#!/usr/bin/env python3
"""Alembic migration health check for Lumen.

Checks:
1) Every migration file has revision/down_revision metadata.
2) All down_revision references resolve to existing revision files.
3) Exactly one head exists.
4) No disconnected migration components.
5) Tables created by migrations exist in db/schema.sql.
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
VERSIONS_DIR = ROOT / "db" / "migrations" / "versions"
SCHEMA_FILE = ROOT / "db" / "schema.sql"

REVISION_RE = re.compile(r'^\s*revision\s*=\s*["\']([^"\']+)["\']\s*$', re.MULTILINE)
DOWN_REVISION_RE = re.compile(r"^\s*down_revision\s*=\s*(.+?)\s*$", re.MULTILINE)
CREATE_TABLE_RE = re.compile(
    r"CREATE\s+TABLE\s+IF\s+NOT\s+EXISTS\s+([a-zA-Z_][a-zA-Z0-9_]*)",
    re.IGNORECASE,
)


@dataclass
class RevisionMeta:
    file: Path
    revision: str
    down_revisions: list[str]


def _parse_down_revision(raw: str) -> list[str]:
    value = raw.split("#", 1)[0].strip()
    if value == "None":
        return []
    if value.startswith(("'", '"')) and value.endswith(("'", '"')):
        return [value[1:-1]]
    if value.startswith("(") and value.endswith(")"):
        inner = value[1:-1].strip()
        if not inner:
            return []
        items = []
        for part in inner.split(","):
            part = part.strip()
            if not part:
                continue
            if part.startswith(("'", '"')) and part.endswith(("'", '"')):
                items.append(part[1:-1])
            else:
                items.append(part)
        return items
    return [value]


def load_revisions() -> tuple[list[RevisionMeta], list[str]]:
    errors: list[str] = []
    revisions: list[RevisionMeta] = []
    for file in sorted(VERSIONS_DIR.glob("*.py")):
        if file.name == "__init__.py":
            continue
        text = file.read_text(encoding="utf-8")
        rev_match = REVISION_RE.search(text)
        down_match = DOWN_REVISION_RE.search(text)
        if not rev_match:
            errors.append(f"{file.name}: missing 'revision'")
            continue
        if not down_match:
            errors.append(f"{file.name}: missing 'down_revision'")
            continue
        revision = rev_match.group(1).strip()
        down_revisions = _parse_down_revision(down_match.group(1))
        revisions.append(RevisionMeta(file=file, revision=revision, down_revisions=down_revisions))
    return revisions, errors


def check_graph(revisions: list[RevisionMeta]) -> list[str]:
    errors: list[str] = []
    rev_map = {r.revision: r for r in revisions}

    for r in revisions:
        for parent in r.down_revisions:
            if parent and parent not in rev_map:
                errors.append(f"{r.file.name}: down_revision '{parent}' not found")

    child_count: dict[str, int] = {r.revision: 0 for r in revisions}
    for r in revisions:
        for parent in r.down_revisions:
            if parent in child_count:
                child_count[parent] += 1

    heads = [rev for rev, count in child_count.items() if count == 0]
    if len(heads) != 1:
        errors.append(f"expected 1 head, found {len(heads)} heads: {sorted(heads)}")

    base_candidates = [r.revision for r in revisions if not r.down_revisions]
    if len(base_candidates) != 1:
        errors.append(f"expected 1 base revision, found {len(base_candidates)}: {sorted(base_candidates)}")
        return errors

    # Connectivity from head to base (or from base forward by parents).
    head = heads[0] if heads else None
    if not head:
        return errors

    visited: set[str] = set()
    stack = [head]
    while stack:
        current = stack.pop()
        if current in visited:
            continue
        visited.add(current)
        meta = rev_map.get(current)
        if not meta:
            continue
        stack.extend([parent for parent in meta.down_revisions if parent])

    unreachable = sorted(set(rev_map.keys()) - visited)
    if unreachable:
        errors.append(f"disconnected revisions not reachable from head: {unreachable}")

    return errors


def check_schema_coverage(revisions: list[RevisionMeta]) -> list[str]:
    errors: list[str] = []
    schema_text = SCHEMA_FILE.read_text(encoding="utf-8")
    schema_tables = {name.lower() for name in CREATE_TABLE_RE.findall(schema_text)}

    created_tables: set[str] = set()
    for rev in revisions:
        text = rev.file.read_text(encoding="utf-8")
        for table in CREATE_TABLE_RE.findall(text):
            created_tables.add(table.lower())

    missing = sorted(created_tables - schema_tables)
    if missing:
        errors.append(
            "tables created in migrations but missing from db/schema.sql: "
            + ", ".join(missing)
        )
    return errors


def main() -> int:
    revisions, errors = load_revisions()
    errors.extend(check_graph(revisions))
    errors.extend(check_schema_coverage(revisions))

    if errors:
        print("Migration health check: FAILED")
        for err in errors:
            print(f"- {err}")
        return 1

    print("Migration health check: OK")
    print(f"- revisions: {len(revisions)}")
    print(f"- versions dir: {VERSIONS_DIR}")
    print(f"- schema file: {SCHEMA_FILE}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
