"""Tutorial webapp backend — proxies Claude API calls and manages the user's MCP server subprocess."""
import json
import os
import sys
import asyncio
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
import anthropic
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse
from pydantic import BaseModel
from mcp import ClientSession, StdioServerParameters, stdio_client

load_dotenv()

ANTHROPIC_API_KEY = os.getenv('ANTHROPIC_API_KEY')

WORKSPACE = Path(__file__).parent / "workspace"
WORKSPACE.mkdir(exist_ok=True)
SERVER_FILE = WORKSPACE / "mcp_server.py"
VIEW_FILE = WORKSPACE / "view.html"

DEFAULT_PYTHON = '''\
import requests
from fastmcp import FastMCP
from fastmcp.apps import AppConfig, ResourceCSP

API_BASE_URL = "https://dog.ceo/api"
RESOURCE_URI = "ui://dog_image"

mcp = FastMCP("dogs")
view_resource = {"resourceUri": RESOURCE_URI}


@mcp.tool(app=view_resource)
def get_random_dog() -> str:
    """Retrieves the URL of an image of a random dog and displays it."""
    resp = requests.get(f"{API_BASE_URL}/breeds/image/random")
    return resp.json()["message"]


@mcp.tool(app=view_resource)
def get_dog_by_breed(breed: str) -> str:
    """Retrieves a dog image for the given breed name."""
    resp = requests.get(f"{API_BASE_URL}/breed/{breed}/images")
    return resp.json()["message"][0]


@mcp.resource(
    RESOURCE_URI,
    app=AppConfig(
        csp=ResourceCSP(
            resource_domains=["https://unpkg.com", "https://images.dog.ceo"],
            connect_domains=["http://dog.ceo"],
        )
    ),
)
def view() -> str:
    with open("view.html") as f:
        return f.read()


if __name__ == "__main__":
    mcp.run()
'''

DEFAULT_HTML = '''\
<!DOCTYPE html>
<html>
<head>
  <style>
    body {
      font-family: system-ui, sans-serif;
      background: #77c;
      display: flex;
      flex-direction: column;
      align-items: center;
      padding: 20px;
    }
    img { max-width: 400px; border-radius: 8px; margin-top: 16px; }
    form { margin-top: 14px; display: flex; gap: 10px; align-items: center; }
    select, button {
      font: inherit;
      padding: 10px 12px;
      border-radius: 8px;
      border: 1px solid rgba(0,0,0,0.18);
      background: rgba(255,255,255,0.92);
    }
    button { font-weight: 600; cursor: pointer; }
  </style>
</head>
<body>
  <img id="dog-img" src="" alt="Dog will appear here" />
  <form id="breed-form">
    <select id="breed-select">
      <option value="">(choose a breed)</option>
      <option value="bullterrier/staffordshire">pit bull</option>
      <option value="doberman">doberman</option>
      <option value="malamute">malamute</option>
      <option value="pekinese">pekinese</option>
      <option value="pug">pug</option>
    </select>
    <button type="submit">Get my dog</button>
  </form>
  <script type="module">
    import { App } from "https://unpkg.com/@modelcontextprotocol/ext-apps@0.4.0/app-with-deps";
    const app = new App({ name: "Dog Viewer", version: "1.0.0" });

    function showDog(content) {
      const url = content?.find(b => b.type === "text")?.text;
      if (url) document.getElementById("dog-img").src = url;
    }

    app.ontoolresult = ({ content }) => showDog(content);
    await app.connect();

    document.getElementById("breed-form").addEventListener("submit", async (e) => {
      e.preventDefault();
      const breed = document.getElementById("breed-select").value;
      if (!breed) return;
      const result = await app.callServerTool({ name: "get_dog_by_breed", arguments: { breed } });
      showDog(result?.content);
    });
  </script>
</body>
</html>
'''


def _serialize_block(b) -> dict:
    """Serialize an Anthropic content block to only the fields the API accepts."""
    if b.type == "text":
        return {"type": "text", "text": b.text}
    if b.type == "tool_use":
        return {"type": "tool_use", "id": b.id, "name": b.name, "input": b.input}
    return b.model_dump(exclude_none=True)


class MCPServer:
    """Keeps a long-lived MCP client session open against a user-supplied subprocess server."""

    def __init__(self) -> None:
        self.session: Optional[ClientSession] = None
        self.running = False
        self.error: Optional[str] = None
        self._task: Optional[asyncio.Task] = None
        self._ready: asyncio.Event = asyncio.Event()
        self._shutdown: asyncio.Event = asyncio.Event()

    async def start(self, python_code: str) -> None:
        await self.stop()
        SERVER_FILE.write_text(python_code)
        if not VIEW_FILE.exists():
            VIEW_FILE.write_text(DEFAULT_HTML)
        self._ready = asyncio.Event()
        self._shutdown = asyncio.Event()
        self.error = None
        self._task = asyncio.create_task(self._run())
        try:
            await asyncio.wait_for(asyncio.shield(self._ready.wait()), timeout=15.0)
        except asyncio.TimeoutError:
            await self.stop()
            raise HTTPException(500, "MCP server startup timed out")
        if self.error:
            raise HTTPException(500, self.error)

    async def _run(self) -> None:
        params = StdioServerParameters(
            command=sys.executable,
            args=[str(SERVER_FILE)],
            cwd=str(WORKSPACE),
        )
        try:
            async with stdio_client(params) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    self.session = session
                    self.running = True
                    self._ready.set()
                    await self._shutdown.wait()
        except Exception as exc:
            self.error = str(exc)
        finally:
            self.session = None
            self.running = False
            self._ready.set()

    async def stop(self) -> None:
        if self._task and not self._task.done():
            self._shutdown.set()
            try:
                await asyncio.wait_for(self._task, timeout=5.0)
            except (asyncio.TimeoutError, asyncio.CancelledError):
                self._task.cancel()
        self._task = None
        self.session = None
        self.running = False


mcp_server = MCPServer()
aclient = anthropic.AsyncAnthropic(api_key=ANTHROPIC_API_KEY)

app = FastAPI()


class StartRequest(BaseModel):
    python_code: str


class SaveViewRequest(BaseModel):
    html_code: str


class ChatRequest(BaseModel):
    message: str
    history: list[dict]


@app.get("/")
async def index() -> HTMLResponse:
    return HTMLResponse((Path(__file__).parent / "index.html").read_text())


@app.get("/playground")
async def playground() -> HTMLResponse:
    return HTMLResponse((Path(__file__).parent / "playground.html").read_text())


@app.get("/tutorial.md")
async def tutorial() -> HTMLResponse:
    return HTMLResponse(
        (Path(__file__).parent / "tutorial.md").read_text(),
        media_type="text/plain",
    )


@app.get("/defaults/python")
async def default_python() -> HTMLResponse:
    return HTMLResponse(DEFAULT_PYTHON, media_type="text/plain")


@app.get("/defaults/html")
async def default_html() -> HTMLResponse:
    return HTMLResponse(DEFAULT_HTML, media_type="text/plain")


@app.post("/server/start")
async def start_server(req: StartRequest) -> dict:
    await mcp_server.start(req.python_code)
    return {"status": "running"}


@app.post("/server/stop")
async def stop_server() -> dict:
    await mcp_server.stop()
    return {"status": "stopped"}


@app.get("/server/status")
async def server_status() -> dict:
    return {"running": mcp_server.running, "error": mcp_server.error}


@app.post("/server/save-view")
async def save_view(req: SaveViewRequest) -> dict:
    VIEW_FILE.write_text(req.html_code)
    return {"status": "saved"}


@app.post("/chat")
async def chat(req: ChatRequest) -> StreamingResponse:
    async def generate():
        messages = list(req.history) + [{"role": "user", "content": req.message}]

        tools: list[dict] | None = None
        if mcp_server.session and mcp_server.running:
            try:
                result = await mcp_server.session.list_tools()
                if result.tools:
                    tools = [
                        {
                            "name": t.name,
                            "description": t.description or "",
                            "input_schema": t.inputSchema,
                        }
                        for t in result.tools
                    ]
            except Exception as exc:
                yield f"data: {json.dumps({'type': 'error', 'text': str(exc)})}\n\n"
                return

        try:
            while True:
                call_kwargs: dict = {
                    "model": "claude-opus-4-7",
                    "max_tokens": 4096,
                    "messages": messages,
                }
                if tools:
                    call_kwargs["tools"] = tools

                async with aclient.messages.stream(**call_kwargs) as stream:
                    async for text in stream.text_stream:
                        yield f"data: {json.dumps({'type': 'text', 'delta': text})}\n\n"
                    final = await stream.get_final_message()

                messages.append({
                    "role": "assistant",
                    "content": [_serialize_block(b) for b in final.content],
                })

                if final.stop_reason != "tool_use":
                    break

                tool_results = []
                for block in final.content:
                    if block.type != "tool_use":
                        continue
                    yield f"data: {json.dumps({'type': 'tool_use', 'name': block.name, 'input': block.input})}\n\n"
                    if mcp_server.session:
                        try:
                            r = await mcp_server.session.call_tool(block.name, block.input)
                            content = [
                                {"type": "text", "text": getattr(c, "text", str(c))}
                                for c in r.content
                            ]
                        except Exception as exc:
                            content = [{"type": "text", "text": f"Tool error: {exc}"}]
                    else:
                        content = [{"type": "text", "text": "No MCP server is running."}]
                    yield f"data: {json.dumps({'type': 'tool_result', 'name': block.name, 'content': content})}\n\n"
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": content,
                    })

                messages.append({"role": "user", "content": tool_results})

        except Exception as exc:
            yield f"data: {json.dumps({'type': 'error', 'text': str(exc)})}\n\n"

        yield f"data: {json.dumps({'type': 'done', 'history': messages})}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"X-Accel-Buffering": "no", "Cache-Control": "no-cache"},
    )


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
