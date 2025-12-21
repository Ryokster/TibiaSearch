import unittest
from urllib.parse import quote

from app import FANDOM_BASE_URL, IMBUEMENTS, fandom_article_url


class TestFandomArticleUrls(unittest.TestCase):
    def test_ingredient_urls(self) -> None:
        materials = {
            material.name
            for imbuement in IMBUEMENTS
            for material in imbuement.materials
        }
        for name in sorted(materials):
            with self.subTest(material=name):
                expected_slug = quote(name.strip().replace(" ", "_"), safe="_")
                expected = f"{FANDOM_BASE_URL}{expected_slug}"
                url = fandom_article_url(name)
                self.assertEqual(url, expected)
                self.assertNotIn("Special:Search", url)
                self.assertNotIn("+", url)


if __name__ == "__main__":
    unittest.main()
