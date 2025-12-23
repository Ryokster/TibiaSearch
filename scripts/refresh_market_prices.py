from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Callable, Iterable
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ITEM_IDS_URL = "https://tibia.fandom.com/wiki/Item_IDs"
MARKET_VALUES_URL = "https://api.tibiamarket.top/market_values"
USER_AGENT = "Mozilla/5.0 (compatible; TibiaSearchBot/1.0)"

ROOT_DIR = Path(__file__).resolve().parents[1]
RESOURCE_DIR = ROOT_DIR / "resources" / "tibia"
CACHE_FILE = RESOURCE_DIR / "market_cache.json"
ITEM_IDS_CACHE_FILE = RESOURCE_DIR / "item_ids_cache.json"

CACHE_TTL = timedelta(hours=6)


@dataclass
class HtmlCell:
    text: str


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
            self._current_row.append(HtmlCell(text=text))
            self._cell_text = []


def iso_timestamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def normalize_header(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().lower())


def normalize_name(value: str) -> str:
    cleaned = value.strip().replace("’", "'")
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.lower()


def fetch_html(url: str, log: Callable[[str], None] | None = None) -> str:
    if log:
        log(f"GET {url}")
    request = Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urlopen(request, timeout=30) as response:
            payload = response.read()
    except URLError as exc:
        raise RuntimeError(str(exc)) from exc
    return payload.decode("utf-8", errors="replace")


def parse_tables(html: str) -> list[list[list[HtmlCell]]]:
    parser = TableParser()
    parser.feed(html)
    return parser.tables


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


def fetch_item_ids(log: Callable[[str], None] | None = None) -> dict[str, int]:
    html = fetch_html(ITEM_IDS_URL, log=log)
    tables = parse_tables(html)
    table = find_table(tables, {"item id", "name"})
    if not table:
        table = find_table(tables, {"item id", "item"})
    if not table:
        raise RuntimeError("Item IDs table not found on fandom page")
    headers, rows = table
    name_idx = find_column(headers, ["name", "item"]) or 0
    id_idx = find_column(headers, ["item id", "id"]) or 1

    mapping: dict[str, int] = {}
    for row in rows:
        if name_idx >= len(row) or id_idx >= len(row):
            continue
        name = row[name_idx].text.strip()
        raw_id = row[id_idx].text.strip()
        if not name or not raw_id:
            continue
        match = re.search(r"\d+", raw_id)
        if not match:
            continue
        mapping[normalize_name(name)] = int(match.group(0))
    return mapping


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def load_cache() -> dict | None:
    if not CACHE_FILE.exists():
        return None
    try:
        return json.loads(CACHE_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def load_item_ids_cache() -> dict | None:
    if not ITEM_IDS_CACHE_FILE.exists():
        return None
    try:
        return json.loads(ITEM_IDS_CACHE_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def save_item_ids_cache(mapping: dict[str, int]) -> None:
    payload = {
        "fetched_at": iso_timestamp(),
        "items": mapping,
    }
    ITEM_IDS_CACHE_FILE.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def item_ids_cache_is_fresh(cache: dict) -> bool:
    fetched_at = cache.get("fetched_at")
    if not fetched_at:
        return False
    try:
        timestamp = datetime.fromisoformat(fetched_at.replace("Z", "+00:00"))
    except ValueError:
        return False
    return datetime.now(timezone.utc) - timestamp < CACHE_TTL


def cache_is_fresh(cache: dict, server: str) -> bool:
    if cache.get("server") != server:
        return False
    fetched_at = cache.get("fetched_at")
    if not fetched_at:
        return False
    try:
        timestamp = datetime.fromisoformat(fetched_at.replace("Z", "+00:00"))
    except ValueError:
        return False
    return datetime.now(timezone.utc) - timestamp < CACHE_TTL


def save_cache(server: str, items: dict[int, int]) -> None:
    payload = {
        "server": server,
        "fetched_at": iso_timestamp(),
        "items": {str(key): value for key, value in items.items()},
    }
    CACHE_FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def fetch_market_values(
    server: str,
    item_ids: list[int],
    log: Callable[[str], None] | None = None,
) -> dict[int, int]:
    market_values: dict[int, int] = {}
    for offset in range(0, len(item_ids), 100):
        batch = item_ids[offset : offset + 100]
        params = urlencode(
            {
                "server": server,
                "item_ids": ",".join(str(item_id) for item_id in batch),
                "limit": 100,
            }
        )
        url = f"{MARKET_VALUES_URL}?{params}"
        if log:
            log(f"GET {url}")
        request = Request(url, headers={"User-Agent": USER_AGENT})
        with urlopen(request, timeout=30) as response:
            payload = json.loads(response.read().decode("utf-8"))
        items = payload.get("items") if isinstance(payload, dict) else None
        if items is None and isinstance(payload, list):
            items = payload
        if not items:
            continue
        for entry in items:
            try:
                entry_id = int(entry.get("id"))
            except (TypeError, ValueError):
                continue
            sell_offer = entry.get("sell_offer")
            if sell_offer is None:
                continue
            try:
                market_values[entry_id] = int(sell_offer)
            except (TypeError, ValueError):
                continue
    return market_values


def apply_item_ids(items: list[dict[str, object]], name_to_id: dict[str, int]) -> list[int]:
    item_ids: list[int] = []
    for item in items:
        name = str(item.get("name", ""))
        normalized = normalize_name(name)
        item_id = item.get("id")
        if not isinstance(item_id, int):
            item_id = name_to_id.get(normalized)
            if item_id is not None:
                item["id"] = item_id
        if isinstance(item_id, int):
            item_ids.append(item_id)
    return item_ids


def update_items_with_prices(
    items: list[dict[str, object]],
    name_to_id: dict[str, int],
    market_values: dict[int, int] | None,
) -> tuple[int, int, int]:
    updated = 0
    without_price = 0
    missing_ids = 0
    for item in items:
        name = str(item.get("name", ""))
        normalized = normalize_name(name)
        item_id = item.get("id")
        if not isinstance(item_id, int):
            item_id = name_to_id.get(normalized)
            if item_id is not None:
                item["id"] = item_id
        if not isinstance(item_id, int):
            missing_ids += 1
            if market_values is None:
                continue
            item["gold"] = 0
            without_price += 1
            continue
        if market_values is None:
            continue
        sell_offer = market_values.get(item_id)
        if sell_offer is None or sell_offer == -1:
            item["gold"] = 0
            without_price += 1
        else:
            item["gold"] = int(sell_offer)
        updated += 1
    return updated, without_price, missing_ids


def refresh_market_prices(
    server: str,
    log: Callable[[str], None] | None = None,
) -> dict[str, int | str]:
    if log:
        log(f"Starting market refresh for server {server}")

    creature_path = RESOURCE_DIR / "creature_products.json"
    delivery_path = RESOURCE_DIR / "delivery_task_items.json"

    creature_data = load_json(creature_path)
    delivery_data = load_json(delivery_path)

    name_to_id: dict[str, int] | None = None
    ids_cache = load_item_ids_cache()
    if ids_cache and item_ids_cache_is_fresh(ids_cache):
        cached_items = ids_cache.get("items")
        if isinstance(cached_items, dict):
            name_to_id = {str(key): int(value) for key, value in cached_items.items()}
    if name_to_id is None:
        try:
            name_to_id = fetch_item_ids(log=log)
        except RuntimeError as exc:
            if log:
                log(f"Failed to fetch item ids: {exc}")
            return {"server": server, "error": "item_ids"}
        save_item_ids_cache(name_to_id)
    item_ids: list[int] = []
    item_ids.extend(apply_item_ids(creature_data.get("items", []), name_to_id))
    item_ids.extend(apply_item_ids(delivery_data.get("items", []), name_to_id))
    item_ids = sorted(set(item_ids))

    cache = load_cache()
    market_values: dict[int, int] | None = {}
    if cache and cache_is_fresh(cache, args.server):
        items_cache = cache.get("items", {})
        market_values = {int(key): int(value) for key, value in items_cache.items()}
    else:
        try:
            market_values = fetch_market_values(server, item_ids, log=log)
        except (URLError, RuntimeError, json.JSONDecodeError) as exc:
            if log:
                log(f"Failed to fetch market values: {exc}")
            market_values = None
        else:
            save_cache(server, market_values)

    updated = 0
    without_price = 0
    missing_ids = 0
    updated_count, without_count, missing_count = update_items_with_prices(
        creature_data.get("items", []),
        name_to_id,
        market_values,
    )
    updated += updated_count
    without_price += without_count
    missing_ids += missing_count

    updated_count, without_count, missing_count = update_items_with_prices(
        delivery_data.get("items", []),
        name_to_id,
        market_values,
    )
    updated += updated_count
    without_price += without_count
    missing_ids += missing_count

    save_json(creature_path, creature_data)
    save_json(delivery_path, delivery_data)

    print(
        json.dumps(
            {
                "server": server,
                "timestamp": iso_timestamp(),
                "updated_items": updated,
                "items_without_market_price": without_price,
                "items_missing_ids": missing_ids,
            },
            indent=2,
        )
    )
    if log:
        log(
            "Market refresh done: "
            f"updated={updated}, "
            f"without_price={without_price}, "
            f"missing_ids={missing_ids}"
        )
    return {
        "server": server,
        "updated_items": updated,
        "items_without_market_price": without_price,
        "items_missing_ids": missing_ids,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Refresh market prices for tibia items.")
    parser.add_argument("--server", default="Antica", help="Tibia server name for market prices.")
    args = parser.parse_args()

    refresh_market_prices(args.server)


if __name__ == "__main__":
    main()
