from __future__ import annotations

"""Apply Tibia item IDs from a saved HTML dump to the resource files."""

import argparse
import html
import json
import re
from pathlib import Path
from typing import Iterable

from refresh_market_prices import find_column, normalize_header, normalize_name, parse_tables


ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_HTML_DUMP = ROOT_DIR / "https___tibia.fandom.com_wiki_Item_IDs.htm"
RESOURCE_DIR = ROOT_DIR / "resources" / "tibia"


def strip_highlight_wrappers(raw_html: str) -> str:
    """Remove the view-source highlighting wrappers and unescape HTML entities."""

    without_spans = re.sub(r"</?(?:span|a)[^>]*>", "", raw_html)
    return html.unescape(without_spans)


def find_item_id_table(tables: Iterable[list[list[object]]]) -> tuple[list[object], list[list[object]]]:
    for table in tables:
        if not table:
            continue
        headers = table[0]
        normalized_headers = {normalize_header(cell.text) for cell in headers}
        if {"item", "id"}.issubset(normalized_headers):
            return headers, table[1:]
    raise RuntimeError("Item ID table not found in the provided HTML dump")


def load_item_ids(html_path: Path) -> dict[str, int]:
    raw_html = html_path.read_text(encoding="utf-8")
    decoded_html = strip_highlight_wrappers(raw_html)
    tables = parse_tables(decoded_html)
    headers, rows = find_item_id_table(tables)

    name_idx = find_column(headers, ["name", "item"]) or 0
    id_idx = find_column(headers, ["item id", "id"]) or 1

    mapping: dict[str, int] = {}
    for row in rows:
        if name_idx >= len(row) or id_idx >= len(row):
            continue
        name = row[name_idx].text.strip()
        raw_id = row[id_idx].text.strip()
        match = re.search(r"\d+", raw_id)
        if not name or not match:
            continue
        mapping[normalize_name(name)] = int(match.group(0))
    if not mapping:
        raise RuntimeError("Failed to parse any item IDs from the HTML dump")
    return mapping


def build_alias_mapping(mapping: dict[str, int]) -> dict[str, int]:
    aliases: dict[str, int] = {}
    alias_pairs = {
        "Frozen Claw (Ice Horror)": "Frozen Claw",
        "Darklight Core": "Darklight Core (Object)",
        "Darklight Matter": "Darklight Matter (Object)",
        "Gore Horn": "Gore Horn (Item)",
        "Silencer Claw": "Silencer Claws",
    }
    for target, source in alias_pairs.items():
        source_id = mapping.get(normalize_name(source))
        if source_id is not None:
            aliases[normalize_name(target)] = source_id
    return aliases


def apply_ids_to_items(items: list[dict[str, object]], mapping: dict[str, int], aliases: dict[str, int]) -> int:
    updated = 0
    for item in items:
        normalized = normalize_name(str(item.get("name", "")))
        item_id = mapping.get(normalized) or aliases.get(normalized)
        if item_id is not None:
            if item.get("id") != item_id:
                item["id"] = item_id
                updated += 1
    return updated


def update_resource(path: Path, mapping: dict[str, int], aliases: dict[str, int]) -> int:
    payload = json.loads(path.read_text(encoding="utf-8"))
    items = payload.get("items", [])
    updated = apply_ids_to_items(items, mapping, aliases)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return updated


def main() -> int:
    parser = argparse.ArgumentParser(description="Apply item IDs to Tibia resource files from a saved HTML dump.")
    parser.add_argument(
        "--html",
        dest="html_path",
        default=DEFAULT_HTML_DUMP,
        type=Path,
        help="Path to the saved Item IDs HTML (defaults to the repository dump).",
    )
    parser.add_argument(
        "--include-snapshots",
        action="store_true",
        help="Also update the snapshot resource files with IDs.",
    )
    args = parser.parse_args()

    mapping = load_item_ids(args.html_path)
    aliases = build_alias_mapping(mapping)

    updated_total = 0
    for filename in ("creature_products.json", "delivery_task_items.json"):
        updated_total += update_resource(RESOURCE_DIR / filename, mapping, aliases)

    if args.include_snapshots:
        snapshots = RESOURCE_DIR / "snapshots"
        for filename in ("creature_products.json", "delivery_task_items.json"):
            snapshot_path = snapshots / filename
            if snapshot_path.exists():
                updated_total += update_resource(snapshot_path, mapping, aliases)

    print(f"Updated IDs for {updated_total} items.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
