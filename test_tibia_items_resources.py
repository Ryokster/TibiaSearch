import json
import unittest
from pathlib import Path


RESOURCE_DIR = Path(__file__).resolve().parent / "resources" / "tibia"
CREATURE_PRODUCTS_PATH = RESOURCE_DIR / "creature_products.json"
DELIVERY_ITEMS_PATH = RESOURCE_DIR / "delivery_task_items.json"
FANDOM_BASE = "https://tibia.fandom.com/wiki/"


class TestCreatureProductsResource(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        with CREATURE_PRODUCTS_PATH.open("r", encoding="utf-8") as handle:
            cls.resource = json.load(handle)

    def test_items_present(self) -> None:
        items = self.resource.get("items", [])
        self.assertTrue(items)

    def test_item_schema(self) -> None:
        for item in self.resource.get("items", []):
            with self.subTest(item=item.get("name")):
                self.assertTrue(item.get("name"))
                self.assertIsInstance(item.get("weight"), (int, float))
                self.assertTrue(item.get("category"))
                providers = item.get("providers")
                self.assertIsInstance(providers, list)
                url = item.get("url", "")
                self.assertTrue(url.startswith(FANDOM_BASE))
                slug = item.get("slug", "")
                self.assertEqual(url[len(FANDOM_BASE):], slug)

    def test_known_items(self) -> None:
        items_by_name = {item["name"]: item for item in self.resource.get("items", [])}
        for expected in ["Demon Horn", "Rope Belt", "Vampire Teeth"]:
            with self.subTest(expected=expected):
                self.assertIn(expected, items_by_name)


class TestDeliveryItemsResource(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        with DELIVERY_ITEMS_PATH.open("r", encoding="utf-8") as handle:
            cls.resource = json.load(handle)

    def test_items_present(self) -> None:
        items = self.resource.get("items", [])
        self.assertTrue(items)

    def test_item_schema(self) -> None:
        for item in self.resource.get("items", []):
            with self.subTest(item=item.get("name")):
                self.assertTrue(item.get("name"))
                self.assertIsInstance(item.get("weight"), (int, float))
                self.assertTrue(item.get("category"))
                providers = item.get("providers")
                self.assertIsInstance(providers, list)

    def test_known_items(self) -> None:
        items_by_name = {item["name"]: item for item in self.resource.get("items", [])}
        for expected in ["Parcel", "Letter", "Present Box"]:
            with self.subTest(expected=expected):
                self.assertIn(expected, items_by_name)


if __name__ == "__main__":
    unittest.main()
