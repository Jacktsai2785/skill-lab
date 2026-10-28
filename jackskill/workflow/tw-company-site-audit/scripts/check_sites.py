#!/usr/bin/env python3
"""Batch-check company websites with Playwright and classify why each one fails.

Usage:
    python3 check_sites.py companies.json [out.json]

companies.json: [{"name": "神能健康服務", "url": "www.godpower.net"}, ...]
Entries with an empty url are reported as "no_url", never skipped silently.

Requires: pip install playwright && playwright install chromium

Classification (the point of this script is to avoid calling a site "dead"
when it is not):
    ok          reachable, HTTP < 400
    no_scheme   url lacked http(s)://  -> data bug; tested with https:// added, then
                http:// if https failed (marked http_only) and the site opened
    bot_check   403/503 plus a challenge page -> needs a HUMAN to open it
    dns_fail    domain does not resolve
    cert_error  TLS certificate expired or invalid
    http_error  server answered 4xx/5xx without a challenge page
    conn_fail   connection refused / closed / timeout after one retry
    no_url      the record has no url
This script uses Playwright's default browser identity on purpose. It does not
try to get past bot checks; those are reported for a person to confirm.
"""
import asyncio
import json
import re
import sys

from playwright.async_api import async_playwright

CONCURRENCY = 6
TIMEOUT_MS = 25000
RETRY_TIMEOUT_MS = 45000
CHALLENGE_HINTS = ("checking your browser", "just a moment", "attention required", "verify you are human")


def normalise(raw: str):
    """Return (url_to_test, had_scheme)."""
    raw = raw.strip()
    if re.match(r"https?://", raw, re.I):
        return raw, True
    return "https://" + raw, False


def classify_error(msg: str) -> str:
    if "ERR_NAME_NOT_RESOLVED" in msg:
        return "dns_fail"
    if "ERR_CERT" in msg or "SSL" in msg:
        return "cert_error"
    return "conn_fail"


async def attempt(browser, url: str, timeout_ms: int) -> dict:
    ctx = None
    try:
        ctx = await browser.new_context(locale="zh-TW")
        page = await ctx.new_page()
        resp = await page.goto(url, timeout=timeout_ms, wait_until="domcontentloaded")
        status = resp.status if resp else None
        title = (await page.title())[:80]
        body = ""
        if status and status >= 400:
            try:
                body = (await page.inner_text("body"))[:400].lower()
            except Exception:
                pass
        return {"status": status, "final": page.url, "title": title, "body": body, "err": None}
    except Exception as e:  # noqa: BLE001 - classify any navigation failure
        return {"status": None, "final": None, "title": "", "body": "", "err": str(e).split("\n")[0][:160]}
    finally:
        if ctx is not None:
            await ctx.close()


async def check(browser, sem, rec: dict) -> dict:
    # `or ""` because spreadsheet exports often give null, not a missing key
    out = {"name": rec.get("name") or "", "url": rec.get("url") or ""}
    if not out["url"].strip():
        out["verdict"] = "no_url"
        return out
    url, had_scheme = normalise(out["url"])
    out["tested"] = url
    async with sem:
        r = await attempt(browser, url, TIMEOUT_MS)
        transient = r["err"] and classify_error(r["err"]) == "conn_fail"
        if transient:  # one patient retry: ERR_NETWORK_CHANGED, timeouts, resets
            r = await attempt(browser, url, RETRY_TIMEOUT_MS)
        # A scheme-less url may be an http-only site; https failing proves nothing.
        # DNS failure is the exception: http would fail the same way.
        if r["err"] and not had_scheme and classify_error(r["err"]) != "dns_fail":
            http_url = "http://" + out["url"].strip()
            r_http = await attempt(browser, http_url, TIMEOUT_MS)
            if not r_http["err"]:
                r, url = r_http, http_url
                out["tested"] = url
                out["http_only"] = True
    out.update({k: r[k] for k in ("status", "final", "title", "err")})
    if r["err"]:
        out["verdict"] = classify_error(r["err"])
    elif r["status"] and r["status"] >= 400:
        challenged = any(h in (r["title"] + " " + r["body"]).lower() for h in CHALLENGE_HINTS)
        out["verdict"] = "bot_check" if challenged else "http_error"
    else:
        out["verdict"] = "ok"
    if not had_scheme:
        out["no_scheme"] = True
        if out["verdict"] == "ok":
            out["verdict"] = "no_scheme"
    return out


async def main(src: str, dst: str):
    with open(src, encoding="utf-8") as f:
        records = json.load(f)
    sem = asyncio.Semaphore(CONCURRENCY)
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        results = await asyncio.gather(*[check(browser, sem, r) for r in records])
        await browser.close()
    with open(dst, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=1)
    order = ["no_scheme", "dns_fail", "cert_error", "http_error", "conn_fail", "bot_check", "no_url", "ok"]
    for v in order:
        group = [r for r in results if r["verdict"] == v]
        if not group:
            continue
        print(f"\n== {v} ({len(group)})")
        if v == "ok":
            continue
        for r in group:
            print(f"  {r['name']} | {r.get('tested', r['url'])} | status={r.get('status')} {r.get('err') or r.get('title') or ''}")
    print(f"\ntotal {len(results)}; details -> {dst}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    asyncio.run(main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else "site_results.json"))
