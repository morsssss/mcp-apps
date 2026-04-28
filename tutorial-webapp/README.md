# Tutorial Webapp

An interactive tutorial page for building MCP apps, with a live playground that lets you edit and run an MCP server and chat with Claude against it.

*Note: this is a work in progress!*

## Requirements

- Python 3.14+
- [uv](https://docs.astral.sh/uv/getting-started/installation/)
- An Anthropic API key

## Setup

```bash
cd tutorial-webapp
uv sync
```

Create a `.env` file with your API key:

```
ANTHROPIC_API_KEY=sk-ant-...
```

## Running locally

```bash
uv run python server.py
```

Then open [http://localhost:8000](http://localhost:8000).


## Structure

| File | Purpose |
|---|---|
| `server.py` | FastAPI backend — serves pages, proxies Claude API calls, manages the MCP server subprocess |
| `index.html` | Tutorial page — renders `tutorial.md` with syntax highlighting and language tabs |
| `playground.html` | Live playground — Python editor, HTML editor, and chat UI |
| `tutorial.md` | Tutorial content (edit this to update the tutorial) |
| `workspace/` | Scratch directory where the playground writes and runs user code |
