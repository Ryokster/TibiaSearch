from __future__ import annotations

"""Refresh Tibia item resources with a snapshot fallback when scraping is blocked."""

import json
import re
import sys
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Iterable
from urllib.error import URLError
from urllib.parse import urljoin, quote
from urllib.request import Request, urlopen

CREATURE_PRODUCTS_URL = "https://tibia.fandom.com/wiki/Creature_Products"
DELIVERY_TASK_ITEMS_URL = "https://tibiopedia.pl/items/others/delivery"

ROOT_DIR = Path(__file__).resolve().parents[1]
RESOURCE_DIR = ROOT_DIR / "resources" / "tibia"
SNAPSHOT_DIR = RESOURCE_DIR / "snapshots"

USER_AGENT = "Mozilla/5.0 (compatible; TibiaSearchBot/1.0)"


@dataclass
class HtmlCell:
    text: str
    links: tuple[str, ...]


class TableParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.tables: list[list[list[HtmlCell]]] = []
        self._in_table = False
        self._in_row = False
        self._in_cell = False
        self._current_table: list[list[HtmlCell]] = []
        self._current_row: list[HtmlCell] = []
        self._cell_text: list[str] = []
        self._cell_links: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "table":
            self._in_table = True
            self._current_table = []
        if not self._in_table:
            return
        if tag == "tr":
            self._in_row = True
            self._current_row = []
        elif tag in {"td", "th"} and self._in_row:
            self._in_cell = True
            self._cell_text = []
            self._cell_links = []
        elif tag == "a" and self._in_cell:
            for key, value in attrs:
                if key == "href" and value:
                    self._cell_links.append(value)

    def handle_data(self, data: str) -> None:
        if self._in_cell:
            self._cell_text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "table" and self._in_table:
            self._in_table = False
            if self._current_table:
                self.tables.append(self._current_table)
            self._current_table = []
        elif tag == "tr" and self._in_row:
            self._in_row = False
            if self._current_row:
                self._current_table.append(self._current_row)
            self._current_row = []
        elif tag in {"td", "th"} and self._in_cell:
            self._in_cell = False
            text = " ".join(part.strip() for part in self._cell_text if part.strip())
            self._current_row.append(HtmlCell(text=text, links=tuple(self._cell_links)))
            self._cell_text = []
            self._cell_links = []


class FetchError(RuntimeError):
    pass


def iso_timestamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def fetch_html(url: str) -> str:
    request = Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urlopen(request, timeout=30) as response:
            payload = response.read()
    except URLError as exc:
        raise FetchError(str(exc)) from exc
    return payload.decode("utf-8", errors="replace")


def parse_tables(html: str) -> list[list[list[HtmlCell]]]:
    parser = TableParser()
    parser.feed(html)
    return parser.tables


def normalize_header(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().lower())


def slugify(name: str) -> str:
    cleaned = name.replace("’", "'").replace("‘", "'")
    cleaned = unicodedata.normalize("NFKD", cleaned)
    cleaned = cleaned.encode("ascii", "ignore").decode("ascii")
    cleaned = cleaned.replace(" ", "_")
    return quote(cleaned, safe="_")


def clean_item_name(name: str) -> str:
    name = name.strip()
    name = re.sub(r"^item\s+", "", name, flags=re.IGNORECASE)
    return name.strip()


def split_providers(raw: str) -> list[str]:
    if not raw:
        return []
    parts = [part.strip() for part in raw.split(",")]
    return [part for part in parts if part]


def parse_weight(raw: str) -> float:
    if not raw:
        return 0.0
    match = re.search(r"\d+(?:\.\d+)?", raw.replace(",", "."))
    if not match:
        return 0.0
    return float(match.group(0))


def find_table(
    tables: Iterable[list[list[HtmlCell]]],
    required_headers: set[str],
) -> tuple[list[HtmlCell], list[list[HtmlCell]]] | None:
    for table in tables:
        if not table:
            continue
        headers = table[0]
        header_names = {normalize_header(cell.text) for cell in headers}
        if required_headers.issubset(header_names):
            return headers, table[1:]
    return None


def find_column(headers: list[HtmlCell], candidates: Iterable[str]) -> int | None:
    normalized = [normalize_header(cell.text) for cell in headers]
    for idx, name in enumerate(normalized):
        for candidate in candidates:
            if candidate in name:
                return idx
    return None


def parse_creature_products(html: str) -> list[dict[str, object]]:
    tables = parse_tables(html)
    table = find_table(tables, {"item", "weight"})
    if not table:
        raise FetchError("Creature products table not found")
    headers, rows = table
    name_idx = find_column(headers, ["item", "name"]) or 0
    weight_idx = find_column(headers, ["weight"]) or 0
    providers_idx = find_column(headers, ["dropped by", "creature", "creatures", "dropped"])
    category_idx = find_column(headers, ["category", "type"]) or None

    items: list[dict[str, object]] = []
    for row in rows:
        if name_idx >= len(row):
            continue
        name = clean_item_name(row[name_idx].text)
        if not name:
            continue
        weight = parse_weight(row[weight_idx].text if weight_idx < len(row) else "")
        providers_text = row[providers_idx].text if providers_idx is not None and providers_idx < len(row) else ""
        category = row[category_idx].text if category_idx is not None and category_idx < len(row) else "Creature Product"
        slug = slugify(name)
        items.append(
            {
                "name": name,
                "slug": slug,
                "url": f"https://tibia.fandom.com/wiki/{slug}",
                "weight": weight,
                "category": category or "Creature Product",
                "providers": split_providers(providers_text),
            }
        )
    return items


def parse_delivery_items(html: str) -> list[dict[str, object]]:
    tables = parse_tables(html)
    table = find_table(tables, {"item", "weight"})
    if not table:
        raise FetchError("Delivery task items table not found")
    headers, rows = table
    name_idx = find_column(headers, ["item", "name"]) or 0
    weight_idx = find_column(headers, ["weight"]) or 0
    providers_idx = find_column(headers, ["npc", "from", "provider"]) or None
    category_idx = find_column(headers, ["category", "type"]) or None

    items: list[dict[str, object]] = []
    for row in rows:
        if name_idx >= len(row):
            continue
        name_cell = row[name_idx]
        name = clean_item_name(name_cell.text)
        if not name:
            continue
        weight = parse_weight(row[weight_idx].text if weight_idx < len(row) else "")
        providers_text = row[providers_idx].text if providers_idx is not None and providers_idx < len(row) else ""
        category = row[category_idx].text if category_idx is not None and category_idx < len(row) else "Delivery Task Item"
        slug = slugify(name)
        url = ""
        if name_cell.links:
            url = urljoin(DELIVERY_TASK_ITEMS_URL, name_cell.links[0])
        items.append(
            {
                "name": name,
                "slug": slug,
                "url": url,
                "weight": weight,
                "category": category or "Delivery Task Item",
                "providers": split_providers(providers_text),
            }
        )
    return items


def load_snapshot(path: Path, description: str) -> dict[str, object]:
    if not path.exists():
        raise FetchError(f"Missing snapshot for {description}: {path}")
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def write_resource(path: Path, source_name: str, source_url: str, items: list[dict[str, object]]) -> None:
    payload = {
        "version": 1,
        "source": {
            "name": source_name,
            "url": source_url,
            "fetched_at": iso_timestamp(),
        },
        "items": sorted(items, key=lambda item: item["name"].lower()),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def refresh_creature_products() -> None:
    try:
        html = fetch_html(CREATURE_PRODUCTS_URL)
        items = parse_creature_products(html)
    except FetchError:
        snapshot = load_snapshot(SNAPSHOT_DIR / "creature_products.json", "creature products")
        items = snapshot.get("items", [])
    write_resource(
        RESOURCE_DIR / "creature_products.json",
        "TibiaWiki (Creature Products)",
        CREATURE_PRODUCTS_URL,
        items,
    )


def refresh_delivery_items() -> None:
    try:
        html = fetch_html(DELIVERY_TASK_ITEMS_URL)
        items = parse_delivery_items(html)
    except FetchError:
        snapshot = load_snapshot(SNAPSHOT_DIR / "delivery_task_items.json", "delivery task items")
        items = snapshot.get("items", [])
    write_resource(
        RESOURCE_DIR / "delivery_task_items.json",
        "Tibiopedia (Delivery Items)",
        DELIVERY_TASK_ITEMS_URL,
        items,
    )


def main() -> int:
    refresh_creature_products()
    refresh_delivery_items()
    return 0


if __name__ == "__main__":
    sys.exit(main())
