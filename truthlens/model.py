"""v0.2 data model: claims, evidence and per-claim verdicts."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Optional

SUPPORTED = "SUPPORTED"
PARTLY = "PARTLY SUPPORTED"
CONTRADICTED = "CONTRADICTED"
UNVERIFIED = "UNVERIFIED"
SKIPPED = "SKIPPED"
VERDICTS = [CONTRADICTED, PARTLY, UNVERIFIED, SUPPORTED]
SEVERITY = {CONTRADICTED: 4, PARTLY: 3, UNVERIFIED: 2, SUPPORTED: 1, SKIPPED: 0}

CLAIM_TYPES = ("numeric", "citation", "entity", "opinion")

# v0.4.1: sources whose data path has only been tested on synthetic or rate-limited fixtures, never against the live
# service from our network. Their evidence carries a small "unverified source" tag.
NOT_LIVE_VERIFIED = {
    "datagovin": "data.gov.in (not reachable from our network; synthetic fixtures only)",
    "datagovin-catalog": "data.gov.in catalogue rows (synthetic fixtures only)",
    "semanticscholar": "Semantic Scholar (answered HTTP 429 only; hits from a synthetic fixture)",
    "shodhganga": "Shodhganga (JavaScript bot challenge; OpenSearch answer from a synthetic fixture)",
}


@dataclass
class Evidence:
    retriever: str              # curated | worldbank | mospi | datagovin | docs | web | citation
    source_url: str
    title: str
    snippet: str                # the quoted passage (verbatim from the source, whitespace-normalised)
    date: Optional[str] = None  # publication or data date as given by the source
    publisher: str = ""
    page: Optional[int] = None
    official: bool = False
    score: float = 0.0
    kind: str = "passage"       # passage | datapoint | search_snippet | metadata
    meta: dict = field(default_factory=dict)
    id: str = ""
    source_type: str = ""       # badge: data.gov.in | MoSPI | PIB | Lok Sabha | Rajya Sabha | Paper | Thesis | Report | NDAP | RBI |
                                # CEA | PPAC | JJM | India-WRIS | HMIS | Official data | Web | Cited
    as_of: Optional[str] = None  # "data as of": release / updated date of the dataset or document (v0.3)

    def to_dict(self):
        d = asdict(self)
        if not d.get("source_type"):
            d["source_type"] = source_type_for(self)
        d["data_as_of"] = data_as_of(d)
        # v0.4.1: the deciding cell / sentence, short (the full passage stays in `snippet`)
        cell = (self.meta or {}).get("cell")
        d["quote"] = cell or (self.snippet if len(self.snippet or "") <= 220 else self.snippet[:200].rstrip() + "…")
        d["not_live_verified"] = self.retriever in NOT_LIVE_VERIFIED or (self.meta or {}).get("synthetic", False)
        return d


def _human_date(iso: str) -> str:
    import datetime as _dt
    try:
        d = _dt.date.fromisoformat(iso[:10])
    except ValueError:
        return iso
    return f"{d.day} {d.strftime('%B')} {d.year}"


def data_as_of(ev: dict) -> str:
    """'Data as of' text for one evidence item (a dict as in reports): the release, update or retrieval date of the
    dataset or document, in words. Empty when the source gives no date."""
    import re as _re
    raw = str(ev.get("as_of") or "").strip()
    if not raw:
        raw = str(ev.get("date") or "").strip()
    if not raw:
        return ""
    m = _re.search(r"\b((?:19|20)\d{2}-\d{2}-\d{2})", raw)
    if not m:
        return raw[:80]
    when = _human_date(m.group(1))
    period = _re.search(r"latest period in API:\s*([^;]+)", raw)
    if raw.lower().startswith("retrieved"):
        return f"{when} (retrieved live" + (f"; latest period {period.group(1).strip()})" if period else ")")
    if raw.lower().startswith("updated"):
        return f"{when} (dataset updated)"
    return when if raw.startswith(m.group(1)) else raw[:80]


def source_type_for(e: "Evidence") -> str:
    """Badge text. The retriever decides first (a MoSPI release hosted on static.pib.gov.in is MoSPI's data, read by
    the curated checker), then the URL."""
    r, u = e.retriever, (e.source_url or "").lower()
    pub = (getattr(e, "publisher", "") or "").lower()
    if r == "parliament" or (not r and ("sansad.in" in u or "rajyasabha" in u or "loksabha" in u)):
        house = (e.meta or {}).get("house") or ""
        if house in ("Lok Sabha", "Rajya Sabha"):
            return house
        if "rajyasabha" in u or "/rs/" in u:
            return "Rajya Sabha"
        if "loksabha" in u or "/ls/" in u or "lsapps" in u:
            return "Lok Sabha"
        return "Parliament"
    by_retriever = {"datagovin": "data.gov.in", "mospi": "MoSPI", "mospi-catalog": "MoSPI", "pib": "PIB",
                    "openalex": "Paper", "worldbank": "World Bank", "reports": "Report", "web": "Web",
                    "citation": "Cited source", "ndap": "NDAP", "rbi": "RBI", "cea": "CEA",
                    "ppac": "PPAC", "jjm": "JJM", "indiawris": "India-WRIS", "hmis": "HMIS", "semanticscholar": "Paper",
                    "arxiv": "Paper", "shodhganga": "Thesis"}
    if r in by_retriever:
        return by_retriever[r]
    if r == "curated":
        return "MoSPI" if ("mospi" in pub or "national statistics office" in pub) else "Official data"
    if "data.gov.in" in u:
        return "data.gov.in"
    for host, badge in (("ndap.niti.gov.in", "NDAP"), ("ndapapi.com", "NDAP"), ("rbi.org.in", "RBI"), ("cea.nic.in", "CEA"),
                        ("ppac.gov.in", "PPAC"), ("ejalshakti.gov.in", "JJM"), ("jaljeevanmission.gov.in", "JJM"),
                        ("indiawris.gov.in", "India-WRIS"), ("hmis.mohfw.gov.in", "HMIS"),
                        ("shodhganga.inflibnet.ac.in", "Thesis"), ("arxiv.org", "Paper")):
        if host in u:
            return badge
    if "mospi.gov.in" in u:
        return "MoSPI"
    if "pib.gov.in" in u:
        return "PIB"
    if "sansad.in" in u or "rajyasabha" in u or "loksabha" in u:
        return "Rajya Sabha" if "rajyasabha" in u else "Lok Sabha"
    if e.kind == "metadata":
        return "Paper"
    if r == "docs":
        return "Your documents" if u.startswith("file:") else "Report"
    return r or "source"


@dataclass
class Claim:
    id: str
    sentence_id: str
    sentence: str
    text: str                    # the atomic claim (equal to the sentence for the rule-based extractor)
    type: str                    # numeric | citation | entity | opinion
    location: str
    numbers: list = field(default_factory=list)     # raw number strings
    citations: list = field(default_factory=list)   # URLs / DOIs / reference markers
    entities: list = field(default_factory=list)
    extractor: str = "rules"
    hedged: bool = False         # v0.4.1: an opinion-marked sentence whose factual core is checked
    checkable: bool = True       # v0.5.2: False for descriptive text (objectives, procedures, definitions)
    note: str = ""               # v0.4.1: e.g. "contains a factual claim"
    not_claim: str = ""          # v0.5.3: why it is not a checkable claim: heading | table | rule | plan | contact | description

    def to_dict(self):
        return asdict(self)


@dataclass
class ClaimResult:
    claim: Claim
    verdict: str = UNVERIFIED
    confidence: str = "low"          # high | medium | low
    method: str = ""                 # deterministic-numeric | llm-judge:<provider> | heuristic | skipped
    rationale: str = ""
    evidence: list = field(default_factory=list)       # list[Evidence]
    quotes: list = field(default_factory=list)         # [{"evidence_id", "quote"}]
    numbers: list = field(default_factory=list)        # v0.1 numeric findings (dicts)
    citation_checks: list = field(default_factory=list)
    warnings: list = field(default_factory=list)       # {code, severity, message}
    suggested_fix: Optional[str] = None
    fix_source: Optional[str] = None
    plan: dict = field(default_factory=dict)           # v0.3 query plan: indicator, geography, period, unit, routes
    consulted: list = field(default_factory=list)      # v0.3 sources consulted for this claim and what each returned
    failed_part: str = ""                              # v0.4.1: which figure/clause failed (CONTRADICTED / PARTLY)
    change: dict = field(default_factory=dict)         # v0.4.1: change-calculator result (parts, verdict)
    live_limits: dict = field(default_factory=dict)    # v0.5.1: sources cut off (breaker) / ran out of time (deadline)
    # v0.5.2: why an UNVERIFIED claim could not be checked: no_data | no_response | quick | deadline ("" otherwise)
    unchecked_reason: str = ""
    priority: int = 0                                  # v0.5.2: importance rank used to order the work (higher first)

    def to_dict(self):
        d = asdict(self)
        d["claim"] = self.claim.to_dict()
        d["evidence"] = [e.to_dict() if isinstance(e, Evidence) else e for e in self.evidence]
        return d


@dataclass
class Sentence:
    id: str
    text: str
    location: str
    block: int
    claims: list = field(default_factory=list)   # claim ids
    verdict: Optional[str] = None                # worst verdict of its claims, None when no claim

    def to_dict(self):
        return asdict(self)
