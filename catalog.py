from __future__ import annotations

import base64
import json
import mimetypes
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


SUPPORTED_IMAGE_TYPES = {
    ".gif": "image/gif",
    ".jpeg": "image/jpeg",
    ".jpg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
}
MAX_IMAGE_BYTES = 8 * 1024 * 1024
SAFE_ID = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")


class StickerCatalogError(ValueError):
    """Raised when the sticker catalog or a sticker request is invalid."""


@dataclass(frozen=True)
class Sticker:
    id: str
    file: str
    title: str
    description: str
    tags: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "tags": list(self.tags),
        }


class StickerCatalog:
    def __init__(
        self,
        manifest_path: str | Path | None = None,
        stickers_dir: str | Path | None = None,
    ) -> None:
        project_dir = Path(__file__).resolve().parent
        self.manifest_path = Path(manifest_path or project_dir / "stickers.json").resolve()
        self.stickers_dir = Path(stickers_dir or project_dir / "stickers").resolve()
        self._stickers = self._load_manifest()
        self._by_id = {sticker.id: sticker for sticker in self._stickers}

    def _load_manifest(self) -> tuple[Sticker, ...]:
        try:
            payload = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise StickerCatalogError(f"找不到目录文件：{self.manifest_path}") from exc
        except json.JSONDecodeError as exc:
            raise StickerCatalogError(f"目录 JSON 格式有误：{exc}") from exc

        rows = payload.get("stickers") if isinstance(payload, dict) else None
        if not isinstance(rows, list):
            raise StickerCatalogError("stickers.json 必须包含 stickers 数组。")

        seen_ids: set[str] = set()
        seen_files: set[str] = set()
        stickers: list[Sticker] = []
        for index, row in enumerate(rows):
            if not isinstance(row, dict):
                raise StickerCatalogError(f"第 {index + 1} 条表情包记录不是对象。")

            sticker_id = self._required_text(row, "id", index)
            filename = self._required_text(row, "file", index)
            title = self._required_text(row, "title", index)
            description = self._required_text(row, "description", index)
            tags = row.get("tags")

            if not SAFE_ID.fullmatch(sticker_id):
                raise StickerCatalogError(
                    f"表情包 id {sticker_id!r} 不安全；请只用小写字母、数字、-、_。"
                )
            if sticker_id in seen_ids:
                raise StickerCatalogError(f"重复的表情包 id：{sticker_id}")
            if Path(filename).name != filename:
                raise StickerCatalogError(f"文件名不能包含目录：{filename}")
            if filename in seen_files:
                raise StickerCatalogError(f"重复的表情包文件：{filename}")
            if Path(filename).suffix.lower() not in SUPPORTED_IMAGE_TYPES:
                raise StickerCatalogError(f"不支持的图片格式：{filename}")
            if not isinstance(tags, list) or not tags or not all(
                isinstance(tag, str) and tag.strip() for tag in tags
            ):
                raise StickerCatalogError(f"表情包 {sticker_id} 至少需要一个文字标签。")

            sticker = Sticker(
                id=sticker_id,
                file=filename,
                title=title,
                description=description,
                tags=tuple(tag.strip() for tag in tags),
            )
            self._validate_image(sticker)
            seen_ids.add(sticker_id)
            seen_files.add(filename)
            stickers.append(sticker)

        return tuple(stickers)

    @staticmethod
    def _required_text(row: dict[str, Any], key: str, index: int) -> str:
        value = row.get(key)
        if not isinstance(value, str) or not value.strip():
            raise StickerCatalogError(f"第 {index + 1} 条记录缺少文字字段 {key}。")
        return value.strip()

    def _safe_image_path(self, sticker: Sticker) -> Path:
        path = (self.stickers_dir / sticker.file).resolve()
        if path.parent != self.stickers_dir:
            raise StickerCatalogError(f"表情包路径越界：{sticker.file}")
        return path

    def _validate_image(self, sticker: Sticker) -> None:
        path = self._safe_image_path(sticker)
        if not path.is_file():
            raise StickerCatalogError(f"找不到表情包图片：{sticker.file}")
        if path.stat().st_size > MAX_IMAGE_BYTES:
            raise StickerCatalogError(
                f"表情包 {sticker.file} 超过 {MAX_IMAGE_BYTES // 1024 // 1024} MiB。"
            )

    @property
    def count(self) -> int:
        return len(self._stickers)

    def search(self, query: str = "", limit: int = 20) -> list[Sticker]:
        if not isinstance(query, str):
            raise StickerCatalogError("query 必须是文字。")
        if len(query) > 200:
            raise StickerCatalogError("query 最多 200 个字符。")
        if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 100:
            raise StickerCatalogError("limit 必须是 1 到 100 的整数。")

        needle = self._normalize(query)
        if not needle:
            return list(self._stickers[:limit])

        terms = [term for term in re.split(r"[^\w\u3400-\u9fff]+", needle) if term]
        ranked: list[tuple[int, int, Sticker]] = []
        for position, sticker in enumerate(self._stickers):
            title = self._normalize(sticker.title)
            description = self._normalize(sticker.description)
            tags = [self._normalize(tag) for tag in sticker.tags]
            searchable = " ".join((sticker.id, title, description, *tags))

            score = 0
            if needle == title or needle in tags:
                score += 100
            if needle in searchable:
                score += 50
            for term in terms:
                if term == title or term in tags:
                    score += 25
                elif term in searchable:
                    score += 10

            if score:
                ranked.append((score, -position, sticker))

        ranked.sort(reverse=True, key=lambda item: (item[0], item[1]))
        return [item[2] for item in ranked[:limit]]

    @staticmethod
    def _normalize(value: str) -> str:
        return " ".join(value.casefold().strip().split())

    def get(self, sticker_id: str) -> Sticker:
        if not isinstance(sticker_id, str) or not SAFE_ID.fullmatch(sticker_id):
            raise StickerCatalogError("sticker_id 格式无效。")
        try:
            return self._by_id[sticker_id]
        except KeyError as exc:
            raise StickerCatalogError(f"没有这个表情包：{sticker_id}") from exc

    def image_path(self, sticker_id: str) -> Path:
        sticker = self.get(sticker_id)
        path = self._safe_image_path(sticker)
        self._validate_image(sticker)
        return path

    def mime_type(self, sticker_id: str) -> str:
        path = self.image_path(sticker_id)
        return SUPPORTED_IMAGE_TYPES.get(
            path.suffix.lower(), mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        )

    def image_content(self, sticker_id: str) -> dict[str, str]:
        """Return an MCP-compatible image content block."""
        path = self.image_path(sticker_id)
        return {
            "type": "image",
            "data": base64.b64encode(path.read_bytes()).decode("ascii"),
            "mimeType": self.mime_type(sticker_id),
        }


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="检查并搜索表情包目录。")
    parser.add_argument("query", nargs="?", default="", help="心情、动作、角色或物品")
    parser.add_argument("--limit", type=int, default=20)
    args = parser.parse_args()

    catalog = StickerCatalog()
    results = catalog.search(args.query, args.limit)
    print(json.dumps({"count": len(results), "stickers": [s.as_dict() for s in results]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
