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
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import httpx

log = logging.getLogger("tw-company-identify")

# ── Constants ─────────────────────────────────────────────────────────────────

RONNY_SEARCH = "https://company.g0v.ronny.tw/api/search"
RONNY_BY_ID = "https://company.g0v.ronny.tw/api/id/{tax_id}"
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

_by_taxid: dict[str, str] = {}
_by_name: dict[str, str] = {}
_by_abbrev: dict[str, str] = {}
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
    end = raw.rfind("]")
    if start == -1 or end <= start:
        return []
    try:
        return json.loads(raw[start:end + 1])
    except json.JSONDecodeError:
        return []


# ── LLM extraction ────────────────────────────────────────────────────────────

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
        return result.stdout
    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        log.error("CLI call failed: %s", e)
        return ""


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
    return "".join(b.text for b in msg.content if hasattr(b, "text"))


# ── Listing status cache ──────────────────────────────────────────────────────

async def _load_listing_source(client: httpx.AsyncClient, url: str, status: str) -> None:
    try:
        resp = await client.get(url, timeout=15.0)
        resp.raise_for_status()
        for row in resp.json():
            taxid = (
                row.get("營利事業統一編號") or
                row.get("UnifiedBusinessNo.") or
                row.get("統一編號") or ""
            ).strip()
            cname = (row.get("公司名稱") or row.get("CompanyName") or "").strip()
            if taxid:
                _by_taxid[taxid] = status
            if cname:
                _by_name[cname] = status
    except Exception as e:
        log.warning("listing source %s failed: %s", url, e)


async def _load_gisa(client: httpx.AsyncClient) -> None:
    try:
        resp = await client.get(_GISA_URL, timeout=15.0,
                                headers={"Accept": "application/json"})
        resp.raise_for_status()
        for row in resp.json():
            abbrev = (row.get("CompanyName") or "").strip()
            if abbrev:
                _by_abbrev[abbrev] = "創新板"
    except Exception as e:
        log.warning("GISA load failed: %s", e)


async def ensure_listing_cache(client: httpx.AsyncClient) -> None:
    global _cache_until
    if _cache_until and datetime.now() < _cache_until:
        return
    async with _cache_lock:
        if _cache_until and datetime.now() < _cache_until:
            return
        _by_taxid.clear()
        _by_name.clear()
        _by_abbrev.clear()
        for url, status in _LISTING_SOURCES:
            await _load_listing_source(client, url, status)
        await _load_gisa(client)
        _cache_until = datetime.now() + _CACHE_TTL


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
    return "非公發"


# ── GCIS / g0v lookup ─────────────────────────────────────────────────────────

async def fetch_company_name_by_tax_id(tax_id: str) -> str:
    if not (tax_id and len(tax_id) == 8 and tax_id.isdigit()):
        return ""
    async with httpx.AsyncClient(timeout=TIMEOUT, follow_redirects=True) as client:
        try:
            resp = await client.get(RONNY_BY_ID.format(tax_id=tax_id))
            resp.raise_for_status()
            data = resp.json().get("data", {})
            name = data.get("公司名稱", "") or data.get("Company_Name", "")
            if name:
                return name
        except Exception:
            pass
        try:
            resp = await client.get(GCIS_APP1, params={
                "$format": "json",
                "$filter": f"Business_Accounting_NO eq '{tax_id}'",
                "$skip": "0", "$top": "1",
            })
            resp.raise_for_status()
            data = resp.json()
            if data:
                return data[0].get("Company_Name", "") or data[0].get("公司名稱", "")
        except Exception:
            pass
    return ""


async def _fetch_ronny(
    client: httpx.AsyncClient, name: str
) -> tuple[dict | None, list[dict]]:
    """Return (data, candidates).

    candidates is non-empty only when the query returned multiple hits with no
    exact name match — the caller should surface them for disambiguation instead
    of silently picking the first result.
    """
    try:
        resp = await client.get(RONNY_SEARCH, params={"q": name}, timeout=15.0)
        resp.raise_for_status()
        hits = resp.json().get("data", [])
        if not hits:
            return None, []
        exact = next((h for h in hits if h.get("公司名稱") == name), None)
        if exact is None and len(hits) > 1:
            candidates = [
                {
                    "name": h.get("公司名稱", ""),
                    "tax_id": h.get("統一編號", ""),
                    "address": h.get("公司所在地", ""),
                    "capital": parse_int(h.get("實收資本額(元)", "0")),
                }
                for h in hits[:10]
            ]
            return None, candidates
        row = exact or hits[0]
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
        }, []
    except Exception as e:
        log.warning("g0v fetch failed for %s: %s", name, e)
        return None, []


async def _fetch_gcis_by_tax_id(client: httpx.AsyncClient, tax_id: str) -> dict:
    try:
        resp = await client.get(GCIS_APP1, params={
            "$format": "json",
            "$filter": f"Business_Accounting_NO eq '{tax_id}'",
            "$skip": "0", "$top": "1",
        })
        resp.raise_for_status()
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
    except Exception:
        return {}


async def fetch_company_data(name: str, tax_id_hint: str = "") -> dict:
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
    async with httpx.AsyncClient(timeout=TIMEOUT, follow_redirects=True) as client:
        await ensure_listing_cache(client)
        ronny, candidates = await _fetch_ronny(client, name)
        if candidates:
            result["candidates"] = candidates
            return result
        if ronny:
            result.update(ronny)
        tax_id = result.get("tax_id", "") or tax_id_hint
        if tax_id:
            gcis = await _fetch_gcis_by_tax_id(client, tax_id)
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

def extract_from_text(text: str, provider: str) -> list[dict]:
    if not text or len(text.strip()) < 5:
        return []
    raw = ask_claude_text(TEXT_PROMPT.format(text=text[:8000]), provider=provider)
    names = extract_json_array(raw)
    return [{"name": n, "tax_id": ""} for n in names if isinstance(n, str) and len(n) >= 3]


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
    async def resolve_one(item: dict) -> dict:
        tid = item.get("tax_id", "").strip()
        if tid and len(tid) == 8 and tid.isdigit():
            official = await fetch_company_name_by_tax_id(tid)
            if official:
                item["name"] = official
        return item
    return list(await asyncio.gather(*[resolve_one(i) for i in items]))


# ── Pipeline ──────────────────────────────────────────────────────────────────

async def run_pipeline(items: list[dict], enrich: bool) -> dict:
    items = await resolve_official_names(items)
    result = {"valid": [], "excluded": [], "uncertain": [], "candidates": []}
    seen = set()
    for item in items:
        name = item["name"]
        if name in seen:
            continue
        seen.add(name)
        kind = classify(name)
        if kind == "excluded":
            result["excluded"].append({"name": name})
        elif kind == "uncertain":
            result["uncertain"].append({"name": name})
        else:
            entry = {"name": name}
            if enrich:
                meta = await fetch_company_data(name, tax_id_hint=item.get("tax_id", ""))
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
        name = official or name or f"統編 {tax_id}"
    if not name:
        return {"valid": [], "excluded": [], "uncertain": []}
    return await run_pipeline([{"name": name, "tax_id": tax_id}], enrich=True)


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
        print(f"\n  ⚠ 「{amb['query']}」找到多筆相似公司，請用 --tax-id 精確查詢：", file=stream)
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

    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not args.json_only:
        print_summary(result)
    return 0


if __name__ == "__main__":
    sys.exit(main())
