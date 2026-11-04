"""v0.6: share-of-India maths, hectares, the DATED verdict, compare two versions, more AI providers (mocked HTTP only),
request sentences, and the couldn't-check chips. No network."""
import json

import pytest

from truthlens.claims import checkable_numbers, non_claim_reason
from truthlens.config import Config, redact, use_keys
from truthlens.pipeline import Pipeline
from truthlens.readers import read_text
from truthlens.retrievers.state_data import DOC_STATE, DOC_YEAR, StateDataSource, document_year


@pytest.fixture(scope="module")
def P():
    return Pipeline(Config.load(offline=True), llm=None)


@pytest.fixture(scope="module")
def S():
    return StateDataSource(Config.load(offline=True))


def _match(S, text, state=None, year=None):
    t1, t2 = DOC_STATE.set(state), DOC_YEAR.set(year)
    try:
        return {f["claimed"]: f for f in S.match(text, checkable_numbers(text))}
    finally:
        DOC_STATE.reset(t1)
        DOC_YEAR.reset(t2)


UP_2020 = ("Uttar Pradesh accounts for 16.17 % of the country’s population and has 20.80 % of country’s renewable "
           "water resources with 7.33 % of country’s land area.")     # UP State Water Policy 2020 (draft), para 1


# ---- 1. share of India ---------------------------------------------------------------------------------------------
def test_up_share_of_population_and_area(S):
    fs = _match(S, UP_2020)
    pop, area = fs["16.17 %"], fs["7.33 %"]
    # 199,812,341 / 1,210,854,977 = 16.50% (Census 2011); the draft gives no year, so it differs but is not wrong
    assert pop["verdict"] == "UNVERIFIED" and pop["official"]["display"] == "16.50%"
    assert "Census 2011" in pop["reason"] and "comparison year is 2011" in pop["reason"]
    assert "All India 1,210,854,977" in pop["reason"]          # the All India row, never a sum of States
    # 240,928 / 3,287,469 = 7.33%
    assert area["verdict"] == "MATCH" and area["official"]["display"] == "7.33%"
    assert "20.80 %" not in fs                                  # renewable water resources: no dataset


def test_up_share_end_to_end_is_partly_supported_not_wrong(P):
    rep = P.run(read_text(UP_2020), "t", mode="quick")
    c = rep["claims"][0]
    assert c["verdict"] == "PARTLY SUPPORTED"
    assert rep["summary"]["contradicted"] == 0


def test_share_named_census_2011_that_differs_is_contradicted(S):
    f = _match(S, "Uttar Pradesh accounts for 16.17% of India's population as per Census 2011.")["16.17%"]
    assert f["verdict"] == "MISMATCH" and f["official"]["display"] == "16.50%"


def test_share_named_earlier_census_is_dated(S):
    f = _match(S, "Uttar Pradesh accounts for 16.16% of India's population as per Census 2001.")["16.16%"]
    assert f["verdict"] == "DATED" and "2001" in f["reason"]


def test_share_forms(S):
    ka = _match(S, "The State of Karnataka covers an area of 1,91,791 Sq. Kms., i.e., 5.83% of the area of India.")
    assert ka["5.83%"]["verdict"] == "MATCH" and ka["1,91,791"]["verdict"] == "MATCH"
    kl = _match(S, "Kerala is one of the smallest states in India (38.863 sq.km) covering merely 1.3 per cent of the "
                   "total area of the country.")        # Kerala SPB report: 38,852 / 3,287,469 = 1.18%
    assert kl["1.3 per cent"]["verdict"] == "UNVERIFIED" and kl["1.3 per cent"]["official"]["display"] == "1.18%"


def test_share_uses_document_state_only_when_sentence_says_the_state(S):
    assert _match(S, "The State accounts for 7.33% of the country's land area.", state="uttar pradesh")["7.33%"][
        "verdict"] == "MATCH"
    assert not _match(S, "Rural areas account for 7.33% of the country's land area.", state="uttar pradesh")


def test_no_share_for_india_itself_or_two_states(S):
    assert not _match(S, "India accounts for 2.4% of the world's land area.")
    assert not _match(S, "Uttar Pradesh and Bihar account for 16.50% of the country's population.")


# ---- 2. hectares and boundaries: DATED ------------------------------------------------------------------------------
UP_1999 = ("7.1 Out of about the 29.44 million ha. of geographical area of the state 7.336 million ha has been "
           "recognised as flood prone.")             # UP State Water Policy 1999, para 7.1


def test_up_1999_area_is_undivided_up(S):
    fs = _match(S, UP_1999, state="uttar pradesh", year=1999)
    f = fs["29.44 million"]
    # 240,928 + 53,483 = 294,411 sq km = 29.44 million ha (1 sq km = 100 ha)
    assert f["verdict"] == "DATED"
    assert "294,411" in f["reason"] and "Uttarakhand" in f["reason"] and "9 November 2000" in f["reason"]
    # the flood-prone area is not the State's area: never matched, contradicted or dated
    assert fs.get("7.336 million", {}).get("verdict", "UNVERIFIED") == "UNVERIFIED"


def test_hectares_conversion_matches_today(S):
    assert _match(S, "The geographical area of Uttar Pradesh is 24.09 million ha.")["24.09 million"]["verdict"] == "MATCH"
    assert _match(S, "Uttar Pradesh has a geographical area of 240.93 lakh hectares.")["240.93 lakh"]["verdict"] == "MATCH"


@pytest.mark.parametrize("text,new_state", [
    ("The geographical area of Madhya Pradesh is 44.34 million ha.", "Chhattisgarh"),    # 308,252 + 135,192
    ("The geographical area of Bihar is 1,73,879 sq km.", "Jharkhand"),                 # 94,163 + 79,716
    ("Andhra Pradesh has a geographical area of 2,75,045 sq km.", "Telangana"),         # Census 2011 row, undivided
])
def test_other_splits_are_dated(S, text, new_state):
    f = list(_match(S, text).values())[0]
    assert f["verdict"] == "DATED" and new_state in f["reason"]


def test_low_overlap_area_is_not_contradicted(S):
    f = _match(S, "The State of Karnataka covers an area of 2,50,000 Sq. Kms. as per Census 2011.")["2,50,000"]
    assert f["verdict"] == "UNVERIFIED"


def test_groundwater_figure_for_an_earlier_year_is_dated(S):
    f = _match(S, "In 2009 the annual ground water extraction for all uses in Uttar Pradesh was 49.48 BCM.")["49.48"]
    assert f["verdict"] == "DATED" and "2025" in f["reason"] and "2009" in f["reason"]


def test_undated_figure_in_an_older_document_is_dated(S):
    f = _match(S, "The annual ground water extraction for all uses in Uttar Pradesh is 40.95 BCM.", year=2013)["40.95"]
    assert f["verdict"] == "DATED" and "2013" in f["reason"]
    # the same sentence in a document from after the data: not dated (may be a newer estimate), never wrong
    g = _match(S, "The annual ground water extraction for all uses in Uttar Pradesh is 40.95 BCM.", year=2026)["40.95"]
    assert g["verdict"] != "MISMATCH"


def test_document_year():
    assert document_year(["Uttar Pradesh State Water Policy, 1999", "PREAMBLE"]) == 1999
    assert document_year(["Draft", "Uttar Pradesh State Water Policy, 2020"]) == 2020
    assert document_year(["(Issued by Government Order no.-280/62-1-2013-7WP-2004, TC-III)"]) == 2013
    assert document_year(["Table of Contents", "1. History"]) is None


def test_dated_in_summary_and_reports(P):
    from truthlens.report_v2 import to_claims_csv, to_html, to_markdown
    blocks = read_text("Uttar Pradesh State Water Policy, 1999\n\n" + "\n\n".join(
        ["Uttar Pradesh is a large State."] * 4 + [UP_1999]))
    rep = P.run(blocks, "up1999.txt", mode="quick")
    s = rep["summary"]
    assert s["dated"] == 1 and s["contradicted"] == 0 and s["verdicts"]["DATED"] == 1
    assert "dated" in s["headline"] and rep["meta"]["document_year"] == 1999
    assert "DATED" in to_markdown(rep) and "Dated" in to_html(rep) and "DATED" in to_claims_csv(rep)
    assert any(r["reason"] == "dated" for r in rep["claims_to_cite"])
    assert json.loads(json.dumps(rep, default=str))["summary"]["dated"] == 1


# ---- 5. request sentences --------------------------------------------------------------------------------------------
@pytest.mark.parametrize("text", [
    "Please check the 2011 population figure of 199 million for Uttar Pradesh.",
    "Kindly verify that the State had 97,814 villages in 2011.",
    "Refer to Table 3 for the 2011 population of 199 million.",
    "Verify village-wise water supplied by the Private Operator.",     # Andhra Pradesh O&M SOP
    "Please see Annex -2 for a schematic representation of the Field Level Reorganization.",
])
def test_requests_are_not_facts(text):
    assert non_claim_reason(text) == "request"


@pytest.mark.parametrize("text", [
    "Please note that the population of Uttar Pradesh was 199,812,341 in 2011.",
    "Check dams numbered 5,000 in Uttar Pradesh in 2011.",
    "Share of agriculture in water use was 80% in 2011.",
])
def test_facts_that_look_like_requests_are_kept(text):
    assert non_claim_reason(text) != "request"


# ---- 3. compare two versions -----------------------------------------------------------------------------------------
OLD = """1. PREAMBLE

1.1 The state is endowed with bountiful water resources which were considered abundant in the past.

1.2 About 43.2 BCM (35 m.a.f.) is the quantity which can not be utilised at present.

1.3 State has a total of about 20 mha. of culturable land out of which about 17.4 mha. is presently under agriculture.

1.4 The State shall set up a River Basin Authority for every basin within five years.

Thus there remains only about 22.2 BCM (18.0 m.a.f). Which can be utilised for future irrigation projects after reserving about 24.7 BCM for drinking needs.
"""
NEW = """1. PREAMBLE

The State of Uttar Pradesh is endowed with bountiful water resources which were considered abundant in the past.

About 43.2 BCM is the quantity which cannot be utilized at present.

4.3 State has a total of 19.13 mha of culturable land out of which about 16.5 mha. is presently under agriculture.

Thus there remains only about 22.2 BCM, which can be utilized for future irrigation projects after reserving about 24.67 BCM for drinking needs.

8. ADAPTATION TO CLIMATE CHANGE

Climate change is expected to increase the variability of rainfall across all the river basins of the State.
"""


def test_compare_blocks():
    from truthlens.compare import compare_blocks, to_html, to_markdown
    rep = compare_blocks(read_text(OLD), read_text(NEW), "old.txt", "new.txt")
    s = rep["summary"]
    near = [r["new"] for r in rep["near_copies"]]
    assert any("43.2 BCM" in t for t in near)
    assert any("22.2 BCM" in t for t in near)                 # two old sentences joined into one
    assert any(r.get("note") == "two old sentences joined into one" for r in rep["near_copies"])
    changes = [c for r in rep["number_changes"] for c in r["numbers"]["changed"]]
    assert {"old": "20 mha", "new": "19.13 mha"} in changes and {"old": "17.4 mha", "new": "16.5 mha"} in changes
    assert {"old": "24.7 BCM", "new": "24.67 BCM"} in changes
    assert s["dropped_commitments"] == 1 and "River Basin Authority" in rep["dropped"][0]["text"]
    assert [x["heading"] for x in rep["new_sections"]] == ["8. ADAPTATION TO CLIMATE CHANGE"]
    assert "Near-copied sentences" in to_markdown(rep) and "<del>" in to_html(rep)


def test_compare_number_changes_ignore_section_numbers():
    from truthlens.compare import number_changes
    ch = number_changes("4.1 A river basin should be considered as a unit.", "13.3 A river basin should be considered as a unit.")
    assert ch == {"changed": [], "removed": [], "added": []}
    ch = number_changes("27.8 BCM (22.5 m.a.f.) of surface water shall get utilised.", "27.8 BCM of surface water shall get utilized.")
    assert ch["changed"] == [] and ch["removed"] == ["22.5 m.a.f."]


def test_compare_cli_and_api(tmp_path, capsys):
    from fastapi.testclient import TestClient
    from truthlens import api
    from truthlens.cli import main
    (tmp_path / "old.txt").write_text(OLD)
    (tmp_path / "new.txt").write_text(NEW)
    out = tmp_path / "c.json"
    assert main(["compare", str(tmp_path / "old.txt"), str(tmp_path / "new.txt"), "-f", "json", "-o", str(out)]) == 0
    assert json.loads(out.read_text())["kind"] == "compare"
    c = TestClient(api.app)
    r = c.post("/compare/file?format=json", files={"old": ("old.txt", OLD.encode()), "new": ("new.txt", NEW.encode())})
    assert r.status_code == 200 and r.json()["summary"]["near_copies"] >= 3
    r = c.post("/compare/file?format=html", files={"old": ("old.txt", OLD.encode()), "new": ("new.txt", NEW.encode())})
    assert r.status_code == 200 and "Near-copied" in r.text
    r = c.post("/compare/file", files={"old": ("old.exe", b"x"), "new": ("new.txt", NEW.encode())})
    assert r.status_code == 415


# ---- 4. AI providers (mocked HTTP only) ------------------------------------------------------------------------------
class _Resp:
    def __init__(self, status, payload):
        self.status_code, self._p = status, payload
        self.text = json.dumps(payload)

    def json(self):
        return self._p


class _Sess:
    def __init__(self, answers):
        self.answers, self.calls = list(answers), []

    def post(self, url, headers=None, json=None, timeout=None, allow_redirects=True):
        self.calls.append({"url": url, "headers": headers, "json": json, "allow_redirects": allow_redirects})
        return self.answers.pop(0)


OK = _Resp(200, {"choices": [{"message": {"content": '{"verdict": "UNVERIFIED"}'}}]})


@pytest.mark.parametrize("prov,url,env,model", [
    ("deepseek", "https://api.deepseek.com/chat/completions", "DEEPSEEK_API_KEY", "deepseek-flash"),
    ("mistral", "https://api.mistral.ai/v1/chat/completions", "MISTRAL_API_KEY", "mistral-small-latest"),
    ("xai", "https://api.x.ai/v1/chat/completions", "XAI_API_KEY", "grok-4.7"),
    ("gemini", "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions", "GEMINI_API_KEY",
     "gemini-3.8-flash"),
    ("moonshot", "https://api.moonshot.ai/v1/chat/completions", "MOONSHOT_API_KEY", "kimi-k3.1-pro"),
    ("qwen", "https://dashscope-intl.aliyuncs.com/compatible-mode/v1/chat/completions", "DASHSCOPE_API_KEY", "qwen-plus"),
    ("zhipu", "https://api.z.ai/api/paas/v4/chat/completions", "ZAI_API_KEY", "glm-5.3"),
    ("openrouter", "https://openrouter.ai/api/v1/chat/completions", "OPENROUTER_API_KEY", "~openai/gpt-sol-latest"),
])
def test_openai_compatible_providers(prov, url, env, model):
    from truthlens.llm import LLMClient
    s = _Sess([OK])
    with use_keys({env: "key-1234567890abcdef"}):
        c = LLMClient(prov, session=s)
        assert c.complete_json("sys", "user") == {"verdict": "UNVERIFIED"}
    call = s.calls[0]
    assert call["url"] == url and call["json"]["model"] == model
    assert call["headers"]["Authorization"] == "Bearer key-1234567890abcdef"
    assert call["json"]["response_format"] == {"type": "json_object"} and call["allow_redirects"] is False
    assert "untested live" in c.label


def test_aliases_and_config_detection(monkeypatch):
    from truthlens.llm import norm_provider
    assert norm_provider("Grok") == "xai" and norm_provider("kimi") == "moonshot" and norm_provider("glm") == "zhipu"
    for k in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "TRUTHLENS_LLM"):
        monkeypatch.delenv(k, raising=False)
    with use_keys({"MISTRAL_API_KEY": "mistral-key-123456"}):
        assert Config.load().resolved_llm() == "mistral"


def test_json_object_rejected_falls_back_to_plain_prompt():
    from truthlens.llm import LLMClient
    s = _Sess([_Resp(400, {"error": "response_format not supported"}),
               _Resp(200, {"choices": [{"message": {"content": 'Sure: {"verdict": "SUPPORTED"} done'}}]})])
    with use_keys({"MOONSHOT_API_KEY": "moon-key-1234567890"}):
        assert LLMClient("moonshot", session=s).complete_json("sys", "user") == {"verdict": "SUPPORTED"}
    assert "response_format" not in s.calls[1]["json"] and "JSON" in s.calls[1]["json"]["messages"][0]["content"]


def test_key_never_in_errors():
    from truthlens.llm import LLMClient, LLMError
    key = "xai-SECRETSECRETSECRET123"
    s = _Sess([_Resp(401, {"error": f"bad key {key}"})])
    with use_keys({"XAI_API_KEY": key}):
        c = LLMClient("xai", session=s)
        with pytest.raises(LLMError) as e:
            c.complete_json("s", "u")
        assert key not in str(e.value) and all(key not in x for x in c.errors)
    assert key not in redact(f"Authorization: Bearer {key}")


def test_custom_base_url_ssrf_guard(monkeypatch):
    from truthlens.llm import LLMClient, LLMError, check_base_url
    for bad in ("http://8.8.8.8/v1", "https://127.0.0.1/v1", "https://10.0.0.5/v1", "https://169.254.169.254/latest",
                "https://user:pw@8.8.8.8/v1", "file:///etc/passwd", "https://8.8.8.8/v1?x=1"):
        with pytest.raises(LLMError):
            check_base_url(bad, public=True)
    assert check_base_url("https://8.8.8.8/v1/", public=True) == "https://8.8.8.8/v1"
    assert check_base_url("http://127.0.0.1:1234/v1", public=False) == "http://127.0.0.1:1234/v1"   # local use only
    # hosted: a base URL that points inside the network is refused at call time too
    monkeypatch.setenv("TRUTHLENS_PUBLIC", "1")
    with use_keys({"TRUTHLENS_CUSTOM_API_KEY": "custom-key-123456", "TRUTHLENS_CUSTOM_BASE_URL": "https://10.1.1.1/v1",
                   "TRUTHLENS_LLM_MODEL": "m"}):
        c = LLMClient("custom", session=_Sess([OK]))
        with pytest.raises(LLMError):
            c.complete_json("s", "u")
    with use_keys({"TRUTHLENS_CUSTOM_API_KEY": "custom-key-123456", "TRUTHLENS_CUSTOM_BASE_URL": "https://8.8.8.8/v1",
                   "TRUTHLENS_LLM_MODEL": "my-model"}):
        s = _Sess([OK])
        LLMClient("custom", session=s).complete_json("s", "u")
        assert s.calls[0]["url"] == "https://8.8.8.8/v1/chat/completions" and s.calls[0]["json"]["model"] == "my-model"


def test_provider_hosts_never_cached():
    from truthlens.livecache import cacheable_request
    for u in ("https://api.deepseek.com/chat/completions", "https://api.mistral.ai/v1/chat/completions",
              "https://api.x.ai/v1/chat/completions", "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions",
              "https://api.moonshot.ai/v1/chat/completions", "https://dashscope-intl.aliyuncs.com/compatible-mode/v1/chat/completions",
              "https://api.z.ai/api/paas/v4/chat/completions", "https://openrouter.ai/api/v1/chat/completions",
              "https://my-own-llm.example.com/v1/chat/completions"):
        assert not cacheable_request("POST", u, {})


def test_api_maps_new_providers(monkeypatch):
    from fastapi import HTTPException
    from truthlens import api

    class R:
        def __init__(self, h):
            self.headers = h
    u = api._user_keys("deepseek", "ds-key-1234567890", request=R({"x-llm-model": "deepseek-flash"}))
    assert u == {"provider": "deepseek", "keys": {"DEEPSEEK_API_KEY": "ds-key-1234567890",
                                                  "TRUTHLENS_LLM_MODEL": "deepseek-flash"}}
    monkeypatch.setattr(api, "PUBLIC", True)
    with pytest.raises(HTTPException) as e:
        api._user_keys("custom", "k-1234567890", request=R({"x-llm-base-url": "https://192.168.1.10/v1", "x-llm-model": "m"}))
    assert e.value.status_code == 422
    with pytest.raises(HTTPException):
        api._user_keys("custom", "k-1234567890", request=R({"x-llm-base-url": "http://8.8.8.8/v1", "x-llm-model": "m"}))
    with pytest.raises(HTTPException):
        api._user_keys("nonsense", "k-1234567890")


def test_cli_offers_providers():
    from truthlens.cli import LLM_CHOICES
    assert {"deepseek", "mistral", "xai", "gemini", "moonshot", "qwen", "zhipu", "openrouter", "custom"} <= set(LLM_CHOICES)


# ---- UI ------------------------------------------------------------------------------------------------------------
def test_web_page_has_provider_picker_compare_tab_and_split_chips():
    from truthlens.webui import PAGE
    for v in ("deepseek", "mistral", "xai", "gemini", "moonshot", "qwen", "zhipu", "openrouter", "custom"):
        assert f'<option value="{v}">' in PAGE
    assert 'id="tab-cmp"' in PAGE and "compare/file" in PAGE
    assert '"DATED":{c:"dat"' in PAGE
    assert "Source didn't respond" in PAGE and "UNVERIFIED:" in PAGE
