"""Optional MCP server (pip install 'truthlens[mcp]') with two tools:

  check_claims(text)          v0.2: every claim, citation and number in the text -> verdict, evidence, fix
  verify_india_stat(statement) v0.1: numbers about India against official statistics

Run: truthlens-mcp   (stdio transport)
"""
from __future__ import annotations

from .checker import Checker
from .core import check_text

_checker = None
_pipe = None


def check_claims(text: str) -> dict:
    """Check every factual claim, citation and number in a draft passage against evidence.

    Returns the verified score and, per claim: verdict (SUPPORTED / PARTLY SUPPORTED / CONTRADICTED /
    UNVERIFIED / SKIPPED for opinions), confidence, quoted evidence with source URL and date, citation
    checks and a suggested corrected sentence. Uses the LLM and search keys in the server's environment.
    """
    global _pipe
    if _pipe is None:
        from .pipeline import Pipeline
        _pipe = Pipeline()
    from .readers import read_text
    rep = _pipe.run(read_text(text), "mcp")
    claims = []
    for c in rep["claims"]:
        claims.append({"sentence": c["claim"]["sentence"], "type": c["claim"]["type"], "verdict": c["verdict"],
                       "confidence": c["confidence"], "rationale": c["rationale"],
                       "evidence": [{"quote": e["snippet"][:500], "source": e["source_url"], "date": e["date"],
                                     "page": e["page"], "publisher": e["publisher"]} for e in c["evidence"][:3]],
                       "warnings": c["warnings"], "citation_checks": c["citation_checks"],
                       "suggested_fix": c["suggested_fix"], "fix_source": c["fix_source"]})
    return {"summary": rep["summary"], "claims": claims}


def verify_india_stat(statement: str) -> dict:
    """Check the numbers in a sentence about India against official statistics.

    Example: "India's real GDP grew 7.8% in FY 2025-26". Returns one finding per number with
    verdict (MATCH / CLOSE / MISMATCH / UNVERIFIED), official value, period, source URL,
    a ready-to-paste citation and India data-trap warnings.
    """
    global _checker
    if _checker is None:
        _checker = Checker()
    report = check_text(statement, name="mcp", checker=_checker)
    keep = ("claimed", "indicator_name", "period", "verdict", "reason", "official", "citation", "warnings")
    return {"summary": report["summary"], "findings": [{k: f[k] for k in keep} for f in report["findings"]]}


def build_server():
    try:
        from mcp.server.mcpserver import MCPServer as Server  # mcp >= 2
    except ImportError:
        try:
            from mcp.server.fastmcp import FastMCP as Server  # mcp 1.x
        except ImportError as e:  # pragma: no cover
            raise SystemExit("The MCP server needs the 'mcp' package: pip install 'truthlens[mcp]'") from e
    server = Server("truthlens")
    server.tool()(check_claims)
    server.tool()(verify_india_stat)
    return server


def main():  # pragma: no cover
    build_server().run()


if __name__ == "__main__":  # pragma: no cover
    main()
