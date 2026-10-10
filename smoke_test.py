from __future__ import annotations

import base64
import json

from catalog import StickerCatalog


def main() -> None:
    catalog = StickerCatalog()
    matches = catalog.search("累了 融化")
    chosen = matches[0]
    image = catalog.image_content(chosen.id)
    raw = base64.b64decode(image["data"])
    print(
        json.dumps(
            {
                "catalog_count": catalog.count,
                "query": "累了 融化",
                "chosen": chosen.as_dict(),
                "mime_type": image["mimeType"],
                "image_bytes": len(raw),
                "png_signature_ok": raw.startswith(b"\x89PNG\r\n\x1a\n"),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
