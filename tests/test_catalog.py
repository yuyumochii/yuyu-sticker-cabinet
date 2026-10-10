from __future__ import annotations

import base64
import json
import tempfile
import unittest
from pathlib import Path

from catalog import StickerCatalog, StickerCatalogError


class StickerCatalogTests(unittest.TestCase):
    def setUp(self) -> None:
        self.catalog = StickerCatalog()

    def test_loads_three_stickers(self) -> None:
        self.assertEqual(self.catalog.count, 3)

    def test_searches_by_chinese_mood(self) -> None:
        self.assertEqual(self.catalog.search("融化")[0].id, "turtle-melting")
        self.assertEqual(self.catalog.search("读书")[0].id, "cat-on-book")

    def test_builds_valid_mcp_image_content(self) -> None:
        content = self.catalog.image_content("turtle-plate")
        self.assertEqual(content["type"], "image")
        self.assertEqual(content["mimeType"], "image/png")
        self.assertTrue(base64.b64decode(content["data"]).startswith(b"\x89PNG\r\n\x1a\n"))

    def test_rejects_unknown_id(self) -> None:
        with self.assertRaisesRegex(StickerCatalogError, "没有这个表情包"):
            self.catalog.image_path("not-here")

    def test_rejects_path_traversal_in_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "stickers").mkdir()
            manifest = {
                "stickers": [
                    {
                        "id": "bad-path",
                        "file": "../secret.png",
                        "title": "坏路径",
                        "description": "测试",
                        "tags": ["测试"],
                    }
                ]
            }
            manifest_path = root / "stickers.json"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            with self.assertRaisesRegex(StickerCatalogError, "不能包含目录"):
                StickerCatalog(manifest_path, root / "stickers")


if __name__ == "__main__":
    unittest.main()
