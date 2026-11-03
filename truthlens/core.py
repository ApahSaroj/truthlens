"""High-level entry points used by the CLI, the API and the MCP tool."""
from __future__ import annotations

from pathlib import Path
from typing import Optional, Union

from .checker import Checker
from .readers import read_file, read_text, read_url
from .report import build_report


def check_path(path: Union[str, Path], online: bool = True, checker: Optional[Checker] = None) -> dict:
    ck = checker or Checker(online=online)
    blocks = read_file(path)
    findings = ck.check_blocks(blocks)
    return build_report(findings, Path(path).name, {"blocks": len(blocks), "worldbank_errors": ck.wb.errors})


def check_bytes(data: bytes, suffix: str, name: str, online: bool = True, checker: Optional[Checker] = None) -> dict:
    """v0.5.2: numbers-only check of an uploaded file read in memory."""
    from .readers import read_bytes
    ck = checker or Checker(online=online)
    blocks = read_bytes(data, suffix)
    findings = ck.check_blocks(blocks)
    return build_report(findings, name, {"blocks": len(blocks), "worldbank_errors": ck.wb.errors})


def check_text(text: str, name: str = "text input", online: bool = True, checker: Optional[Checker] = None) -> dict:
    ck = checker or Checker(online=online)
    blocks = read_text(text)
    findings = ck.check_blocks(blocks)
    return build_report(findings, name, {"blocks": len(blocks), "worldbank_errors": ck.wb.errors})


def check_url(url: str, online: bool = True, checker: Optional[Checker] = None) -> dict:
    ck = checker or Checker(online=online)
    blocks, meta = read_url(url)
    findings = ck.check_blocks(blocks)
    try:  # optional: domain trust rating from the original TruthLens source list (repo checkout only)
        from services.source_evaluator import evaluate_source
        meta["source_rating"] = evaluate_source(meta.get("domain", ""))
    except Exception:
        pass
    meta.update({"blocks": len(blocks), "worldbank_errors": ck.wb.errors})
    return build_report(findings, url, meta)
