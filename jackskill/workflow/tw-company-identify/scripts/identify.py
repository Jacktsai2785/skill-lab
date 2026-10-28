#!/usr/bin/env python3
"""tw-company-identify — extract + classify + normalize Taiwan companies.

Pipeline:
  Extract (Claude LLM) → Classify (suffix rule) → Normalize (g0v + GCIS APIs)

Standalone CLI; no project-specific dependencies. See SKILL.md for usage.
"""
from __future__ import annotations

import argparse
import asyncio
import base64
import json
import logging
import os
import subprocess
import sys
import unicodedata
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import httpx

log = logging.getLogger("tw-company-identify")

# Failures we report as a one-line "Error: ..." (exit 1) instead of a traceback.
# The anthropic SDK is optional, so its API errors (bad key, rate limit) join only if installed.
_EXPECTED_ERRORS: tuple[type[BaseException], ...] = (RuntimeError, ValueError)
try:
    from anthropic import APIError as _AnthropicAPIError
    _EXPECTED_ERRORS += (_AnthropicAPIError,)
except ImportError:
    pass

# ── Constants ─────────────────────────────────────────────────────────────────

RONNY_SEARCH = "https://company.g0v.ronny.tw/api/search"
RONNY_BY_ID = "https://company.g0v.ronny.tw/api/show/{tax_id}"
GCIS_APP1 = (
    "https://data.gcis.nat.gov.tw/od/data/api/"
    "5F64D864-61CB-4D0D-8AD9-492047CC1EA6"
)
TIMEOUT = 20.0
DEFAULT_MODEL = os.environ.get("CLAUDEMODEL", "claude-sonnet-4-6")

_LISTING_SOURCES = [
    ("https://openapi.twse.com.tw/v1/opendata/t187ap03_L", "上市"),
    ("https://www.tpex.org.tw/openapi/v1/mopsfin_t187ap03_O", "上櫃"),
    ("https://www.tpex.org.tw/openapi/v1/mopsfin_t187ap03_R", "興櫃"),
]
_GISA_URL = "https://www.tpex.org.tw/openapi/v1/tpex_gisa_company"

_NAME_SUFFIXES = ("股份有限公司", "有限公司")
_CACHE_TTL = timedelta(hours=24)
_DEGRADED_TTL = timedelta(minutes=5)  # retry soon when a listing source failed
LISTING_UNKNOWN = "未知"  # listing data failed to load; do NOT report "非公發"
_ENRICH_CONCURRENCY = 4  # gov APIs: keep batch lookups polite
_CHUNK_CHARS = 8000
_MAX_CHUNKS = 10
_BREAK_CHARS = (" ", "\t", "　", ",", "，", "、", ";", "；", "。", ".", "\n")

_by_taxid: dict[str, str] = {}
_by_name: dict[str, str] = {}
_by_abbrev: dict[str, str] = {}
_failed_sources: list[str] = []
_cache_until: datetime | None = None
_cache_lock = asyncio.Lock()

# ── Prompts (verbatim from taiwan-company/services/company_extractor.py) ─────

TEXT_PROMPT = (
    "請從以下文字中找出所有疑似公司或機構的名稱。\n"
    "規則：\n"
    "1. 包含「股份有限公司」或「有限公司」的請完整列出\n"
    "2. 看起來是公司或組織但沒有標準結尾的名稱也請列出\n"
    "3. 不要捏造不存在於文字中的名稱\n"
    "4. 只回傳 JSON 陣列，例如：[\"AA科技股份有限公司\", \"BB有限公司\", \"CC創新\"]\n"
    "5. 如果文字中沒有任何公司名稱，回傳空陣列 []\n"
    "6. 不要有任何其他說明文字，只輸出 JSON 陣列\n\n"
    "文字內容：\n{text}"
)

IMAGE_PROMPT = (
    "請讀取圖片，找出其中的台灣公司資料。\n\n"
    "【輸出規則】\n"
    "1. 若圖片有「統一編號」欄位，請輸出 JSON 陣列，每筆格式為 "
    "{\"name\": \"公司名稱\", \"tax_id\": \"統一編號\"}\n"
    "2. 若圖片沒有統一編號，請輸出純字串陣列 [\"公司名稱A\", \"公司名稱B\"]\n"
    "3. 統一編號為8位數字，請完整抓取，不要省略\n"
    "4. 只抓公司或機構名稱，不要列人名、地址、電話、欄位標題\n"
    "5. 只輸出 JSON，不要任何說明文字"
)

# ── Classification ────────────────────────────────────────────────────────────

def classify(name: str) -> str:
    if "股份有限公司" in name:
        return "valid"
    if "有限公司" in name:
        return "excluded"
    return "uncertain"


def parse_int(value: Any) -> int:
    if not value:
        return 0
    try:
        return int(str(value).replace(",", ""))
    except (ValueError, TypeError):
        return 0


def parse_representative_of(val: Any) -> str:
    if isinstance(val, list) and len(val) > 1:
        return str(val[1])
    return ""


def extract_json_array(raw: str) -> list:
    start = raw.find("[")
    if start == -1:
        return []  # prose with no list at all, e.g. "no companies found"
    end = raw.rfind("]")
    # A "[" with no usable list after it means the reply was cut off or malformed.
    # Returning [] here would make a failed extraction look like "0 companies".
    if end <= start:
        raise ValueError("LLM reply contains '[' but no closing ']' (reply cut off?)")
    try:
        return json.loads(raw[start:end + 1])
    except json.JSONDecodeError as e:
        raise ValueError(f"LLM reply is not a valid JSON array: {e}") from e


# ── LLM extraction ────────────────────────────────────────────────────────────

def _raise_if_cut_off(msg: Any) -> None:
    """A reply cut off by max_tokens has no closing ']'; it would parse as zero companies."""
    if getattr(msg, "stop_reason", None) == "max_tokens":
        raise RuntimeError(
            "LLM output was cut off at max_tokens, so the company list is incomplete. "
            "Use a shorter input."
        )


def ask_claude_text(prompt: str, provider: str = "anthropic", timeout: int = 90) -> str:
    if provider == "anthropic" and os.environ.get("ANTHROPIC_API_KEY"):
        try:
            from anthropic import Anthropic
        except ImportError:
            log.warning("anthropic SDK not installed, falling back to CLI")
            return ask_claude_cli(prompt, timeout)
        client = Anthropic()
        msg = client.messages.create(
            model=DEFAULT_MODEL,
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}],
        )
        _raise_if_cut_off(msg)
        return "".join(b.text for b in msg.content if hasattr(b, "text"))
    return ask_claude_cli(prompt, timeout)


def ask_claude_cli(prompt: str, timeout: int = 90) -> str:
    cli = os.environ.get("CLAUDE_CLI_PATH") or "claude"
    try:
        result = subprocess.run(
            [cli, "-p", prompt],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        raise RuntimeError(f"claude CLI call failed: {e}") from e
    if result.returncode != 0:
        # An empty stdout here would parse as "no companies found" and hide the failure.
        raise RuntimeError(
            f"claude CLI exited {result.returncode}: {result.stderr.strip()[:200]}"
        )
    return result.stdout


def ask_claude_image(prompt: str, image_path: Path, timeout: int = 120) -> str:
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise RuntimeError(
            "Image mode requires ANTHROPIC_API_KEY (Claude CLI image support is unreliable)."
        )
    try:
        from anthropic import Anthropic
    except ImportError:
        raise RuntimeError("Image mode requires `pip install anthropic`")

    ext = image_path.suffix.lstrip(".").lower()
    media_type = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png",
                  "webp": "image/webp", "gif": "image/gif"}.get(ext)
    if not media_type:
        raise ValueError(f"Unsupported image type: {ext}")

    data = base64.standard_b64encode(image_path.read_bytes()).decode("ascii")
    client = Anthropic()
    msg = client.messages.create(
        model=DEFAULT_MODEL,
        max_tokens=4096,
        messages=[{
            "role": "user",
            "content": [
                {"type": "image", "source": {"type": "base64",
                                              "media_type": media_type, "data": data}},
                {"type": "text", "text": prompt},
            ],
        }],
    )
    _raise_if_cut_off(msg)
    return "".join(b.text for b in msg.content if hasattr(b, "text"))


# ── Listing status cache ──────────────────────────────────────────────────────

async def _load_listing_source(
    client: httpx.AsyncClient, url: str, status: str,
    taxids: dict[str, str], names: dict[str, str],
) -> bool:
    """Fetch one source into the given dicts. Nothing is written unless the whole fetch parses."""
    try:
        resp = await client.get(url, timeout=15.0)
        resp.raise_for_status()
        new_tax: dict[str, str] = {}
        new_name: dict[str, str] = {}
        for row in resp.json():
            taxid = (
                row.get("營利事業統一編號") or
                row.get("UnifiedBusinessNo.") or
                row.get("統一編號") or ""
            ).strip()
            cname = (row.get("公司名稱") or row.get("CompanyName") or "").strip()
            if taxid:
                new_tax[taxid] = status
            if cname:
                new_name[cname] = status
        taxids.update(new_tax)
        names.update(new_name)
        return True
    except Exception as e:
        log.warning("listing source %s failed: %s", url, e)
        return False


async def _load_gisa(client: httpx.AsyncClient, abbrevs: dict[str, str]) -> bool:
    try:
        resp = await client.get(_GISA_URL, timeout=15.0,
                                headers={"Accept": "application/json"})
        resp.raise_for_status()
        found = {}
        for row in resp.json():
            abbrev = (row.get("CompanyName") or "").strip()
            if abbrev:
                found[abbrev] = "創新板"
        abbrevs.update(found)
        return True
    except Exception as e:
        log.warning("GISA load failed: %s", e)
        return False


async def ensure_listing_cache(client: httpx.AsyncClient) -> None:
    global _cache_until
    if _cache_until and datetime.now() < _cache_until:
        return
    async with _cache_lock:
        if _cache_until and datetime.now() < _cache_until:
            return
        # Build into fresh dicts and swap at the end. Concurrent lookups keep
        # reading the old cache until then, and never see a half-loaded one.
        new_tax: dict[str, str] = {}
        new_name: dict[str, str] = {}
        new_abbrev: dict[str, str] = {}
        results = await asyncio.gather(
            *[_load_listing_source(client, url, status, new_tax, new_name)
              for url, status in _LISTING_SOURCES],
            _load_gisa(client, new_abbrev),
        )
        failed = [status for (_, status), ok in zip(_LISTING_SOURCES, results[:-1]) if not ok]
        if not results[-1]:
            failed.append("創新板")
        # A source that failed this time keeps its previous entries rather than
        # silently dropping those companies.
        for status in failed:
            for src, dst in ((_by_taxid, new_tax), (_by_name, new_name), (_by_abbrev, new_abbrev)):
                for k, v in src.items():
                    if v == status:
                        dst.setdefault(k, v)
        # No await between here and the end: the swap is atomic for other tasks.
        for old, new in ((_by_taxid, new_tax), (_by_name, new_name), (_by_abbrev, new_abbrev)):
            old.clear()
            old.update(new)
        _failed_sources[:] = failed
        _cache_until = datetime.now() + (_DEGRADED_TTL if failed else _CACHE_TTL)


def resolve_listing_status(tax_id: str, name: str) -> str:
    if tax_id and tax_id in _by_taxid:
        return _by_taxid[tax_id]
    if name and name in _by_name:
        return _by_name[name]
    abbrev = name
    for sfx in _NAME_SUFFIXES:
        if abbrev.endswith(sfx):
            abbrev = abbrev[: -len(sfx)]
            break
    if abbrev and abbrev != name and abbrev in _by_abbrev:
        return _by_abbrev[abbrev]
    # No match is only "非公發" when every listing source actually loaded.
    return LISTING_UNKNOWN if _failed_sources else "非公發"


# ── GCIS / g0v lookup ─────────────────────────────────────────────────────────

def _reason(e: Exception) -> str:
    """Short, readable cause for a failed request (no URL, no multi-line noise)."""
    if isinstance(e, httpx.HTTPStatusError):
        return f"HTTP {e.response.status_code}"
    return f"{type(e).__name__}: {str(e)[:80]}"


def _norm(name: str) -> str:
    """Comparison key only: unify full/half-width characters and trim spaces."""
    return unicodedata.normalize("NFKC", name or "").strip()


async def fetch_company_name_by_tax_id(
    tax_id: str, client: httpx.AsyncClient | None = None
) -> str:
    if not (tax_id and len(tax_id) == 8 and tax_id.isdigit()):
        return ""
    if client is None:
        async with httpx.AsyncClient(timeout=TIMEOUT, follow_redirects=True) as own:
            return await _name_by_tax_id(own, tax_id)
    return await _name_by_tax_id(client, tax_id)


async def _name_by_tax_id(client: httpx.AsyncClient, tax_id: str) -> str:
    try:
        resp = await client.get(RONNY_BY_ID.format(tax_id=tax_id))
        resp.raise_for_status()
        data = resp.json().get("data", {})
        name = data.get("公司名稱", "") or data.get("Company_Name", "")
        if name:
            return name
    except Exception as e:
        log.warning("g0v tax-id lookup failed for %s: %s", tax_id, _reason(e))
    try:
        resp = await client.get(GCIS_APP1, params={
            "$format": "json",
            "$filter": f"Business_Accounting_NO eq '{tax_id}'",
            "$skip": "0", "$top": "1",
        })
        resp.raise_for_status()
        if not resp.content.strip():  # GCIS answers 200 with an empty body for "no such tax id"
            return ""
        data = resp.json()
        if data:
            return data[0].get("Company_Name", "") or data[0].get("公司名稱", "")
    except Exception as e:
        log.warning("GCIS tax-id lookup failed for %s: %s", tax_id, _reason(e))
    return ""


async def _fetch_ronny(
    client: httpx.AsyncClient, name: str, tax_id_hint: str = ""
) -> tuple[dict | None, list[dict], str]:
    """Return (data, candidates, error).

    A hit counts as the company when its name matches (after _norm) or its tax
    id equals `tax_id_hint`. When nothing matches, every hit is returned as a
    candidate, even if there is only one: a brand or abbreviated name can
    partially match a different company, so the caller must surface it for
    confirmation instead of silently attaching that company's tax id and
    directors. `error` is non-empty only when the request itself failed, so
    "no data" and "lookup failed" stay distinguishable.
    """
    try:
        resp = await client.get(RONNY_SEARCH, params={"q": name}, timeout=15.0)
        resp.raise_for_status()
        hits = resp.json().get("data", [])
        has_hint = bool(tax_id_hint) and len(tax_id_hint) == 8 and tax_id_hint.isdigit()
        exact = None
        if has_hint:
            # A tax id the caller supplied outranks any name match.
            exact = next((h for h in hits if h.get("統一編號", "") == tax_id_hint), None)
        else:
            exact = next((h for h in hits if _norm(h.get("公司名稱", "")) == _norm(name)), None)
        if exact is None and has_hint:
            # Search missed it (renamed company, different spelling): ask by tax id directly.
            r2 = await client.get(RONNY_BY_ID.format(tax_id=tax_id_hint), timeout=15.0)
            r2.raise_for_status()
            data = r2.json().get("data")
            if isinstance(data, dict) and data.get("公司名稱"):
                exact = {**data, "統一編號": tax_id_hint}
        if not hits and exact is None:
            return None, [], ""
        if exact is None:
            candidates = [
                {
                    "name": h.get("公司名稱", ""),
                    "tax_id": h.get("統一編號", ""),
                    "address": h.get("公司所在地", ""),
                    "capital": parse_int(h.get("實收資本額(元)", "0")),
                }
                for h in hits[:10]
            ]
            return None, candidates, ""
        row = exact
        total_shares = parse_int(row.get("已發行股份總數(股)", "0"))
        directors = [
            {
                "name": d.get("姓名", ""),
                "title": d.get("職稱", ""),
                "representative_of": parse_representative_of(d.get("所代表法人", "")),
                "shares": parse_int(d.get("出資額", "0")),
                "ratio": round(parse_int(d.get("出資額", "0")) / total_shares, 6)
                          if total_shares > 0 else 0.0,
            }
            for d in row.get("董監事名單", [])
        ]
        return {
            "tax_id": row.get("統一編號", ""),
            "representative": row.get("代表人姓名", ""),
            "capital": parse_int(row.get("實收資本額(元)", "0")),
            "address": row.get("公司所在地", ""),
            "par_value": parse_int(row.get("每股金額(元)", "0")),
            "total_shares": total_shares,
            "directors": directors,
        }, [], ""
    except Exception as e:
        log.warning("g0v fetch failed for %s: %s", name, _reason(e))
        return None, [], f"g0v lookup failed for {name}: {_reason(e)}"


async def _fetch_gcis_by_tax_id(client: httpx.AsyncClient, tax_id: str) -> dict:
    try:
        resp = await client.get(GCIS_APP1, params={
            "$format": "json",
            "$filter": f"Business_Accounting_NO eq '{tax_id}'",
            "$skip": "0", "$top": "1",
        })
        resp.raise_for_status()
        if not resp.content.strip():  # empty body = no such tax id, not a failure
            return {}
        data = resp.json()
        if not data:
            return {}
        row = data[0]
        return {
            "representative": row.get("Responsible_Name", ""),
            "capital": parse_int(row.get("Paid_In_Capital_Amount", "0")),
            "authorized_capital": parse_int(row.get("Capital_Stock_Amount", "0")),
            "address": row.get("Company_Location", ""),
        }
    except Exception as e:
        log.warning("GCIS lookup failed for %s: %s", tax_id, _reason(e))
        # Marker, not {}: an empty dict would look like "GCIS has no data".
        return {"_error": f"GCIS lookup failed for {tax_id}: {_reason(e)}"}


async def fetch_company_data(
    name: str, tax_id_hint: str = "", client: httpx.AsyncClient | None = None
) -> dict:
    """Enrich one company. Pass a shared `client` for batch use; otherwise one is opened."""
    if client is None:
        async with httpx.AsyncClient(timeout=TIMEOUT, follow_redirects=True) as own:
            return await _fetch_company_data(own, name, tax_id_hint)
    return await _fetch_company_data(client, name, tax_id_hint)


async def _fetch_company_data(
    client: httpx.AsyncClient, name: str, tax_id_hint: str
) -> dict:
    result = {
        "tax_id": tax_id_hint,
        "representative": "",
        "capital": 0,
        "authorized_capital": 0,
        "address": "",
        "listing_status": "非公發",
        "par_value": 0,
        "total_shares": 0,
        "directors": [],
    }
    await ensure_listing_cache(client)
    ronny, candidates, ronny_error = await _fetch_ronny(client, name, tax_id_hint)
    if ronny_error:
        result.setdefault("warnings", []).append(ronny_error)
    if candidates:
        result["candidates"] = candidates
        return result
    if ronny:
        result.update(ronny)
    tax_id = result.get("tax_id", "") or tax_id_hint
    if tax_id:
        gcis = await _fetch_gcis_by_tax_id(client, tax_id)
        if gcis.get("_error"):
            result.setdefault("warnings", []).append(gcis["_error"])
        if gcis.get("authorized_capital"):
            result["authorized_capital"] = gcis["authorized_capital"]
        if not ronny:
            for k in ("representative", "capital", "address"):
                if gcis.get(k):
                    result[k] = gcis[k]
        result["tax_id"] = tax_id
    result["listing_status"] = resolve_listing_status(result["tax_id"], name)
    return result


# ── Extraction wrappers ───────────────────────────────────────────────────────

def _chunk_text(text: str) -> list[str]:
    """Split on line boundaries into pieces of at most _CHUNK_CHARS characters.

    A single line longer than the limit (typical for text pasted from a PDF) is
    cut at the last space or punctuation mark in the window, so a company name
    is not sliced in half. Only a run with no break character at all is cut hard.
    """
    chunks: list[str] = []
    cur = ""
    for line in text.splitlines(keepends=True):
        while len(line) > _CHUNK_CHARS:
            if cur:
                chunks.append(cur)
                cur = ""
            window = line[:_CHUNK_CHARS]
            cut = max(window.rfind(ch) for ch in _BREAK_CHARS) + 1
            if cut < _CHUNK_CHARS // 2:  # no break nearby: hard cut
                cut = _CHUNK_CHARS
            chunks.append(line[:cut])
            line = line[cut:]
        if cur and len(cur) + len(line) > _CHUNK_CHARS:
            chunks.append(cur)
            cur = ""
        cur += line
    if cur:
        chunks.append(cur)
    return chunks


def extract_from_text(text: str, provider: str) -> list[dict]:
    if not text or len(text.strip()) < 5:
        return []
    chunks = _chunk_text(text)
    if len(chunks) > _MAX_CHUNKS:
        # Refuse rather than quietly read only the start: the JSON output carries
        # no truncation marker, so a partial result would look complete.
        raise RuntimeError(
            f"input is {len(text)} chars ({len(chunks)} chunks); the limit is "
            f"{_MAX_CHUNKS * _CHUNK_CHARS} chars. Split the input and run it in parts."
        )
    if len(chunks) > 1:
        log.warning("input is %d chars; reading it in %d chunks", len(text), len(chunks))
    seen: set[str] = set()
    items: list[dict] = []
    for chunk in chunks:
        raw = ask_claude_text(TEXT_PROMPT.format(text=chunk), provider=provider)
        for n in extract_json_array(raw):
            if isinstance(n, str) and len(n) >= 3 and n not in seen:
                seen.add(n)
                items.append({"name": n, "tax_id": ""})
    return items


def extract_from_image(image_path: Path) -> list[dict]:
    raw = ask_claude_image(IMAGE_PROMPT, image_path)
    parsed = extract_json_array(raw)
    items = []
    for item in parsed:
        if isinstance(item, str) and len(item) >= 3:
            items.append({"name": item, "tax_id": ""})
        elif isinstance(item, dict):
            name = (item.get("name") or item.get("募資企業名稱")
                    or item.get("公司名稱", ""))
            tax_id = str(item.get("tax_id") or item.get("統一編號", "")).strip()
            if name and len(name) >= 3:
                items.append({"name": name, "tax_id": tax_id})
    return items


async def resolve_official_names(items: list[dict]) -> list[dict]:
    """Replace candidate name with official GCIS name when tax_id is valid."""
    sem = asyncio.Semaphore(_ENRICH_CONCURRENCY)

    async def resolve_one(client: httpx.AsyncClient, item: dict) -> dict:
        tid = item.get("tax_id", "").strip()
        if item.get("name_resolved"):  # caller already looked this tax id up
            return item
        if tid and len(tid) == 8 and tid.isdigit():
            async with sem:
                official = await fetch_company_name_by_tax_id(tid, client=client)
            if official:
                item["name"] = official
        return item

    async with httpx.AsyncClient(timeout=TIMEOUT, follow_redirects=True) as client:
        return list(await asyncio.gather(*[resolve_one(client, i) for i in items]))


# ── Pipeline ──────────────────────────────────────────────────────────────────

async def run_pipeline(items: list[dict], enrich: bool) -> dict:
    items = await resolve_official_names(items)
    result = {"valid": [], "excluded": [], "uncertain": [], "candidates": []}
    seen = set()
    unique: list[dict] = []
    for item in items:
        if item["name"] in seen:
            continue
        seen.add(item["name"])
        unique.append(item)

    # Independent lookups run concurrently over one shared client; results are
    # assembled below in the original order.
    metas: dict[str, dict] = {}
    if enrich:
        targets = [i for i in unique if classify(i["name"]) == "valid"]
        sem = asyncio.Semaphore(_ENRICH_CONCURRENCY)
        async with httpx.AsyncClient(timeout=TIMEOUT, follow_redirects=True) as client:
            async def enrich_one(item: dict) -> tuple[str, dict]:
                async with sem:
                    meta = await fetch_company_data(
                        item["name"], tax_id_hint=item.get("tax_id", ""), client=client
                    )
                return item["name"], meta
            metas = dict(await asyncio.gather(*[enrich_one(i) for i in targets]))

    for item in unique:
        name = item["name"]
        kind = classify(name)
        if kind == "excluded":
            result["excluded"].append({"name": name})
        elif kind == "uncertain":
            result["uncertain"].append({"name": name})
        else:
            entry = {"name": name}
            if enrich:
                meta = metas[name]
                if meta.get("candidates"):
                    result["candidates"].append({
                        "query": name,
                        "hits": meta["candidates"],
                    })
                    continue
                entry.update(meta)
            result["valid"].append(entry)
    return result


async def normalize_single(name: str = "", tax_id: str = "") -> dict:
    if tax_id:
        official = await fetch_company_name_by_tax_id(tax_id)
        if not official and not name:
            # Never invent a placeholder name: it would be classified "uncertain"
            # and exit 0, which reads like a real result rather than a failed lookup.
            raise RuntimeError(
                f"could not resolve tax id {tax_id}: no such company, or both g0v and "
                f"GCIS lookups failed (see warnings above)"
            )
        name = official or name
    if not name:
        return {"valid": [], "excluded": [], "uncertain": []}
    # name_resolved: the tax id was already looked up above; don't query it a second time.
    return await run_pipeline(
        [{"name": name, "tax_id": tax_id, "name_resolved": bool(tax_id)}], enrich=True
    )


# ── CLI ───────────────────────────────────────────────────────────────────────

def print_summary(result: dict, stream=sys.stderr) -> None:
    v, e, u = result["valid"], result["excluded"], result["uncertain"]
    print(f"\n=== Identified: {len(v)} valid, {len(e)} excluded, {len(u)} uncertain ===",
          file=stream)
    for c in v:
        line = f"  ✓ {c['name']}"
        if c.get("tax_id"):
            line += f"  [{c['tax_id']}]"
        if c.get("listing_status") and c["listing_status"] != "非公發":
            line += f"  ({c['listing_status']})"
        print(line, file=stream)
    for c in e:
        print(f"  ✗ {c['name']}  (excluded: 有限公司)", file=stream)
    for c in u:
        print(f"  ? {c['name']}  (uncertain)", file=stream)
    for amb in result.get("candidates", []):
        print(f"\n  ⚠ 「{amb['query']}」沒有完全相符的公司名稱，找到以下相似公司，"
              f"請確認後用 --tax-id 精確查詢：", file=stream)
        for hit in amb["hits"]:
            cap = f"  資本 {hit['capital']:,}" if hit.get("capital") else ""
            print(f"    [{hit['tax_id']}] {hit['name']}  {hit['address']}{cap}", file=stream)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Identify and normalize Taiwan companies from text/image/name/tax-id.",
    )
    src = parser.add_mutually_exclusive_group(required=True)
    src.add_argument("--text", help="Text to extract from")
    src.add_argument("--stdin", action="store_true", help="Read text from stdin")
    src.add_argument("--image", type=Path, help="Image file to extract from")
    src.add_argument("--name", help="Single company name to normalize (skip extraction)")
    src.add_argument("--tax-id", help="Single 統一編號 to normalize (skip extraction)")

    parser.add_argument("--no-enrich", action="store_true",
                        help="Skip GCIS enrichment (extract+classify only)")
    parser.add_argument("--provider", choices=["anthropic", "cli"], default="anthropic",
                        help="LLM provider for text extraction")
    parser.add_argument("--json-only", action="store_true",
                        help="Print only JSON to stdout (no stderr summary)")
    parser.add_argument("--verbose", "-v", action="store_true", help="Debug logging")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.WARNING,
        format="%(levelname)s [%(name)s] %(message)s",
    )

    try:
        if args.name or args.tax_id:
            result = asyncio.run(normalize_single(name=args.name or "",
                                                  tax_id=args.tax_id or ""))
        else:
            if args.stdin:
                text = sys.stdin.read()
                items = extract_from_text(text, args.provider)
            elif args.text:
                items = extract_from_text(args.text, args.provider)
            elif args.image:
                if not args.image.exists():
                    print(f"Image not found: {args.image}", file=sys.stderr)
                    return 2
                items = extract_from_image(args.image)
            else:
                parser.print_help()
                return 2
            result = asyncio.run(run_pipeline(items, enrich=not args.no_enrich))
    except _EXPECTED_ERRORS as e:
        # LLM/CLI failure must not look like "0 companies found".
        print(f"Error: {e}", file=sys.stderr)
        return 1

    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not args.json_only:
        print_summary(result)
    return 0


if __name__ == "__main__":
    sys.exit(main())
