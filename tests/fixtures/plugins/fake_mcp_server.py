"""Tiny fake MCP server for the plug-in tests (offline). Usage: fake_mcp_server.py stdio | http PORT

Tool `get_indicator(indicator, place)` returns rows like a statistics service would:
{"data": [{"year": "2023", "value": 3.2, "country": "India", "unit": "%"}, ...], "source": {...}}
"""
import json
import sys

DATA = {
    ("unemployment", "IND"): [{"year": "2022", "value": 3.6}, {"year": "2023", "value": 3.2}],
    ("inflation", "IND"): [{"year": "2023", "value": 5.6}],
}


def get_indicator(indicator: str, place: str = "IND") -> str:
    """Return yearly values of an indicator for a place, as JSON text."""
    rows = DATA.get((indicator, place), [])
    return json.dumps({"data": [dict(r, country="India", unit="%", title="<b>Fake</b> " + indicator) for r in rows],
                       "source": {"url": "https://stats.example.org/" + indicator, "updated": "2026-10-01"}})


def env_probe(name: str) -> str:
    """Report whether an environment variable reached this server (value never returned)."""
    import os
    return json.dumps({"data": [{"year": "2023", "value": 1 if os.environ.get(name) else 0, "country": "India"}]})


def build(port=None):
    try:
        from mcp.server.mcpserver import MCPServer as S  # mcp 2.x
        s = S("fake-stats")
    except ImportError:
        from mcp.server.fastmcp import FastMCP as S  # mcp 1.x
        s = S("fake-stats", host="127.0.0.1", port=port or 8000)
    s.tool()(get_indicator)
    s.tool()(env_probe)
    return s


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "stdio"
    if mode == "stdio":
        build().run()
    else:
        port = int(sys.argv[2])
        s = build(port)
        try:
            s.run(transport="streamable-http", host="127.0.0.1", port=port)
        except TypeError:
            s.run(transport="streamable-http")
