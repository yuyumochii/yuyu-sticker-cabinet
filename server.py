from __future__ import annotations

import os
from typing import Annotated, Any, TypedDict

from mcp.server.mcpserver import Image, MCPServer
from mcp_types import ToolAnnotations
from pydantic import Field

from catalog import StickerCatalog, StickerCatalogError


SERVER_INSTRUCTIONS = (
    "这是 yuyu 的私人表情包柜。表情包确实贴合当前语境时，可以自然地主动挑一张，"
    "不必等用户点名；但要克制，不要每句话都发。未知准确 id 时先调用 list_stickers，"
    "选定后再调用 show_sticker。只有 show_sticker 成功后，才可以说已经发出了图片。"
)


class StickerResult(TypedDict):
    id: str
    title: str
    description: str
    tags: list[str]


class StickerListResult(TypedDict):
    query: str
    count: int
    stickers: list[StickerResult]


def build_server() -> MCPServer[Any]:

    catalog = StickerCatalog()
    mcp = MCPServer(
        name="yuyu-sticker-cabinet",
        title="yuyu 的表情包小炉子",
        description="只读地查找并发送 yuyu 自己的表情包。",
        instructions=SERVER_INSTRUCTIONS,
        version="0.1.0",
    )

    read_only = ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    )

    @mcp.tool(
        name="list_stickers",
        title="查找表情包",
        description=(
            "按心情、动作、角色或物品搜索 yuyu 的表情包。未知准确 id 时先调用本工具；"
            "query 留空可浏览目录。结果只含描述和稳定 id，不会发送图片。"
        ),
        annotations=read_only,
        structured_output=True,
    )
    def list_stickers(
        query: Annotated[str, Field(max_length=200)] = "",
        limit: Annotated[int, Field(ge=1, le=100)] = 20,
    ) -> StickerListResult:
        try:
            stickers = catalog.search(query=query, limit=limit)
        except StickerCatalogError as exc:
            raise ValueError(str(exc)) from exc
        return {
            "query": query,
            "count": len(stickers),
            "stickers": [sticker.as_dict() for sticker in stickers],
        }

    @mcp.tool(
        name="show_sticker",
        title="发送表情包",
        description=(
            "按稳定 id 读取并直接渲染一张表情包。应在 list_stickers 选定结果后调用；"
            "不要猜测不存在的 id，也不要把图片内容改写成文字冒充已发送。"
        ),
        annotations=read_only,
    )
    def show_sticker(
        sticker_id: Annotated[str, Field(pattern=r"^[a-z0-9][a-z0-9_-]{0,63}$")],
    ) -> Image:
        try:
            path = catalog.image_path(sticker_id)
        except StickerCatalogError as exc:
            raise ValueError(str(exc)) from exc
        return Image(data=path.read_bytes(), format=path.suffix.lstrip(".").lower())

    return mcp


def main() -> None:
    build_server().run(
        transport="streamable-http",
        host=os.getenv("STICKER_HOST", "127.0.0.1"),
        port=int(os.getenv("STICKER_PORT", "8765")),
        streamable_http_path="/mcp",
        stateless_http=True,
        json_response=True,
    )


if __name__ == "__main__":
    main()
