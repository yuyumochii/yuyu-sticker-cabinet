from __future__ import annotations

import socket
import subprocess
import time

import anyio
import httpx2
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client


HOST = "127.0.0.1"
PORT = 8765
URL = f"http://{HOST}:{PORT}/mcp"


def wait_until_listening(process: subprocess.Popen[str]) -> None:
    for _ in range(50):
        if process.poll() is not None:
            output = process.stdout.read() if process.stdout else ""
            raise RuntimeError(f"服务器提前退出：\n{output}")
        try:
            with socket.create_connection((HOST, PORT), timeout=0.1):
                return
        except OSError:
            time.sleep(0.1)
    raise RuntimeError("服务器在 5 秒内没有启动。")


async def inspect_server() -> None:
    async with httpx2.AsyncClient(trust_env=False) as http_client:
        async with streamable_http_client(URL, http_client=http_client) as (read, write):
            async with ClientSession(read, write) as session:
                initialized = await session.initialize()
                tools = await session.list_tools()
                listed = await session.call_tool(
                    "list_stickers", {"query": "呆住", "limit": 3}
                )
                shown = await session.call_tool(
                    "show_sticker", {"sticker_id": "turtle-plate"}
                )

                tool_names = [tool.name for tool in tools.tools]
                selected_id = listed.structured_content["stickers"][0]["id"]
                image = shown.content[0]

                assert initialized.server_info.name == "yuyu-sticker-cabinet"
                assert initialized.instructions
                assert tool_names == ["list_stickers", "show_sticker"]
                assert selected_id == "turtle-plate"
                assert image.type == "image"
                assert image.mime_type == "image/png"
                assert image.data

                print(f"服务器：{initialized.server_info.name} {initialized.server_info.version}")
                print(f"工具：{', '.join(tool_names)}")
                print(f"‘呆住’选中：{selected_id}")
                print(f"图片返回：{image.mime_type}，{len(image.data)} 个 base64 字符")
                print("端到端测试通过。")


def main() -> None:
    process = subprocess.Popen(
        [".venv/bin/python", "server.py"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    try:
        wait_until_listening(process)
        anyio.run(inspect_server)
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)


if __name__ == "__main__":
    main()
