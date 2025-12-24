from __future__ import annotations

import argparse
import html
import json
import random
import re
import threading
import time
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Callable, Iterable
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

MARKET_VALUES_URL = "https://api.tibiamarket.top/market_values"
WORLD_DATA_URL = "https://api.tibiamarket.top/world_data"
USER_AGENT = "Mozilla/5.0 (compatible; TibiaSearchBot/1.0)"

ROOT_DIR = Path(__file__).resolve().parents[1]
RESOURCE_DIR = ROOT_DIR / "resources" / "tibia"
CACHE_FILE = RESOURCE_DIR / "market_cache.json"
ITEM_IDS_CACHE_FILE = RESOURCE_DIR / "item_ids_cache.json"
ITEM_IDS_DUMP_PATH = ROOT_DIR / "https___tibia.fandom.com_wiki_Item_IDs.htm"
MARKET_REFRESH_META_FILE = RESOURCE_DIR / "market_refresh_meta.json"

CACHE_TTL = timedelta(hours=6)
THROTTLE_SECONDS = 1.0
RETRY_JITTER_RANGE = (0.1, 0.3)
BACKOFF_NO_RETRY_AFTER = [
    (2.0, 5.0),
    (5.0, 12.0),
    (10.0, 25.0),
]
SERVER_ERROR_BACKOFF = (1.0, 3.0)
BATCH_DELAY_SECONDS = 1.0


class Throttle:
    def __init__(self, delay_seconds: float) -> None:
        self.delay_seconds = delay_seconds
        self._last_request_at: float | None = None

    def required_delay(self) -> float:
        if self._last_request_at is None:
            return 0.0
        elapsed = time.monotonic() - self._last_request_at
        return max(0.0, self.delay_seconds - elapsed)

    def wait(self, log: Callable[[str], None] | None = None) -> None:
        delay = self.required_delay()
        if delay > 0:
            if log:
                log(f"Throttle active; waiting {delay:.2f}s before next request")
            time.sleep(delay)

    def mark(self) -> None:
        self._last_request_at = time.monotonic()


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


def load_market_refresh_meta(path: Path = MARKET_REFRESH_META_FILE) -> dict[str, dict[str, str]]:
    if not path.exists():
        return {
            "market_last_update_by_server": {},
            "market_last_refresh_at_by_server": {},
        }
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {
            "market_last_update_by_server": {},
            "market_last_refresh_at_by_server": {},
        }
    return {
        "market_last_update_by_server": payload.get("market_last_update_by_server", {}),
        "market_last_refresh_at_by_server": payload.get("market_last_refresh_at_by_server", {}),
    }


def save_market_refresh_meta(data: dict[str, dict[str, str]], path: Path = MARKET_REFRESH_META_FILE) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def strip_highlight_wrappers(raw_html: str) -> str:
    """Remove view-source highlighting wrappers and unescape HTML entities."""

    without_spans = re.sub(r"</?(?:span|a)[^>]*>", "", raw_html)
    return html.unescape(without_spans)


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
    del log  # no-op to align with existing signature
    if not ITEM_IDS_DUMP_PATH.exists():
        raise RuntimeError(f"Item IDs dump not found: {ITEM_IDS_DUMP_PATH}")
    raw_html = ITEM_IDS_DUMP_PATH.read_text(encoding="utf-8")
    decoded_html = strip_highlight_wrappers(raw_html)
    tables = parse_tables(decoded_html)
    table = find_table(tables, {"item", "id"})
    if not table:
        raise RuntimeError("Item IDs table not found in saved dump")
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


def _decode_json_response(response) -> object:
    return json.loads(response.read().decode("utf-8"))


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
    processed_ids: set[int] | None = None,
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
        if processed_ids is not None and item_id not in processed_ids:
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

    refresher = MarketRefresher(resource_dir=RESOURCE_DIR, log=log)
    return refresher.refresh_server(server)


class MarketRefresher:
    def __init__(
        self,
        resource_dir: Path,
        log: Callable[[str], None] | None = None,
        throttle_seconds: float = THROTTLE_SECONDS,
        market_values_url: str = MARKET_VALUES_URL,
        world_data_url: str = WORLD_DATA_URL,
    ) -> None:
        self.resource_dir = resource_dir
        self.log = log
        self.market_values_url = market_values_url
        self.world_data_url = world_data_url
        self.throttle_seconds = throttle_seconds
        self.meta_file = self.resource_dir / "market_refresh_meta.json"
        self._flights: dict[str, _ServerFlight] = defaultdict(_ServerFlight)
        self._flights_lock = threading.Lock()
        self._throttle = Throttle(delay_seconds=throttle_seconds)

    def _log(self, message: str) -> None:
        if self.log:
            self.log(message)

    def refresh_server(self, server: str) -> dict[str, int | str]:
        with self._flights_lock:
            flight = self._flights[server]
        with flight.lock:
            if flight.in_progress:
                self._log(f"Refresh already in progress for {server}; joining existing run")
                flight.waiters += 1
                while flight.in_progress:
                    flight.condition.wait()
                flight.waiters -= 1
                result = dict(flight.last_result or {})
                result.setdefault("server", server)
                result.setdefault("status", "joined")
                return result
            flight.in_progress = True

        start = time.monotonic()
        result: dict[str, int | str] | None = None
        try:
            result = self._refresh_server_impl(server)
            return result
        finally:
            duration = time.monotonic() - start
            with flight.lock:
                flight.in_progress = False
                flight.last_result = {
                    "server": server,
                    "duration_seconds": duration,
                    **(result or {}),
                }
                flight.condition.notify_all()

    def _refresh_server_impl(self, server: str) -> dict[str, int | str]:
        meta = load_market_refresh_meta(self.meta_file)
        world_data = self._fetch_world_data(server)
        last_update_remote = self._extract_last_update(world_data, server)
        last_update_local = meta["market_last_update_by_server"].get(server)

        if last_update_remote and last_update_local == last_update_remote:
            self._log(f"No new scan for {server}, skipping refresh")
            meta["market_last_refresh_at_by_server"][server] = iso_timestamp()
            save_market_refresh_meta(meta, self.meta_file)
            return {
                "server": server,
                "updated_items": 0,
                "items_without_market_price": 0,
                "items_missing_ids": 0,
                "skipped": True,
            }

        creature_path = self.resource_dir / "creature_products.json"
        delivery_path = self.resource_dir / "delivery_task_items.json"

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
                name_to_id = fetch_item_ids(log=self.log)
            except RuntimeError as exc:
                self._log(f"Failed to fetch item ids: {exc}")
                return {"server": server, "error": "item_ids"}
            save_item_ids_cache(name_to_id)
        aliases = build_alias_mapping(name_to_id)
        name_to_id = {**name_to_id, **aliases}

        item_ids: list[int] = []
        item_ids.extend(apply_item_ids(creature_data.get("items", []), name_to_id))
        item_ids.extend(apply_item_ids(delivery_data.get("items", []), name_to_id))
        item_ids = sorted(set(item_ids))

        market_values: dict[int, int] = {}
        processed_ids: set[int] = set()
        failed_batches = 0
        total_batches = 0

        for batch_start in range(0, len(item_ids), 100):
            batch = item_ids[batch_start : batch_start + 100]
            if total_batches > 0:
                self._throttle.wait(log=self.log)
            total_batches += 1
            batch_values = self._fetch_market_batch(server, batch)
            if batch_values is None:
                failed_batches += 1
                self._log(f"Failed to fetch batch starting at offset {batch_start} for {server}; skipping updates for this batch")
                continue
            market_values.update(batch_values)
            processed_ids.update(batch)
            if BATCH_DELAY_SECONDS > 0 and batch_start + 100 < len(item_ids):
                self._log(f"Batch processed, sleeping {BATCH_DELAY_SECONDS:.2f}s before next batch")
                time.sleep(BATCH_DELAY_SECONDS)

        updated = 0
        without_price = 0
        missing_ids = 0

        if processed_ids:
            updated_count, without_count, missing_count = update_items_with_prices(
                creature_data.get("items", []),
                name_to_id,
                market_values,
                processed_ids=processed_ids,
            )
            updated += updated_count
            without_price += without_count
            missing_ids += missing_count

            updated_count, without_count, missing_count = update_items_with_prices(
                delivery_data.get("items", []),
                name_to_id,
                market_values,
                processed_ids=processed_ids,
            )
            updated += updated_count
            without_price += without_count
            missing_ids += missing_count

            save_json(creature_path, creature_data)
            save_json(delivery_path, delivery_data)

        if last_update_remote:
            meta["market_last_update_by_server"][server] = last_update_remote
        meta["market_last_refresh_at_by_server"][server] = iso_timestamp()
        save_market_refresh_meta(meta, self.meta_file)

        summary = {
            "server": server,
            "updated_items": updated,
            "items_without_market_price": without_price,
            "items_missing_ids": missing_ids,
            "batches": total_batches,
            "failed_batches": failed_batches,
        }

        self._log(
            "Market refresh done: "
            f"updated={updated}, "
            f"without_price={without_price}, "
            f"missing_ids={missing_ids}, "
            f"batches={total_batches}, "
            f"failed_batches={failed_batches}"
        )
        return summary

    def _fetch_world_data(self, server: str) -> dict:
        params = urlencode({"servers": server})
        url = f"{self.world_data_url}?{params}"
        self._log(f"GET {url}")
        request = Request(url, headers={"User-Agent": USER_AGENT})
        with urlopen(request, timeout=30) as response:
            payload = _decode_json_response(response)
        if not isinstance(payload, dict):
            return {}
        return payload

    def _extract_last_update(self, world_data: dict, server: str) -> str | None:
        servers = world_data.get("servers")
        if isinstance(servers, dict):
            server_entry = servers.get(server)
            if isinstance(server_entry, dict):
                last_update = server_entry.get("last_update")
                if isinstance(last_update, str):
                    return last_update
        return None

    def _fetch_market_batch(self, server: str, batch: list[int]) -> dict[int, int] | None:
        params = urlencode(
            {
                "server": server,
                "item_ids": ",".join(str(item_id) for item_id in batch),
                "limit": 100,
            }
        )
        url = f"{self.market_values_url}?{params}"
        max_attempts = 3

        for attempt in range(1, max_attempts + 1):
            self._throttle.wait(log=self.log)
            self._log(f"GET {url} (attempt {attempt}/{max_attempts})")
            request = Request(url, headers={"User-Agent": USER_AGENT})
            try:
                with urlopen(request, timeout=30) as response:
                    payload = _decode_json_response(response)
                self._throttle.mark()
                return self._parse_market_values(payload)
            except HTTPError as exc:
                self._throttle.mark()
                if exc.code == 429:
                    wait_seconds = self._compute_retry_after(exc, attempt)
                    if attempt == max_attempts:
                        self._log(f"HTTP 429 on final attempt for {server} batch {batch[0]}-{batch[-1]}, giving up")
                        return None
                    self._log(f"HTTP 429 received; waiting {wait_seconds:.2f}s before retrying")
                    time.sleep(wait_seconds)
                    continue
                if 500 <= exc.code < 600:
                    if attempt == max_attempts:
                        self._log(f"Server error {exc.code} on final attempt for {server} batch {batch[0]}-{batch[-1]}, giving up")
                        return None
                    wait_seconds = random.uniform(*SERVER_ERROR_BACKOFF)
                    wait_seconds = max(wait_seconds, self._throttle.required_delay())
                    self._log(f"Server error {exc.code}; retrying in {wait_seconds:.2f}s")
                    time.sleep(wait_seconds)
                    continue
                self._log(f"HTTP error {exc.code} for {server} batch {batch[0]}-{batch[-1]}: {exc}; not retrying")
                return None
            except (URLError, json.JSONDecodeError) as exc:
                self._throttle.mark()
                if attempt == max_attempts:
                    self._log(f"Request failed on attempt {attempt} for {server} batch {batch[0]}-{batch[-1]}: {exc}")
                    return None
                wait_seconds = max(random.uniform(*SERVER_ERROR_BACKOFF), self._throttle.required_delay())
                self._log(f"Request error: {exc}; retrying in {wait_seconds:.2f}s")
                time.sleep(wait_seconds)
        return None

    def _compute_retry_after(self, exc: HTTPError, attempt: int) -> float:
        retry_after = exc.headers.get("Retry-After") if exc.headers else None
        base_delay: float
        if retry_after:
            try:
                base_delay = float(retry_after)
            except (TypeError, ValueError):
                base_delay = 0.0
            base_delay += random.uniform(*RETRY_JITTER_RANGE)
        else:
            index = min(attempt - 1, len(BACKOFF_NO_RETRY_AFTER) - 1)
            base_delay = random.uniform(*BACKOFF_NO_RETRY_AFTER[index])
        throttle_delay = self._throttle.required_delay()
        return max(base_delay, throttle_delay)

    def _parse_market_values(self, payload: object) -> dict[int, int]:
        items = payload.get("items") if isinstance(payload, dict) else None
        if items is None and isinstance(payload, list):
            items = payload
        if not items:
            return {}
        market_values: dict[int, int] = {}
        for entry in items:
            if not isinstance(entry, dict):
                continue
            try:
                entry_id = int(entry.get("id"))
            except (TypeError, ValueError):
                continue
            sell_offer = entry.get("sell_offer")
            if sell_offer is None:
                market_values[entry_id] = 0
                continue
            try:
                sell_value = int(sell_offer)
            except (TypeError, ValueError):
                market_values[entry_id] = 0
                continue
            market_values[entry_id] = 0 if sell_value == -1 else max(0, sell_value)
        return market_values


class _ServerFlight:
    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.condition = threading.Condition(self.lock)
        self.in_progress = False
        self.waiters = 0
        self.last_result: dict[str, int | str] | None = None


def main() -> None:
    parser = argparse.ArgumentParser(description="Refresh market prices for tibia items.")
    parser.add_argument("--server", default="Xyla", help="Tibia server name for market prices.")
    parser.add_argument(
        "--allow-partial-refresh",
        action="store_true",
        help="Continue even if some batches fail (default: false).",
    )
    parser.add_argument(
        "--delay-between-batches",
        type=float,
        default=DELAY_BETWEEN_BATCHES_SECONDS,
        help="Seconds to wait between batch requests (default: 12).",
    )
    args = parser.parse_args()

    refresher = MarketRefresher(
        resource_dir=RESOURCE_DIR,
        log=print,
        delay_between_batches_seconds=args.delay_between_batches,
        throttle_seconds=args.delay_between_batches,
        allow_partial_refresh=args.allow_partial_refresh,
    )
    refresher.refresh_server(args.server)


if __name__ == "__main__":
    main()
