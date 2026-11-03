"""A small JSONPath subset for plug-in response mapping (no dependency).

Supported:  $                      the document (or the current record)
            .name  ['name']        a key
            [0]  [-1]              a list index
            [*]  .*                every list item / every dict value
Examples:   $[1][*]   $.data[*]   $.values.NGDP_RPCH.IND   $.country.value   $[0].lastupdated
Anything else raises ValueError when the config is loaded (so a typo fails at `truthlens sources test`, not silently).
"""
from __future__ import annotations

import re
from typing import Any

_TOKEN_RX = re.compile(r"\.\*|\[\*\]|\.([A-Za-z_][\w\-]*)|\[(-?\d+)\]|\['([^']*)'\]|\[\"([^\"]*)\"\]")


def parse(path: str) -> list:
    p = (path or "").strip()
    if not p.startswith("$"):
        raise ValueError(f"JSONPath must start with '$': {path!r}")
    toks, i = [], 1
    while i < len(p):
        m = _TOKEN_RX.match(p, i)
        if not m:
            raise ValueError(f"unsupported JSONPath at {p[i:]!r} in {path!r} (supported: .key ['key'] [n] [*] .*)")
        g = m.group(0)
        if g in (".*", "[*]"):
            toks.append(("*", None))
        elif m.group(1) is not None:
            toks.append(("k", m.group(1)))
        elif m.group(2) is not None:
            toks.append(("i", int(m.group(2))))
        else:
            toks.append(("k", m.group(3) if m.group(3) is not None else m.group(4)))
        i = m.end()
    return toks


def find(doc: Any, path: str) -> list:
    """All values the path selects (empty list when nothing matches; never raises on data shape)."""
    cur = [doc]
    for kind, arg in parse(path):
        nxt = []
        for x in cur:
            if kind == "*":
                if isinstance(x, list):
                    nxt.extend(x)
                elif isinstance(x, dict):
                    nxt.extend(x.values())
            elif kind == "k":
                if isinstance(x, dict) and arg in x:
                    nxt.append(x[arg])
            elif kind == "i":
                if isinstance(x, list) and -len(x) <= arg < len(x):
                    nxt.append(x[arg])
        cur = nxt
    return cur


def first(doc: Any, path: str, default=None):
    if not path:
        return default
    got = find(doc, path)
    return got[0] if got else default
