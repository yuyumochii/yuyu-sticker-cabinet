from __future__ import annotations

import unittest

import anyio
import httpx2
from mcp import Client
from mcp_types import ImageContent, TextContent

from server import STICKER_WIDGET_URI, build_server


class StickerServerTests(unittest.TestCase):
    def test_show_sticker_exposes_image_and_ui_card(self) -> None:
        anyio.run(self._check_show_sticker)

    @staticmethod
    async def _check_show_sticker() -> None:
        server = build_server()
        async with Client(server) as client:
            tools = {tool.name: tool for tool in (await client.list_tools()).tools}
            show = tools["show_sticker"]

            assert show.output_schema is not None
            assert show.meta is not None
            assert show.meta["ui"]["resourceUri"] == STICKER_WIDGET_URI
            assert show.meta["openai/outputTemplate"] == STICKER_WIDGET_URI

            result = await client.call_tool(
                "show_sticker", {"sticker_id": "turtle-plate"}
            )
            assert result.is_error is False
            assert result.structured_content is not None
            assert result.structured_content["image_url"].endswith(
                "/stickers/turtle-plate"
            )
            assert any(isinstance(item, ImageContent) for item in result.content)
            assert any(isinstance(item, TextContent) for item in result.content)

            resource = await client.read_resource(STICKER_WIDGET_URI)
            assert resource.contents[0].mime_type == "text/html;profile=mcp-app"
            assert "ui/notifications/tool-result" in resource.contents[0].text

    def test_public_sticker_route_serves_original_image(self) -> None:
        anyio.run(self._check_public_sticker_route)

    @staticmethod
    async def _check_public_sticker_route() -> None:
        server = build_server()
        transport = httpx2.ASGITransport(app=server.streamable_http_app())
        async with httpx2.AsyncClient(
            transport=transport, base_url="http://127.0.0.1"
        ) as client:
            response = await client.get("/stickers/turtle-plate")
            missing = await client.get("/stickers/not-here")

        assert response.status_code == 200
        assert response.headers["content-type"].startswith("image/png")
        assert response.content.startswith(b"\x89PNG\r\n\x1a\n")
        assert missing.status_code == 404


if __name__ == "__main__":
    unittest.main()
