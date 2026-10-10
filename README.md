# yuyu 的表情包小炉子

一个最小、只读的 MCP 表情包服务器。它让 ChatGPT 能够：

1. 用 `list_stickers` 按心情、动作、角色或物品查找表情包；
2. 用 `show_sticker` 读取选中的原图，并通过 MCP Apps 内嵌图片卡片直接渲染；
3. 根据服务器说明，在语境确实合适时自然地主动使用，但不会每句话都发。

当前装了三位测试员：书上小猫、餐盘小龟、融化小龟。

## 先在本机验货

目录和图片读取只依赖 Python 标准库：

```bash
git clone https://github.com/yuyumochii/yuyu-sticker-cabinet.git
cd yuyu-sticker-cabinet
python -m unittest discover -s tests -v
python smoke_test.py
python catalog.py 融化
```

## 启动 MCP

建议放进独立虚拟环境：

```bash
cd yuyu-sticker-cabinet
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python server.py
```

项目使用官方 Python MCP SDK 2.x；`requirements.txt` 已把主版本约束在兼容范围内。

安装依赖后，还可以一键跑完整的 MCP 握手、列工具、选图和图片返回测试：

```bash
python integration_test.py
```

默认只监听 `127.0.0.1:8765`，Streamable HTTP 地址是：

```text
http://127.0.0.1:8765/mcp
```

可以用环境变量改监听地址：

```bash
STICKER_HOST=127.0.0.1 STICKER_PORT=8765 python server.py
```

## 往柜子里添图

1. 把 PNG/APNG、JPG、WebP（包括动态 WebP）或 GIF 放进 `stickers/`；服务器会原样送出动图，不会压成静态图片。单张上限 8 MiB。
2. 在 `stickers.json` 增加一条记录。
3. `id` 用稳定的小写英文标识；`title`、`description` 和 `tags` 写给小机看，越贴近真实语境，挑图越准。
4. 运行测试。服务器不需要因为新增图片而改代码。

示例：

```json
{
  "id": "turtle-hug",
  "file": "turtle-hug.png",
  "title": "抱住不撒手的小龟",
  "description": "适合撒娇、贴贴、安慰和不想松手。",
  "tags": ["乌龟", "抱住", "贴贴", "撒娇", "安慰"]
}
```

## 接进 ChatGPT

本地验证通过后，把 `/mcp` 暴露成稳定的 HTTPS 地址，或使用 Secure MCP Tunnel。然后在 ChatGPT 的 Plugins 页面选择 `+` → **Add custom MCP server**，填入完整的 `/mcp` 地址，扫描并安装到自己的工作区。

这个项目默认绑定回环地址。不要直接把 8765 端口裸露到公网；沿用反向代理或隧道，并把它和玩具控制服务分开部署。

## 用 Docker 部署到 VPS

仓库自带 `compose.yaml`，并仅把服务映射到 VPS 回环地址
`127.0.0.1:18765`：

```bash
git clone https://github.com/yuyumochii/yuyu-sticker-cabinet.git
cd yuyu-sticker-cabinet
docker compose up -d --build
docker compose ps
```

当 Cloudflare Tunnel 容器使用 host 网络时，源站服务填写：

```text
http://127.0.0.1:18765
```

公网 MCP 地址则是：

```text
https://你的独立子域名/mcp
```

`show_sticker` 还会在同一域名下读取原图，例如：

```text
https://你的独立子域名/stickers/turtle-plate
```

部署新版本后，在 ChatGPT 的插件详情页点一次 **Refresh**，让 ChatGPT 重新读取
`show_sticker` 的输出结构和 `ui://` 图片卡片资源。

官方参考：

- https://developers.openai.com/plugins/build/mcp-server
- https://developers.openai.com/plugins/connect-and-test
