"""Query planning (v0.3): from a claim derive indicator words, geography, period and unit, then route it to the
retrievers most likely to hold the evidence.

  numbers                -> official data first. v0.4: the ministry source whose subject the claim names is tried
                            before the general catalogues: RBI (rates, forex reserves, bank credit), CEA (power
                            capacity, demand, generation), PPAC (crude imports, fuel consumption, fuel prices), JJM
                            (tap-water connections); then MoSPI eSankhyiki, data.gov.in, NDAP data (with a token).
                            The NDAP catalogue is searched for every figure to name the dataset to cite (pointer only).
                            (+ PIB / Parliament when the figure is about a scheme, mission or ministry)
  scheme / policy facts  -> PIB press releases, Parliament answers, government reports
  studies / research     -> OpenAlex, Semantic Scholar and arXiv (abstracts); Shodhganga when a thesis is named;
                            Crossref/OpenAlex/Semantic Scholar/arXiv for cited DOIs and arXiv ids
  always                 -> the local document index; web search when a key is set

Retrievers run in parallel with a per-claim time budget, so a 2-page draft checks in about a minute even when a
source is slow; a source that times out is listed as such and the claim fails closed.
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field

from .retrievers.tables import claim_geo, claim_periods

SCHEME_RX = re.compile(r"\b(mission|yojana|scheme|programme|program|abhiyan|policy|act|bill|ministry|minister|government|"
                       r"launched|announced|introduced|approved|cabinet|lok sabha|rajya sabha|parliament|pradhan mantri|pm[- ]\w+|"
                       r"portal|initiative|guidelines|notified)\b", re.I)
STUDY_RX = re.compile(r"\b(study|studies|research|researchers|paper|journal|meta-analysis|trial|et al\.?|peer[- ]reviewed|"
                      r"scientists?|evidence (?:shows|suggests))\b", re.I)
REPORT_RX = re.compile(r"\b(economic survey|budget|cag|audit|niti aayog|annual report|white paper|census|report|bulletin|"
                       r"press note|rbi)\b", re.I)
UNIT_RX = re.compile(r"(%|per ?cent|percentage points?|₹|rs\.?|crore|lakh|million|billion|tonnes?|km|mw|gw|households?|"
                     r"persons?|people|students?|schools?|universities)", re.I)


THESIS_RX = re.compile(r"\b(thesis|theses|ph\.?\s?d|doctoral|dissertation|shodhganga)\b", re.I)


def _source_keywords() -> dict:
    from .retrievers.ministry import CEASource, JJMSource, PPACSource, RBISource
    return {c.name: c.keywords for c in (RBISource, CEASource, PPACSource, JJMSource)}


def ministry_routes(text: str) -> list[str]:
    """Ministry sources whose keywords the claim names, most hits first."""
    from .retrievers.official_api import kw_hits
    scored = [(kw_hits(text, kws), name) for name, kws in _source_keywords().items()]
    return [n for h, n in sorted(scored, key=lambda x: -x[0]) if h > 0]


@dataclass
class Plan:
    indicator: str = ""
    geography: str = "India"
    period: list = field(default_factory=list)
    unit: str = ""
    routes: list = field(default_factory=list)       # retriever names, in priority order
    data_matchers: list = field(default_factory=list)
    why: list = field(default_factory=list)

    def to_dict(self):
        return asdict(self)


def plan_claim(claim, available: set) -> Plan:
    from .retrievers.base import terms
    text = claim.text
    p = Plan()
    geo = claim_geo(text)
    p.geography = "India" if geo == "india" else geo.title()
    p.period = sorted(claim_periods(text))
    m = UNIT_RX.search(text)
    p.unit = m.group(1).lower() if m else ""
    p.indicator = " ".join(sorted(terms(re.sub(r"[\d.,%₹]+", " ", text)))[:8])
    numeric = bool(claim.numbers) and claim.type != "opinion"
    scheme = bool(SCHEME_RX.search(text))
    study = bool(STUDY_RX.search(text))
    report = bool(REPORT_RX.search(text))
    if numeric:
        mins = [x for x in ministry_routes(text) if x in available]
        from .plugins import TRUST_OF, routes_for
        plug = routes_for(text, available)        # v0.5: the user's plug-in sources, routed by their keywords
        trusted = [x for x in plug if TRUST_OF.get(x) != "other"]
        state = ["state-data"] if "state-data" in available and _state_data_relevant(text) else []
        p.data_matchers += mins + trusted + state + [x for x in ("mospi-catalog", "datagovin-catalog")
                                                     if x in available]
        p.data_matchers += [x for x in plug if x not in trusted]
        if plug:
            p.why.append("plug-in source(s) for this subject: " + ", ".join(x.split(":", 1)[1] for x in plug))
        p.why.append("figure: official statistics first" + (f" ({', '.join(m.upper() for m in mins)} for this subject)" if mins else ""))
    routes = ["docs"]
    if scheme or not numeric:
        routes += ["pib", "parliament"]
        p.why.append("scheme/policy statement: PIB releases and Parliament answers" if scheme else "factual statement")
    elif numeric:
        routes += ["parliament"]        # answers in Parliament often state scheme and state-level figures
    if report:
        routes.append("reports")
        p.why.append("mentions a report: official report listings")
    if numeric:
        routes.append("ndap")
        p.why.append("NDAP catalogue: the dataset to cite (pointer, never support on its own)")
    if study or THESIS_RX.search(text):
        routes += ["openalex", "semanticscholar", "arxiv"]
        if THESIS_RX.search(text):
            routes.append("shodhganga")
        p.why.append("research claim: OpenAlex, Semantic Scholar and arXiv abstracts" +
                     ("; Shodhganga theses" if THESIS_RX.search(text) else ""))
    routes.append("web")
    if "datagovin" in available:
        routes.append("datagovin")       # hand-mapped resources from truthlens.toml
    if not getattr(claim, "_fallback", True):
        # v0.5.2: outside a document's most important claims, no slow general fallbacks: PIB, Parliament answers,
        # report listings and the NDAP catalogue are asked only for the top claims (TRUTHLENS_FALLBACK_CLAIMS)
        dropped = [r for r in routes if r in FALLBACK_ROUTES]
        routes = [r for r in routes if r not in FALLBACK_ROUTES]
        if dropped:
            p.why.append("lower-priority claim in a long document: general fallbacks (" + ", ".join(dict.fromkeys(dropped))
                         + ") not asked")
    p.routes = [r for r in dict.fromkeys(routes) if r in available]
    return p


FALLBACK_ROUTES = {"pib", "parliament", "reports", "ndap"}


def _state_data_relevant(text: str) -> bool:
    from .retrievers.official_api import kw_hits
    from .retrievers.state_data import StateDataSource
    return kw_hits(text, StateDataSource.keywords) > 0
