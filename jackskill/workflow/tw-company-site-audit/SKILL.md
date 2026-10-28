---
name: tw-company-site-audit
description: >
  Batch-check a list of Taiwan companies' websites with Playwright, explain WHY each
  broken one fails (missing https://, DNS gone, expired cert, bot check, HTTP error),
  then check the company's registry status and look for a replacement site.
  Exists because a dead website is often a dissolved company, and a "dead" link is
  often just a data bug.
  TRIGGER when: user has a list/canvas/spreadsheet of Taiwan companies with URLs and says
  "檢查官網打不打得開", "哪些公司網站失效", "官網點不開", "清單裡的網址有沒有壞", "公司還在不在",
  or asks why one company's site will not open.
  DO NOT TRIGGER when: looking up ONE company's registration record (use tw-company-lookup);
  identifying companies from raw text or images (use tw-company-identify);
  general web scraping; non-Taiwan companies (the registry steps do not apply).
---

# Taiwan Company Site Audit

Find which company websites are broken in a list, say why, and tell apart "公司已解散" from "只是網站壞了".

## Workflow

1. **Collect the list** as `[{"name": ..., "url": ..., "tax_id": ...}]`. Keep records with no url; they are a finding, not noise.
2. **Run the checker** (needs `pip install playwright && playwright install chromium`):
   `python3 scripts/check_sites.py companies.json out.json`
   It prints each failure with a reason class. Read `out.json` for details.
3. **Triage by class**, do not treat them alike:
   - `no_scheme`: the data lacks `https://`. The site works; fix the data.
   - `bot_check`: a person must open it. Report it as "needs human confirmation".
   - `dns_fail`, `cert_error`, `http_error`, `conn_fail`: possibly dead. Go to step 4.
   - `no_url`: list them separately so they are not mistaken for "checked and fine".
4. **Check registry status before hunting a replacement site** (see Registry checks). A dissolved company needs no new site; it needs removing or flagging.
5. **Companies without a tax ID** are the blind spot: no tax-ID query covers them. Resolve the legal name first (Registry checks, steps b and c), then query. List any that stay unresolved.
6. **Look for a replacement site** only for companies still registered. Use their own social page, press interviews, or an independent search. Then re-run `check_sites.py` on the candidates and confirm the page really names the company (title, address, products).
7. **Report** one table: company, old url, failure class, registry status, replacement (verified or not). Change source data only after the user agrees, and say what was left unverified.

## Registry checks

Use `curl`, not Python `urllib` (see Gotchas).

- a. By tax ID: `https://company.g0v.ronny.tw/api/show/{tax_id}` for the full record. Cross-check status with GCIS company data (`5F64D864-61CB-4D0D-8AD9-492047CC1EA6`, field `Company_Status_Desc`), because g0v's status field can be empty.
- b. By company name: `https://company.g0v.ronny.tw/api/search?q={name}` (matches company names only).
- c. By a person's name: `https://company.g0v.ronny.tw/api/name?q={founder}&page=1` (matches 負責人 and directors). Use the founder from a press article or an accelerator page.

Endpoint details and field meanings: `../tw-company-identify/reference/api-spec.md` (optional; this skill works without it).

## Gotchas

- **A dead site may mean a dissolved company.** Check registry status first. In one audit, two of seven "dead sites" were dissolved companies, and only a person comparing with another tool noticed.
- **No tax ID means never checked.** A tax-ID-based pass silently skips those companies. Always print the "no tax ID, not checked" list at the end.
- **`/api/search` does not search people.** Zero hits for a founder's name says nothing. Use `/api/name`.
- **Brand name is not the legal name.** "Kitchen Lab" was registered as 伽立略餐飲企業股份有限公司. Zero hits on a brand name is normal; find the legal name through the founder.
- **Python `urllib` gets 403 from the GCIS API; `curl` gets 200.** If a whole batch returns 403, it is the client, not the companies. Discard that batch.
- **Do not copy an aggregator's site list as proof.** An accelerator page that lists the same URL as your data is a copy, not an independent check.
- **Never disguise the browser to get past a bot check.** Report `bot_check` for a person to confirm. Note: this class was not reproduced when the script was tested (a site that once showed a challenge answered 200 with Playwright's default identity), so treat the branch as untested.
- **A matched person name is evidence, not proof.** When a company is linked to a brand only through a founder's name plus one article, say so in the output.

## Output example

| Company | Old URL | Class | Registry | Replacement |
|---|---|---|---|---|
| A | `www.a.com` | no_scheme | 核准設立 | `https://www.a.com/` (works) |
| B | `https://b.com.tw/` | dns_fail | 解散 | none; company dissolved |
| C | `https://c.com/` | cert_error | 核准設立 | not found; registered but site down |
