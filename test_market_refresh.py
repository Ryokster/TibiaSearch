import json
import threading
import time
from pathlib import Path
from typing import Any
from unittest import TestCase
from unittest.mock import patch

import scripts.refresh_market_prices as rmp


class _MockResponse:
    def __init__(self, payload: Any, headers: dict[str, str] | None = None) -> None:
        self.payload = payload
        self.headers = headers or {}

    def read(self) -> bytes:
        return json.dumps(self.payload).encode("utf-8")

    def __enter__(self) -> "_MockResponse":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:  # noqa: ANN001
        return None


class MarketRefreshTests(TestCase):
    def setUp(self) -> None:
        self.temp_dir = Path(self._tmpdir())
        tibia_dir = self.temp_dir / "resources" / "tibia"
        tibia_dir.mkdir(parents=True, exist_ok=True)

        self.creature_path = tibia_dir / "creature_products.json"
        self.delivery_path = tibia_dir / "delivery_task_items.json"
        base_payload = {
            "items": [
                {"name": "Foo", "id": 1, "gold": 0},
                {"name": "Bar", "id": 2, "gold": 0},
            ]
        }
        self.creature_path.write_text(json.dumps(base_payload), encoding="utf-8")
        self.delivery_path.write_text(json.dumps(base_payload), encoding="utf-8")

        self.meta_file = tibia_dir / "market_refresh_meta.json"
        self.cache_file = tibia_dir / "market_cache.json"
        self.ids_cache_file = tibia_dir / "item_ids_cache.json"
        self.ids_cache_file.write_text(
            json.dumps({"fetched_at": rmp.iso_timestamp(), "items": {}}),
            encoding="utf-8",
        )

        self._original_paths = (
            rmp.RESOURCE_DIR,
            rmp.CACHE_FILE,
            rmp.ITEM_IDS_CACHE_FILE,
        )
        rmp.RESOURCE_DIR = tibia_dir
        rmp.CACHE_FILE = self.cache_file
        rmp.ITEM_IDS_CACHE_FILE = self.ids_cache_file

        self.addCleanup(self._restore_paths)

    def _tmpdir(self) -> str:
        import tempfile

        return tempfile.mkdtemp(prefix="market-refresh-")

    def _restore_paths(self) -> None:
        rmp.RESOURCE_DIR, rmp.CACHE_FILE, rmp.ITEM_IDS_CACHE_FILE = self._original_paths  # type: ignore[misc]

    def test_skips_when_world_data_unchanged(self) -> None:
        self.meta_file.write_text(
            json.dumps(
                {
                    "market_last_update_by_server": {"Antica": "2024-01-01T00:00:00Z"},
                    "market_last_refresh_at_by_server": {},
                }
            ),
            encoding="utf-8",
        )

        responses = [
            _MockResponse({"servers": {"Antica": {"last_update": "2024-01-01T00:00:00Z"}}}),
        ]

        with patch("scripts.refresh_market_prices.urlopen", side_effect=responses) as mock_urlopen:
            refresher = rmp.MarketRefresher(resource_dir=rmp.RESOURCE_DIR, log=None, throttle_seconds=0.0)
            result = refresher.refresh_server("Antica")

        self.assertTrue(result.get("skipped"))
        self.assertEqual(mock_urlopen.call_count, 1)

    def test_handles_retry_after_and_marks_throttle(self) -> None:
        world_response = _MockResponse({"servers": {"Antica": {"last_update": "2024-02-01T00:00:00Z"}}})
        market_success = _MockResponse([{"id": 1, "sell_offer": 10}, {"id": 2, "sell_offer": -1}])
        retry_error = rmp.HTTPError(
            url="http://example",
            code=429,
            msg="Too Many Requests",
            hdrs={"Retry-After": "2"},
            fp=None,
        )
        responses: list[Any] = [world_response, retry_error, market_success]
        sleeps: list[float] = []

        def fake_sleep(seconds: float) -> None:
            sleeps.append(seconds)

        with (
            patch("scripts.refresh_market_prices.urlopen", side_effect=responses),
            patch("scripts.refresh_market_prices.time.sleep", side_effect=fake_sleep),
            patch("scripts.refresh_market_prices.random.uniform", return_value=0.2),
        ):
            refresher = rmp.MarketRefresher(resource_dir=rmp.RESOURCE_DIR, log=None, throttle_seconds=0.0)
            result = refresher.refresh_server("Antica")

        self.assertEqual(result.get("updated_items"), 4)  # two lists * two items
        self.assertIn(2.2, sleeps)  # 2s retry-after + 0.2 jitter

    def test_single_flight_blocks_parallel_refreshes(self) -> None:
        world_response = _MockResponse({"servers": {"Antica": {"last_update": "2024-03-01T00:00:00Z"}}})
        market_success = _MockResponse([{"id": 1, "sell_offer": 10}, {"id": 2, "sell_offer": 5}])
        responses: list[Any] = [world_response, market_success]

        with patch("scripts.refresh_market_prices.urlopen", side_effect=responses * 2):
            refresher = rmp.MarketRefresher(resource_dir=rmp.RESOURCE_DIR, log=None, throttle_seconds=0.0)
            results: list[dict] = []

            def run_refresh() -> None:
                results.append(refresher.refresh_server("Antica"))

            t1 = threading.Thread(target=run_refresh)
            t2 = threading.Thread(target=run_refresh)
            t1.start()
            t2.start()
            t1.join()
            t2.join()

        self.assertEqual(len(results), 2)
        self.assertEqual(results[0].get("updated_items"), 4)
        self.assertEqual(results[1].get("status", "ok"), "joined")
