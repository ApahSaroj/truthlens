"""v0.4 key-free ministry data sources: RBI, CEA, PPAC and Jal Jeevan Mission (probed live on 2 Nov 2026).

RBI   https://www.rbi.org.in/  "Current Rates" box (policy repo, SDF, MSF, bank rate, CRR, SLR, FBIL reference rates)
      https://www.rbi.org.in/pressreleases_rss.xml -> latest "Bulletin Weekly Statistical Supplement - Extract" release
      (foreign exchange reserves; scheduled commercial banks' credit and deposit growth, year-on-year).
      DBIE (data.rbi.org.in) itself is not used: its gateway needs a session token plus RSA/AES-encrypted payloads
      generated in the browser, which is not a documented public API.
CEA   https://cea.nic.in/api/dashboard/installed-capacity     state-wise installed capacity (MW), monthly
      https://cea.nic.in/api/power-sector-performance          all-India monthly: peak demand met (GW), energy supplied
                                                                 (BU), conventional/renewable generation (BU), PLF (%)
      https://cea.nic.in/api/dashboard/energy-supply-position  state-wise energy requirement / supplied (MU)
      These are the JSON calls the CEA home page makes itself.
PPAC  POST https://ppac.gov.in/AjaxController/getImportExports                 (financialYear, reportBy 1=TMT 3=US$ mn, pageId 14)
      POST https://ppac.gov.in/AjaxController/getConsumptionPetroleumProductsData (financialYear, reportBy 1, pageId 43)
      https://ppac.gov.in/ "PPAC Tracker" and "Important News" (retail selling price of petrol/diesel in Delhi,
      ethanol blending, PMUY and active LPG connections).
JJM   POST https://ejalshakti.gov.in/jjmreport/JJMIndia.aspx/Bind_table_graph  (the dashboard's own state table:
      households with tap water connections, total rural households, per cent; parameters obfuscated by the page's
      `encodeTxt` (escape + char shift), reproduced in `_jjm_enc`).
"""
from __future__ import annotations

import datetime as dt
import html as _html
import json
import re
from typing import Optional

from ..net import FetchError, fetch_bytes, get_json, safe_post
from .base import norm_ws, terms
from .official_api import LiveSource, month_period, pick_indicator_rows, scaled, unit_scale
from .tables import dedupe_findings, match_rows

UA_HEADERS = {"Accept": "application/json, text/plain, */*"}


CLAUSE_SPLIT_RX = re.compile(r"(;|,(?!\d)|\band\b|\bwhile\b|\bwhereas\b|\bcompared\b|\bthan\b)")


def _clause_of(claim_text: str, n) -> str:
    """The clause of the sentence that holds figure n ('The repo rate is 5.5% and the CRR is 3%' -> 'the CRR is 3%')."""
    i = claim_text.find(n.raw)
    if i < 0:
        return claim_text
    pos = 0
    for p in CLAUSE_SPLIT_RX.split(claim_text):
        if pos <= i < pos + len(p):
            return p
        pos += len(p)
    return claim_text


def _clause_numbers(claim_text: str, numbers: list, label: str) -> list:
    """Numbers whose own clause shares a term with the indicator label ('repo rate 5.5% and CRR 3%': 3% is CRR's)."""
    lt = terms(label)
    out = []
    for n in numbers:
        if claim_text.find(n.raw) < 0:
            out.append(n)
            continue
        # the clause before the number names the indicator in most sentences ("the repo rate is 5.5%")
        if terms(_clause_of(claim_text, n)) & lt or (len(numbers) == 1 and terms(claim_text) & lt):
            out.append(n)
    return out


PRESENT_RX = re.compile(r"\b(is|are|stands?|stood at|currently|at present|now|as of|as on|latest|today|has|have)\b", re.I)


class GroupedSource(LiveSource):
    """A source whose data is a set of indicator groups {label: rows}; the best-fitting groups are matched.

    Snapshot rule (fail closed): most of these sources publish the *current* value only (a rate, a monthly dashboard).
    When the draft names no period and is not written in the present tense, a different figure may simply be an older
    one, so a mismatch against the snapshot is reported as UNVERIFIED (with the current value), never CONTRADICTED."""
    unit_base: dict = {}

    def __init__(self, cfg, session=None):
        super().__init__(cfg, session)
        self.unit_base = dict(type(self).unit_base)

    def groups(self, claim_text: str) -> tuple[dict, dict]:  # pragma: no cover - interface
        """Return ({label: rows}, {label: source dict})."""
        raise NotImplementedError

    def min_relevance(self, label: str) -> float:
        """Least word overlap between the sentence and a table's rows before its figures are compared (v0.5.3 hook)."""
        return 0.5

    def match(self, claim_text: str, numbers: list, label_ok=None) -> list[dict]:
        from .tables import claim_periods
        if not numbers or not self.relevant(claim_text):
            return []
        groups, sources = self.groups(claim_text)
        if label_ok is not None:
            groups = {k: v for k, v in groups.items() if label_ok(k)}
        out = []
        dated = bool(claim_periods(claim_text))
        decided: set = set()
        for label, rows in pick_indicator_rows(claim_text, groups)[:4]:
            nums = [n for n in _clause_numbers(claim_text, numbers, label) if n.raw not in decided]
            if not nums or not rows:
                continue
            base = self.unit_base.get(label)
            if base:
                div, unit = unit_scale(claim_text, base)
                rows = scaled(rows, div)
                shown = f"{label} ({unit})"
            else:
                shown = label
            src = dict(sources.get(label) or {})
            src.setdefault("retriever", self.name)
            src.setdefault("publisher", self.publisher)
            ind_id = f"{self.name}:{re.sub(r'[^a-z0-9]+', '-', label.lower()).strip('-')}"
            if len(numbers) > 1:
                # several figures in one sentence: each is judged on its own clause when that clause names this
                # indicator, so 'the CRR is 3%' is not diluted by the repo-rate words of the other clause
                fs = []
                lt = terms(label)
                for n in nums:
                    cl = _clause_of(claim_text, n)
                    fs += match_rows(claim_text, [n], rows, label=shown, source=src, indicator_id=ind_id,
                                     relevance_text=cl if terms(cl) & lt else None,
                                     min_relevance=self.min_relevance(label))
            else:
                fs = match_rows(claim_text, nums, rows, label=shown, source=src, indicator_id=ind_id,
                                min_relevance=self.min_relevance(label))
            snapshot = not any(r.get("year") for r in rows)
            for f in fs:
                if f["verdict"] == "MISMATCH" and "sum of States/UTs" in str((f.get("official") or {}).get("snippet") or ""):
                    f["verdict"] = "UNVERIFIED"
                    f["reason"] = (f"TruthLens' sum of the State/UT rows is {f['official']['display']}; a national total "
                                   "derived by adding states is not used to contradict a figure.")
                    continue
                if f["verdict"] == "MISMATCH" and not f.get("negated") and (snapshot or not dated) \
                        and not (dated and not snapshot) and not PRESENT_RX.search(claim_text):
                    f["verdict"] = "UNVERIFIED"
                    f["reason"] = (f"The latest official value is {f['official']['display']}; the draft gives no date and "
                                   "is not in the present tense, so its figure may be an older one (not contradicted).")
            out += fs
            decided |= {f["claimed"] for f in fs if f["verdict"] != "UNVERIFIED"}
            if all(n.raw in decided for n in numbers):
                break
        return dedupe_findings(out)


def _text_of_html(data: bytes) -> str:
    from bs4 import BeautifulSoup
    return norm_ws(BeautifulSoup(data, "html.parser").get_text(" "))


def _num(s: str) -> Optional[float]:
    try:
        return float(str(s).replace(",", "").strip())
    except (TypeError, ValueError):
        return None


def _date_iso(text: str) -> Optional[str]:
    m = re.search(r"([A-Z][a-z]+)\.?\s+(\d{1,2}),\s*((?:19|20)\d{2})", text or "")
    if not m:
        return None
    for fmt in ("%B %d %Y", "%b %d %Y"):
        try:
            return dt.datetime.strptime(f"{m.group(1)[:3] if fmt == '%b %d %Y' else m.group(1)} {m.group(2)} {m.group(3)}",
                                        fmt).date().isoformat()
        except ValueError:
            continue
    return None


# ================================================================================================== RBI
RBI_HOME = "https://www.rbi.org.in/"
RBI_RSS = "https://www.rbi.org.in/pressreleases_rss.xml"
RBI_RATE_NAMES = ["Policy Repo Rate", "Standing Deposit Facility Rate", "Marginal Standing Facility Rate", "Bank Rate",
                  "Fixed Reverse Repo Rate", "CRR", "SLR"]
RBI_FX_RX = re.compile(r"INR\s*/\s*(1|100|10000)\s+([A-Z]{3})\*?\s*:\s*([\d.,]+)")


def parse_rbi_rates(text: str) -> dict:
    """{'rates': {name: value}, 'fx': {'USD': value per 1 unit}, 'fx_as_of': iso} from the RBI home page text."""
    i = text.find("Current Rates")
    block = text[i:i + 2500] if i >= 0 else ""
    rates = {}
    for name in RBI_RATE_NAMES:
        m = re.search(rf"{re.escape(name)}\s*:\s*([\d.]+)\s*%", block)
        if m:
            rates[name] = float(m.group(1))
    fx = {}
    for m in RBI_FX_RX.finditer(block):
        per = float(m.group(1))
        fx[m.group(2)] = round(float(m.group(3).replace(",", "")) / per, 6) if per == 1 else float(m.group(3).replace(",", ""))
    am = re.search(r"As at [^)]*? of ([A-Z][a-z]+ \d{1,2}, \d{4})", block)
    return {"rates": rates, "fx": fx, "fx_as_of": _date_iso(am.group(1)) if am else None}


def parse_rbi_wss(text: str) -> dict:
    """Forex reserves and bank credit/deposit growth from the WSS extract press release text."""
    out: dict = {}
    m = re.search(r"Foreign Exchange Reserves\*?\s*Item\s*As on ([A-Z][a-z]+\.? \d{1,2}, \d{4})", text)
    if m:
        out["fx_as_of"] = _date_iso(m.group(1))
    for key, rx in (("total", r"1 Total Reserves\s+([\d,]+)\s+([\d,]+)"),
                    ("fca", r"1\.1 Foreign Currency Assets\s*#?\s+([\d,]+)\s+([\d,]+)"),
                    ("gold", r"1\.2 Gold\s+([\d,]+)\s+([\d,]+)")):
        mm = re.search(rx, text)
        if mm:
            out[key] = {"inr_crore": _num(mm.group(1)), "usd_mn": _num(mm.group(2))}
    m = re.search(r"Outstanding as on ([A-Z][a-z]+\.? \d{1,2}, \d{4})", text)
    if m:
        out["banks_as_of"] = _date_iso(m.group(1))
    for key, rx in (("deposit_growth", r"2\.1a Growth \(Per cent\)\s+((?:-?[\d.]+\s+){4}-?[\d.]+)"),
                    ("credit_growth", r"7\.1a Growth \(Per cent\)\s+((?:-?[\d.]+\s+){4}-?[\d.]+)")):
        mm = re.search(rx, text)
        if mm:
            vals = [float(x) for x in mm.group(1).split()]
            out[key] = {"yoy": vals[-1], "fy_so_far": vals[2]}
    return out


class RBISource(GroupedSource):
    name = "rbi"
    badge = "RBI"
    publisher = "Reserve Bank of India"
    portal = "rbi.org.in"
    keywords = ["rbi", "reserve bank", "repo rate", "repo", "reverse repo", "crr", "slr", "cash reserve ratio",
                "statutory liquidity ratio", "bank rate", "standing deposit facility", "marginal standing facility",
                "forex reserves", "foreign exchange reserves", "forex", "bank credit", "credit growth", "deposit growth",
                "scheduled commercial banks", "banks' credit", "bank deposits", "aggregate deposits",
                "rupee", "exchange rate", "inr"]
    ttl = 6 * 3600
    unit_base = {"foreign exchange reserves total": "USD_mn", "foreign currency assets": "USD_mn",
                 "gold reserves": "USD_mn"}

    def status(self) -> dict:
        return {"name": self.name, "configured": not self.offline,
                "detail": "RBI current rates (rbi.org.in) + Weekly Statistical Supplement extract via the press-release "
                          "RSS (forex reserves, bank credit/deposit growth), no key. DBIE not used (encrypted session API)."}

    def _home(self):
        def get():
            data, _ct, _u = fetch_bytes(self.session, RBI_HOME, self.cfg.timeout, 4 * 2 ** 20)
            rec = parse_rbi_rates(_text_of_html(data))
            if not rec.get("rates"):
                # v0.5: never cache an empty answer (a changed page would hide the rates for hours); keep the stale one
                raise FetchError("RBI home page: no 'Current Rates' found")
            return rec
        return self.cached("home", get)

    def _wss(self):
        def get():
            data, _ct, _u = fetch_bytes(self.session, RBI_RSS, self.cfg.timeout, 2 * 2 ** 20)
            x = data.decode("utf-8", "replace")
            for item in re.findall(r"<item>(.*?)</item>", x, re.S):
                t = re.search(r"<title>(.*?)</title>", item, re.S)
                ln = re.search(r"<link>(.*?)</link>", item, re.S)
                if t and ln and "Weekly Statistical Supplement" in t.group(1):
                    url = _html.unescape(ln.group(1).strip())
                    if not url.startswith("https://www.rbi.org.in/"):
                        raise FetchError("unexpected WSS link host")
                    page, _c, _f = fetch_bytes(self.session, url, self.cfg.timeout, 4 * 2 ** 20)
                    rec = parse_rbi_wss(_text_of_html(page))
                    rec["url"] = url
                    return rec
            return {}
        return self.cached("wss", get)

    def groups(self, claim_text: str):
        groups, sources = {}, {}
        home, fetched = self._home()
        if home:
            src = {"url": RBI_HOME, "title": "RBI home page, Current Rates", "published": None,
                   "as_of": f"retrieved {fetched}" if fetched else None}
            labels = {"Policy Repo Rate": "policy repo rate", "Standing Deposit Facility Rate": "standing deposit facility rate sdf",
                      "Marginal Standing Facility Rate": "marginal standing facility rate msf", "Bank Rate": "bank rate",
                      "Fixed Reverse Repo Rate": "fixed reverse repo rate", "CRR": "cash reserve ratio crr",
                      "SLR": "statutory liquidity ratio slr"}
            for k, v in (home.get("rates") or {}).items():
                lab = labels.get(k, k.lower())
                groups[lab] = [{"indicator": lab, "value": v}]
                sources[lab] = src
            usd = (home.get("fx") or {}).get("USD")
            if usd:
                lab = "rupee exchange rate inr per us dollar fbil reference rate"
                groups[lab] = [{"indicator": lab, "value": usd}]
                sources[lab] = dict(src, published=home.get("fx_as_of"),
                                    as_of=home.get("fx_as_of") or src["as_of"])
        wss, fetched = self._wss()
        if wss:
            src = {"url": wss.get("url") or RBI_RSS, "title": "RBI Bulletin Weekly Statistical Supplement - Extract",
                   "published": wss.get("fx_as_of")}
            fx_as = wss.get("fx_as_of")

            def wk(iso):     # weekly snapshot: the period is that month, paired only with a claim naming it
                if not iso:
                    return {}
                d = dt.date.fromisoformat(iso)
                return {"year": month_period(d.strftime("%b %Y"), claim_text)}
            for key, lab in (("total", "foreign exchange reserves total"), ("fca", "foreign currency assets"),
                             ("gold", "gold reserves")):
                rec = wss.get(key)
                if rec and rec.get("usd_mn"):
                    groups[lab] = [dict({"indicator": lab + " forex", "value": rec["usd_mn"]}, **wk(fx_as))]
                    sources[lab] = dict(src, as_of=f"{fx_as} (week ended)" if fx_as else None)
            for key, lab in (("credit_growth", "scheduled commercial banks bank credit growth year-on-year"),
                             ("deposit_growth", "scheduled commercial banks aggregate deposits growth year-on-year")):
                rec = wss.get(key)
                if rec:
                    groups[lab] = [dict({"indicator": lab, "value": rec["yoy"]}, **wk(wss.get("banks_as_of")))]
                    sources[lab] = dict(src, published=wss.get("banks_as_of"), as_of=wss.get("banks_as_of"))
        return groups, sources


# ================================================================================================== CEA
CEA = "https://cea.nic.in"


class CEASource(GroupedSource):
    name = "cea"
    badge = "CEA"
    publisher = "Central Electricity Authority, Ministry of Power"
    portal = "cea.nic.in"
    keywords = ["cea", "installed capacity", "generation capacity", "power capacity", "installed power", "peak demand",
                "power demand", "electricity demand", "electricity generation", "power generation", "plant load factor",
                "plf", "energy supplied", "energy requirement", "gw", "mw", "megawatt", "gigawatt", "renewable generation",
                "billion units", "electricity"]
    ttl = 24 * 3600

    def status(self) -> dict:
        return {"name": self.name, "configured": not self.offline,
                "detail": "CEA dashboard JSON (installed capacity by state, all-India monthly power-sector performance, "
                          "energy supply position), no key"}

    def groups(self, claim_text: str):
        groups, sources = {}, {}
        cap, f1 = self.cached("installed", lambda: get_json(self.session, f"{CEA}/api/dashboard/installed-capacity",
                                                              self.cfg.timeout, UA_HEADERS))
        if isinstance(cap, dict) and cap.get("categories") and cap.get("data"):
            per = month_period(cap.get("month") or "", claim_text)
            rows = [{"state": s, "year": per, "indicator": "installed capacity", "value": round(float(v), 2)}
                    for s, v in zip(cap["categories"], cap["data"]) if _num(v) is not None]
            rows.append({"state": "All India", "year": per, "indicator": "installed capacity (sum of States/UTs)",
                         "value": round(sum(float(v) for v in cap["data"] if _num(v) is not None), 2)})
            lab = "installed generation capacity power"
            groups[lab] = rows
            self.unit_base[lab] = "MW"
            sources[lab] = {"url": f"{CEA}/api/dashboard/installed-capacity",
                            "title": f"CEA dashboard: installed capacity by State/UT, {cap.get('month')}",
                            "published": None, "as_of": f"{cap.get('month')} (retrieved {f1})"}
        perf, f2 = self.cached("performance", lambda: get_json(self.session, f"{CEA}/api/power-sector-performance",
                                                                 self.cfg.timeout, UA_HEADERS))
        if isinstance(perf, list) and perf:
            latest = max((p for p in perf if isinstance(p, dict) and p.get("year") and p.get("month")),
                         key=lambda p: (int(p["year"]), int(p["month"])), default=None)
            if latest:
                mlabel = f"{str(latest.get('monthName'))[:3]} {latest['year']}"
                per = month_period(mlabel, claim_text)
                src = {"url": f"{CEA}/api/power-sector-performance",
                       "title": f"CEA power sector performance, {latest.get('monthName')} {latest['year']}",
                       "published": None, "as_of": f"{latest.get('monthName')} {latest['year']} (retrieved {f2})"}
                for key, lab, base in (("peakDemandMet", "all india peak demand met", "GW"),
                                       ("energySupplied", "all india energy supplied billion units", None),
                                       ("allIndiaPlf", "all india plant load factor plf", None),
                                       ("renewableGeneration", "renewable energy generation billion units", None),
                                       ("conventionalGeneration", "conventional generation billion units", None)):
                    v = _num(latest.get(key))
                    if v is None:
                        continue
                    groups[lab] = [{"state": "All India", "year": per, "indicator": lab, "value": v}]
                    sources[lab] = src
                    if base:
                        self.unit_base[lab] = base
        return groups, sources


# ================================================================================================= PPAC
PPAC = "https://ppac.gov.in"


def _fy_label(fy: str) -> str:
    a, b = fy.split("-")
    return f"{a}-{b[-2:]}"


def _dmy_iso(s) -> str:
    m = re.match(r"\s*(\d{1,2})-(\d{1,2})-(\d{4})", str(s or ""))
    return f"{m.group(3)}-{int(m.group(2)):02d}-{int(m.group(1)):02d}" if m else ""


def _ppac_rows(result) -> list[dict]:
    items = result.values() if isinstance(result, dict) else (result or [])
    out = []
    for it in items:
        if not isinstance(it, dict):
            continue
        title = norm_ws(re.sub(r"<[^>]+>", " ", str(it.get("title") or it.get("product_title") or "")))
        months = {m: _num(re.sub(r"<[^>]+>", "", str(it.get(m) or ""))) for m in
                  ("april", "may", "june", "july", "august", "september", "october", "november", "december",
                   "january", "february", "march")}
        total = _num(re.sub(r"<[^>]+>", "", str(it.get("total") or "")))
        out.append({"title": title, "months": months, "total": total, "modified": it.get("modified_date")})
    return out


class PPACSource(GroupedSource):
    name = "ppac"
    badge = "PPAC"
    publisher = "Petroleum Planning & Analysis Cell, Ministry of Petroleum and Natural Gas"
    portal = "ppac.gov.in"
    keywords = ["ppac", "crude oil", "crude", "petroleum", "petrol", "diesel", "lpg", "atf", "naphtha", "bitumen",
                "petcoke", "fuel consumption", "oil import", "oil imports", "pmuy", "ujjwala", "ethanol blending",
                "fuel", "hsd", "kerosene", "pol"]
    ttl = 24 * 3600

    def status(self) -> dict:
        return {"name": self.name, "configured": not self.offline,
                "detail": "PPAC import/export and product-wise consumption tables (the site's own JSON calls) + PPAC "
                          "Tracker on the home page, no key"}

    def _fys(self) -> list[str]:
        today = dt.date.today()
        start = today.year if today.month >= 4 else today.year - 1
        return [f"{start - 1}-{start}", f"{start - 2}-{start - 1}"]   # the last two completed years

    def _post(self, path: str, form: dict):
        r = safe_post(self.session, f"{PPAC}{path}", self.cfg.timeout,
                      headers={"X-Requested-With": "XMLHttpRequest", "Referer": f"{PPAC}/"}, data=form)
        if getattr(r, "status_code", 200) >= 400:
            raise FetchError(f"HTTP {r.status_code}")
        body = r.content if hasattr(r, "content") else b""
        return json.loads(body.decode("utf-8", "replace"))

    def groups(self, claim_text: str):
        groups: dict = {}
        sources: dict = {}
        want_value = bool(re.search(r"\$|us\$|usd|dollar|billion", claim_text, re.I))
        for fy in self._fys():
            fyl = _fy_label(fy)
            report_by = "3" if want_value else "1"
            res, fetched = self.cached(f"ie:{fy}:{report_by}", lambda fy=fy, rb=report_by: self._post(
                "/AjaxController/getImportExports", {"financialYear": fy, "reportBy": rb, "pageId": "14"}).get("result"))
            section = "import"
            for row in _ppac_rows(res):
                t = row["title"].lower()
                if "export" in t:
                    section = "export"
                if row["total"] in (None, 0) or not row["months"].get("march"):
                    continue
                name = re.sub(r"[*^@!$#%&]+", "", t).strip()
                name = {"ms": "ms petrol", "hsd": "hsd diesel", "sko": "sko kerosene", "atf": "atf aviation turbine fuel"}.get(name, name)
                if name.startswith(("total", "net", "product import", "product export")):
                    lab = name.replace("product import", "petroleum product import")
                else:
                    lab = f"{name} {section}"
                if name == "crude oil":
                    lab = "crude oil import"
                lab = re.sub(r"\s+", " ", lab)
                unit = "US$ million" if want_value else "'000 tonnes"
                groups.setdefault(lab, []).append({"year": fyl, "indicator": lab, "value": row["total"], "unit": unit})
                if not want_value:
                    self.unit_base[lab] = "TMT"
                else:
                    self.unit_base[lab] = "USD_mn"
                sources[lab] = {"url": f"{PPAC}/import-export", "title": f"PPAC Import/Export, {fy} ({unit})",
                                "published": _dmy_iso(row.get("modified")) or None,
                                "as_of": f"updated {_dmy_iso(row.get('modified'))}; retrieved {fetched}" if _dmy_iso(row.get("modified"))
                                else f"retrieved {fetched}"}
            cres, cf = self.cached(f"cons:{fy}", lambda fy=fy: self._post(
                "/AjaxController/getConsumptionPetroleumProductsData",
                {"financialYear": fy, "reportBy": "1", "pageId": "43"}).get("result"))
            for row in _ppac_rows(cres):
                t = row["title"].lower()
                if row["total"] in (None, 0) or not row["months"].get("march") or len(t) > 40:
                    continue
                alias = {"ms": "ms petrol", "hsd": "hsd diesel", "sko": "sko kerosene", "atf": "atf aviation turbine fuel",
                         "lpg": "lpg cooking gas", "fo & lshs": "fuel oil fo lshs"}.get(t, t)
                lab = "petroleum products consumption total" if t == "total" else f"{alias} consumption"
                groups.setdefault(lab, []).append({"year": fyl, "indicator": lab, "value": row["total"]})
                self.unit_base[lab] = "TMT"
                sources[lab] = {"url": f"{PPAC}/consumption/products-wise", "title": f"PPAC product-wise consumption, {fy} ('000 tonnes)",
                                "published": _dmy_iso(row.get("modified")) or None,
                                "as_of": f"updated {_dmy_iso(row.get('modified'))}; retrieved {cf}" if _dmy_iso(row.get("modified"))
                                else f"retrieved {cf}"}
        tr, tf = self.cached("tracker", lambda: parse_ppac_home(_text_of_html(
            fetch_bytes(self.session, f"{PPAC}/", self.cfg.timeout, 6 * 2 ** 20)[0])))
        for lab, rec in (tr or {}).items():
            groups[lab] = [dict({"indicator": lab, "value": rec["value"]}, **({"state": rec["state"]} if rec.get("state") else {}))]
            if rec.get("base"):
                self.unit_base[lab] = rec["base"]
            sources[lab] = {"url": f"{PPAC}/", "title": "PPAC home page (PPAC Tracker / Important News)",
                            "published": rec.get("as_of"), "as_of": rec.get("as_of") or f"retrieved {tf}"}
        return groups, sources


def parse_ppac_home(text: str) -> dict:
    out = {}
    for fuel in ("Petrol", "Diesel"):
        m = re.search(rf"RSP of {fuel} in Delhi as per IOCL outlet as on (\d{{1,2}})-([A-Za-z]+)-(\d{{4}}), Rs\. ?([\d.]+)", text)
        if m:
            try:
                iso = dt.datetime.strptime(f"{m.group(1)} {m.group(2)} {m.group(3)}", "%d %B %Y").date().isoformat()
            except ValueError:
                iso = None
            out[f"retail selling price of {fuel.lower()} in delhi rs per litre"] = {"value": float(m.group(4)), "as_of": iso,
                                                                                  "state": "Delhi"}
    m = re.search(r"Ethanol Blending\s+([\d.]+)%\s*ESY:\s*([A-Za-z]+ \d{4}\s*-\s*[A-Za-z]+ \d{4})", text)
    if m:
        out["ethanol blending in petrol per cent"] = {"value": float(m.group(1)), "as_of": f"ESY {m.group(2).strip()}"}
    for lab, rx in (("pmuy ujjwala lpg connections", r"PMUY Connections\s+([\d,.]+)\s*lakhs\s*As on (\d{2}\.\d{2}\.\d{4})"),
                    ("active lpg domestic connections", r"Active LPG Domestic Connections\s+([\d,.]+)\s*lakhs\s*As on (\d{2}\.\d{2}\.\d{4})")):
        m = re.search(rx, text)
        if m:
            d, mo, y = m.group(2).split(".")
            out[lab] = {"value": float(m.group(1).replace(",", "")), "as_of": f"{y}-{mo}-{d}", "base": "lakh"}
    return out


# ================================================================================================== JJM
JJM_PAGE = "https://ejalshakti.gov.in/jjmreport/JJMIndia.aspx"


def _jjm_enc(s: str, n: int = 1) -> str:
    """The dashboard's encodeTxt(): JavaScript escape(), shift every character code by n, escape() again, append n."""
    from urllib.parse import quote
    safe = "@*_+-./"
    shifted = "".join(chr(ord(c) + n) for c in quote(str(s), safe=safe))
    return quote(shifted, safe=safe) + str(n)


class JJMSource(GroupedSource):
    name = "jjm"
    badge = "JJM"
    publisher = "Jal Jeevan Mission, Department of Drinking Water and Sanitation, Ministry of Jal Shakti"
    portal = "ejalshakti.gov.in"
    keywords = ["jal jeevan", "jjm", "har ghar jal", "tap water", "tap connection", "tap connections", "fhtc",
                "household tap", "piped water", "drinking water"]
    ttl = 24 * 3600

    def status(self) -> dict:
        return {"name": self.name, "configured": not self.offline,
                "detail": "JJM dashboard state table (households with tap water, rural households, %), no key"}

    def _table(self):
        def get():
            obj = {k: _jjm_enc("0") for k in ("StCode11", "Cat", "SubCat", "Param")}
            r = safe_post(self.session, f"{JJM_PAGE}/Bind_table_graph", self.cfg.timeout,
                          headers={"Content-Type": "application/json; charset=utf-8", "Referer": JJM_PAGE,
                                   "Origin": "https://ejalshakti.gov.in"}, data=json.dumps(obj))
            if getattr(r, "status_code", 200) >= 400:
                raise FetchError(f"HTTP {r.status_code}")
            d = json.loads(r.content.decode("utf-8", "replace")).get("d")
            if not isinstance(d, list) or not d:
                raise FetchError("unexpected JJM response")
            return d
        return self.cached("table", get)

    def groups(self, claim_text: str):
        groups, sources = {}, {}
        d, fetched = self._table()
        if not d:
            return groups, sources
        src = {"url": JJM_PAGE, "title": "Jal Jeevan Mission dashboard, State/UT table", "published": None,
               "as_of": f"retrieved {fetched} (dashboard updates daily)"}
        tap, tot, pct, base = [], [], [], []
        for r in d:
            st = r.get("Name") or ""
            v, t, p = _num(r.get("Value")), _num(r.get("Total")), _num(r.get("Per"))
            if v is not None:
                tap.append({"state": st, "indicator": "rural households with tap water connections", "value": v})
            if t is not None:
                tot.append({"state": st, "indicator": "total rural households", "value": t})
            if p is not None:
                pct.append({"state": st, "indicator": "rural households with tap water connections per cent", "value": p})
            b = _num(r.get("HCPWS_01042019"))
            if b is not None:
                base.append({"state": st, "year": "2019", "indicator": "rural households with tap water at the start of the mission",
                             "value": b})
        if tap and tot:
            sv, stt = sum(x["value"] for x in tap), sum(x["value"] for x in tot)
            tap.append({"state": "All India", "indicator": "rural households with tap water connections (sum of States/UTs)", "value": sv})
            tot.append({"state": "All India", "indicator": "total rural households (sum of States/UTs)", "value": stt})
            pct.append({"state": "All India", "indicator": "rural households with tap water connections per cent (from the sum of States/UTs)", "value": round(100 * sv / stt, 2)})
        if base:
            base.append({"state": "All India", "year": "2019", "indicator": "rural households with tap water at the start of the mission (sum of States/UTs)",
                         "value": sum(x["value"] for x in base)})
        for lab, rows, b in (("rural households with tap water connections number", tap, "count"),
                             ("total rural households", tot, "count"),
                             ("share of rural households with tap water connections per cent", pct, None),
                             ("households with tap water connections in 2019 at the start of jal jeevan mission", base, "count")):
            if rows:
                groups[lab] = rows
                sources[lab] = src
                if b:
                    self.unit_base[lab] = b
        return groups, sources

    def match(self, claim_text: str, numbers: list) -> list[dict]:
        # a percentage figure is matched against the per-cent table only, a count against the counts only
        pc = [n for n in numbers if "%" in n.raw or "per cent" in n.raw.lower()]
        cnt = [n for n in numbers if n not in pc]
        out = []
        if pc:
            out += super().match(claim_text, pc, label_ok=lambda k: "per cent" in k)
        if cnt:
            out += super().match(claim_text, cnt, label_ok=lambda k: "per cent" not in k)
        return dedupe_findings(out)
