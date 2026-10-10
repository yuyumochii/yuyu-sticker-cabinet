from __future__ import annotations

import os
from pathlib import Path
from typing import Annotated, Any, TypedDict

from mcp.server.apps import Apps, ResourceCsp
from mcp.server.mcpserver import Image, MCPServer
from mcp_types import CallToolResult, TextContent, ToolAnnotations
from pydantic import BaseModel, Field
from starlette.requests import Request
from starlette.responses import FileResponse, PlainTextResponse

from catalog import StickerCatalog, StickerCatalogError


SERVER_INSTRUCTIONS = (
    "这是 yuyu 的私人表情包柜。表情包确实贴合当前语境时，可以自然地主动挑一张，"
    "不必等用户点名；但要克制，不要每句话都发。未知准确 id 时先调用 list_stickers，"
    "选定后再调用 show_sticker。show_sticker 会返回原图和可见图片卡片；只有工具成功后，"
    "才可以说已经发出了图片，也不要用文字描述冒充图片。"
)

DEFAULT_PUBLIC_BASE_URL = "https://stickers.little-archive.com"
STICKER_WIDGET_URI = "ui://yuyu-sticker-cabinet/sticker-v3.html"


class StickerResult(TypedDict):
    id: str
    title: str
    description: str
    tags: list[str]


class StickerListResult(TypedDict):
    query: str
    count: int
    stickers: list[StickerResult]


class StickerDisplayResult(BaseModel):
    sticker_id: str
    title: str
    description: str
    image_url: str
    alt: str


def _public_base_url() -> str:
    return os.getenv("STICKER_PUBLIC_BASE_URL", DEFAULT_PUBLIC_BASE_URL).rstrip("/")


def build_server() -> MCPServer[Any]:

    catalog = StickerCatalog()
    public_base_url = _public_base_url()
    apps = Apps()

    widget_html = (Path(__file__).resolve().parent / "sticker_widget.html").read_text(
        encoding="utf-8"
    )
    apps.add_html_resource(
        STICKER_WIDGET_URI,
        widget_html,
        name="yuyu-sticker-card",
        title="yuyu 的表情包",
        description="在聊天中显示选中的表情包原图。",
        csp=ResourceCsp(resource_domains=[public_base_url]),
        prefers_border=False,
    )

    read_only = ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    )

    @apps.tool(
        resource_uri=STICKER_WIDGET_URI,
        name="show_sticker",
        title="发送表情包",
        description=(
            "按稳定 id 读取并直接渲染一张表情包。应在 list_stickers 选定结果后调用；"
            "不要猜测不存在的 id，也不要把图片内容改写成文字冒充已发送。"
        ),
        annotations=read_only,
        meta={
            "openai/outputTemplate": STICKER_WIDGET_URI,
            "openai/toolInvocation/invoking": "正在端表情包…",
            "openai/toolInvocation/invoked": "表情包端来啦",
        },
    )
    def show_sticker(
        sticker_id: Annotated[str, Field(pattern=r"^[a-z0-9][a-z0-9_-]{0,63}$")],
    ) -> Annotated[CallToolResult, StickerDisplayResult]:
        try:
            sticker = catalog.get(sticker_id)
            path = catalog.image_path(sticker_id)
        except StickerCatalogError as exc:
            raise ValueError(str(exc)) from exc

        image_url = f"{public_base_url}/stickers/{sticker.id}"
        structured = StickerDisplayResult(
            sticker_id=sticker.id,
            title=sticker.title,
            description=sticker.description,
            image_url=image_url,
            alt=sticker.title,
        )
        image = Image(data=path.read_bytes(), format=path.suffix.lstrip(".").lower())
        return CallToolResult(
            content=[
                image.to_image_content(),
                TextContent(
                    text=(
                        f"已返回表情包「{sticker.title}」。图片卡片会直接显示给用户，"
                        "无需再把图片改写成文字。"
                    )
                ),
            ],
            structured_content=structured.model_dump(),
        )

    mcp = MCPServer(
        name="yuyu-sticker-cabinet",
        title="yuyu 的表情包小炉子",
        description="只读地查找并发送 yuyu 自己的表情包。",
        instructions=SERVER_INSTRUCTIONS,
        version="0.5.0",
        extensions=[apps],
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

    @mcp.custom_route("/stickers/{sticker_id}", methods=["GET"], include_in_schema=False)
    async def serve_sticker(request: Request):
        sticker_id = request.path_params["sticker_id"]
        try:
            path = catalog.image_path(sticker_id)
        except StickerCatalogError as exc:
            return PlainTextResponse(str(exc), status_code=404)
        return FileResponse(
            path,
            media_type=catalog.mime_type(sticker_id),
            headers={
                "Cache-Control": "public, max-age=3600",
                "X-Content-Type-Options": "nosniff",
            },
        )

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
