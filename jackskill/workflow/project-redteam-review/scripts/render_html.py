#!/usr/bin/env python3
"""把紅隊審查資料渲染成單一自包含 HTML（離線可開、零外部相依）。

預設行為：渲染後**自動用系統預設瀏覽器開啟**，並把來源 JSON **內嵌進 HTML**
（藏在 <script type="application/json">），所以最後專案裡只需要這一份 .html
——資料沒丟、重跑可從 HTML 撈回來。加 --consume 連帶刪掉來源 JSON。

用法:
    python render_html.py <findings.json|report.html> [-o out.html] [--no-open]
                          [--consume] [--applied]
    python render_html.py <report.html> --export-json <findings.json>

JSON 結構見 references/report-template.md 的「結構化 JSON schema」一節。
未知欄位一律忽略，缺欄位走合理預設，讓重跑 / 半填的 JSON 也能渲染。
"""
import argparse
import html
import json
import os
import platform
import re
import shutil
import subprocess
import sys
from pathlib import Path

SEV_CLASS = {"高": "hi", "中": "mid", "低": "lo"}
EMBEDDED_DATA_RE = re.compile(
    r'<script\b[^>]*\bid=["\']redteam-source["\'][^>]*>(.*?)</script\s*>',
    re.IGNORECASE | re.DOTALL,
)


def esc(s):
    return html.escape(str(s if s is not None else ""))


def sev_pill(sev):
    return f'<span class="pill sev-{SEV_CLASS.get(sev, "lo")}">{esc(sev)}</span>'


def cat_tag(cat):
    if not cat:
        return ""
    cls = "cat-ux" if ("產品" in cat or "體驗" in cat or "UX" in cat.upper()) else "cat-tech"
    return f'<span class="cat {cls}">{esc(cat)}</span>'


def load_data(src: Path) -> dict:
    """從 JSON 或本 renderer 產出的 HTML 載入報告資料。"""
    text = src.read_text(encoding="utf-8")
    if src.suffix.lower() != ".html":
        data = json.loads(text)
    else:
        match = EMBEDDED_DATA_RE.search(text)
        if not match:
            raise ValueError(
                f"HTML 內找不到 id=redteam-source 的內嵌資料：{src}"
            )
        data = json.loads(match.group(1))
    if not isinstance(data, dict):
        raise ValueError("報告資料的最外層必須是 JSON object")
    return data


def render(data: dict) -> str:
    meta = data.get("meta", {})
    teams = data.get("teams", [])
    findings = data.get("findings", [])
    conflicts = data.get("conflicts", [])
    bas = data.get("before_after", [])
    actions = data.get("actions", [])
    applied = bool(meta.get("applied", False))

    # team cards
    accent = ["c1", "c2", "c3", "c1", "c2", "c3"]
    cards = []
    for i, t in enumerate(teams):
        counts = t.get("counts", {})
        cnt = " ".join(
            f'<span class="pill sev-{SEV_CLASS.get(s,"lo")}">{counts.get(s)} {s}</span>'
            for s in ("高", "中", "低") if counts.get(s)
        )
        cards.append(f'''    <div class="card {accent[i % 6]}">
      <div class="tag">紅隊 {esc(t.get("idx", i+1))}</div>
      <div class="title">{esc(t.get("title",""))}</div>
      <div class="ang">{esc(t.get("angle",""))}</div>
      <div class="cnt">{cnt}</div>
    </div>''')

    cross = data.get("cross_check", "")
    cross_html = (
        f'<br><span class="ok">✓ 交叉驗證：</span>{esc(cross)}' if cross else ""
    )

    # findings grouped by team (keep input order of teams)
    team_order = [(t.get("title") or t.get("key") or "") for t in teams]
    seen_teams = {t for t in team_order if t}

    def team_key(f):
        return f.get("team", "")
    grouped = []
    for tk in team_order:
        if not tk:  # 跳過無標題的卡片，避免 orphan finding 被誤掛到空標題下
            continue
        items = [f for f in findings if team_key(f) == tk]
        if items:
            grouped.append((tk, items))
    # any findings whose team didn't match a (non-empty) card title
    leftover = [f for f in findings if team_key(f) not in seen_teams]
    if leftover:
        grouped.append(("其他", leftover))

    find_html = []
    for tk, items in grouped:
        find_html.append(f"  <h3>{esc(tk)}</h3>")
        for f in items:
            sev = f.get("severity", "低")
            confidence = f.get("confidence", "")
            confidence_html = (
                f'<span class="pill sev-{SEV_CLASS.get(confidence, "lo")}">'
                f'信心 {esc(confidence)}</span>'
                if confidence else ""
            )
            evidence = f.get("evidence", "")
            evidence_html = (
                f'<div class="ev"><b>證據：</b>{esc(evidence)}</div>'
                if evidence else ""
            )
            find_html.append(f'''  <div class="find {SEV_CLASS.get(sev,"lo")}">
    <div class="row">{sev_pill(sev)}{cat_tag(f.get("category",""))}{confidence_html}<span class="loc">{esc(f.get("location",""))}</span></div>
    <div class="prob">{esc(f.get("problem",""))}</div>
    <div class="sug"><b>建議：</b>{esc(f.get("suggestion",""))}</div>
    {evidence_html}
  </div>''')

    conf_html = []
    for c in conflicts:
        conf_html.append(
            f'  <div class="conf"><span class="vs">{esc(c.get("issue",""))}</span>'
            f' → <span class="lean">傾向：{esc(c.get("lean",""))}</span></div>'
        )

    ba_html = []
    for b in bas:
        is_open = " open" if b.get("open") else ""
        ba_html.append(f'''  <details{is_open}>
    <summary><span class="id">{esc(b.get("id",""))}</span> {esc(b.get("title",""))}　<span style="margin-left:auto">{sev_pill(b.get("severity","低"))}</span></summary>
    <div class="body">
      <div class="meta" style="margin:4px 0 8px">{esc(b.get("file",""))}</div>
      <div class="ba">
        <div class="col before"><div class="h">BEFORE</div><pre>{esc(b.get("before",""))}</pre></div>
        <div class="col after"><div class="h">AFTER</div><pre>{esc(b.get("after",""))}</pre></div>
      </div>
    </div>
  </details>''')

    act_html = []
    for a in actions:
        auto = '<td class="yes">✅</td>' if a.get("auto") else f'<td class="no">❌ {esc(a.get("note",""))}</td>'
        act_html.append(
            f'      <tr><td>{esc(a.get("n",""))}</td><td>{esc(a.get("action",""))}</td>'
            f'<td>{sev_pill(a.get("confidence","低"))}</td><td>{sev_pill(a.get("risk","低"))}</td>{auto}</tr>'
        )

    banner = (
        '<div class="banner banner-ok">✅ 高信心低風險項已套用到工作區。下方 before→after 對應實際變更；'
        '建議用 <code>git diff</code> 複核後再 commit。</div>'
        if applied else
        '<div class="banner">⚠️ 本報告為 skill 產出的<b>提案版</b>，下方「前後比較」為 before→after 設計，'
        '<b>尚未套用 code</b>（要套用請在對話告訴 Claude 要套哪幾條）。</div>'
    )

    redo = '''  <h2>⑥ 下一步：要套用哪幾條？</h2>
  <div class="note">回到 Claude 對話，告訴它要套用上面「排序行動項」中標 ✅ 的哪些建議：
    <ul style="margin:8px 0 0;padding-left:20px">
      <li><b>全套 ✅ 項</b> — 套用所有標「可自動套用」的高信心低風險項</li>
      <li><b>選幾條</b> — 例：「套用 #1 #2 #4」</li>
      <li><b>都先不套</b> — 留著這份報告當參考</li>
    </ul>
    套用後想針對改動再跑一輪確認沒改壞、或想換視角重審 / 深挖某條，直接再講一句重新觸發 skill 即可。
  </div>'''

    # 把來源資料內嵌進 HTML，讓單一 .html 自帶資料（重跑可撈回）。
    # 跳脫 </ 以免提前關閉 <script>；大括號不影響 .format（這是被代入的值，不會二次解析）。
    embed = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")

    return TEMPLATE.format(
        project=esc(meta.get("project", "")),
        date=esc(meta.get("date", "")),
        ptype=esc(meta.get("type", "")),
        dims=esc(" / ".join(meta.get("dimensions", []))),
        banner=banner,
        cards="\n".join(cards),
        cross=cross_html,
        findings="\n".join(find_html),
        conflicts="\n".join(conf_html) or '  <div class="note">無對立建議需裁決。</div>',
        before_after="\n".join(ba_html) or '  <div class="note">無 before/after 提案。</div>',
        actions="\n".join(act_html),
        redo=redo,
        embed=embed,
    )


def open_in_browser(path: Path) -> bool:
    p = str(path)
    try:
        sysname = platform.system()
        if sysname == "Darwin":
            subprocess.run(["open", p], check=False)
            return True
        if sysname == "Windows":
            os.startfile(p)  # type: ignore[attr-defined]
            return True
        # Linux / WSL
        for opener in ("wslview", "xdg-open"):
            if shutil.which(opener):
                subprocess.Popen([opener, p],
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                return True
        if shutil.which("explorer.exe"):  # WSL fallback：用 Windows 路徑
            win = subprocess.run(["wslpath", "-w", p], capture_output=True, text=True)
            subprocess.Popen(["explorer.exe", win.stdout.strip() or p])
            return True
        print(f"（找不到瀏覽器開啟器，請手動開：{p}）", file=sys.stderr)
        return False
    except Exception as e:
        print(f"（自動開啟失敗，請手動開：{p}）{e}", file=sys.stderr)
        return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("source", help="findings JSON 或既有 REDTEAM-REVIEW.html 路徑")
    ap.add_argument("-o", "--out", help="輸出 HTML 路徑（預設與 JSON 同名 .html）")
    ap.add_argument("--no-open", action="store_true", help="渲染後不要自動開瀏覽器（預設會開）")
    ap.add_argument("--consume", action="store_true", help="渲染成功後刪掉來源 JSON（資料已內嵌進 HTML）")
    ap.add_argument("--applied", action="store_true", help="把 meta.applied 設為 true 後渲染")
    ap.add_argument("--export-json", metavar="PATH", help="從來源匯出 JSON 後結束，不渲染 HTML")
    args = ap.parse_args()

    src = Path(args.source)
    try:
        data = load_data(src)
    except FileNotFoundError:
        print(f"找不到來源檔：{src}", file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"內嵌或來源 JSON 格式錯誤（{src}）：{e}", file=sys.stderr)
        sys.exit(1)
    except (OSError, ValueError) as e:
        print(f"無法讀取報告資料（{src}）：{e}", file=sys.stderr)
        sys.exit(1)

    if args.export_json:
        exported = Path(args.export_json)
        exported.write_text(
            json.dumps(data, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(f"已匯出 JSON：{exported}")
        return

    if args.applied:
        data.setdefault("meta", {})["applied"] = True

    out = Path(args.out) if args.out else src.with_suffix(".html")
    out.write_text(render(data), encoding="utf-8")
    print(f"已產出 HTML：{out}")
    if args.consume and src.suffix.lower() == ".json" and src.resolve() != out.resolve():
        try:
            src.unlink()
            print(f"已刪除來源 JSON（資料已內嵌進 HTML）：{src}")
        except OSError as e:
            print(f"（來源 JSON 刪除失敗，可手動清除：{src}）{e}", file=sys.stderr)
    if not args.no_open:
        open_in_browser(out)


TEMPLATE = '''<!DOCTYPE html>
<html lang="zh-Hant">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>紅隊審查報告 — {project}</title>
<style>
  :root{{--bg:#0f1218;--panel:#171b23;--panel2:#1d222c;--line:#2a3140;--text:#e6e9ef;--muted:#9aa4b2;--accent:#6ea8fe;--hi:#ff6b6b;--mid:#ffb454;--lo:#7f8a9b;--add-bg:#11271a;--add-text:#9ff0b8;--del-bg:#2a1416;--del-text:#ffb0b0;--ok:#3ddc84}}
  @media (prefers-color-scheme: light){{:root{{--bg:#f4f6fa;--panel:#fff;--panel2:#f0f3f8;--line:#dde3ec;--text:#1a2230;--muted:#5b6675;--accent:#1f6feb;--add-bg:#e6ffed;--add-text:#1a7f37;--del-bg:#ffeef0;--del-text:#b3242c}}}}
  *{{box-sizing:border-box}}
  body{{margin:0;background:var(--bg);color:var(--text);font-family:-apple-system,"Segoe UI","Noto Sans TC",system-ui,sans-serif;line-height:1.6;font-size:15px}}
  .wrap{{max-width:1100px;margin:0 auto;padding:32px 20px 80px}}
  h1{{font-size:26px;margin:0 0 4px}}
  h2{{font-size:19px;margin:36px 0 14px;padding-bottom:8px;border-bottom:1px solid var(--line)}}
  h3{{font-size:16px;margin:22px 0 10px}}
  .meta{{color:var(--muted);font-size:13.5px;margin-bottom:18px}}
  .meta b{{color:var(--text)}}
  code,pre{{font-family:"SF Mono","JetBrains Mono",Consolas,monospace}}
  .banner{{background:linear-gradient(90deg,#3a2a12,#2a1f10);border:1px solid var(--mid);color:#ffd9a0;border-radius:10px;padding:12px 16px;font-size:14px;margin-bottom:24px}}
  .banner-ok{{background:linear-gradient(90deg,#10301d,#0f261a);border-color:var(--ok);color:var(--ok)}}
  @media (prefers-color-scheme: light){{.banner{{background:#fff6e6;color:#7a4b00}}.banner-ok{{background:#e6ffed;color:#1a7f37}}}}
  .cards{{display:grid;grid-template-columns:repeat(3,1fr);gap:14px;margin:8px 0}}
  @media(max-width:720px){{.cards{{grid-template-columns:1fr}}}}
  .card{{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:16px}}
  .card .tag{{font-size:12px;color:var(--muted);letter-spacing:.04em}}
  .card .title{{font-size:16px;font-weight:600;margin:4px 0 8px}}
  .card .ang{{font-size:13px;color:var(--muted);min-height:54px}}
  .card .cnt{{font-size:13px;margin-top:8px}}
  .pill{{display:inline-block;border-radius:999px;padding:1px 9px;font-size:12px;font-weight:600;line-height:1.7}}
  .sev-hi{{background:rgba(255,107,107,.16);color:var(--hi);border:1px solid var(--hi)}}
  .sev-mid{{background:rgba(255,180,84,.16);color:var(--mid);border:1px solid var(--mid)}}
  .sev-lo{{background:rgba(127,138,155,.16);color:var(--lo);border:1px solid var(--lo)}}
  .cat{{display:inline-block;border-radius:6px;padding:1px 8px;font-size:11.5px;font-weight:600;border:1px solid var(--line);color:var(--muted)}}
  .cat-tech{{color:var(--accent);border-color:var(--accent);background:rgba(110,168,254,.12)}}
  .cat-ux{{color:var(--ok);border-color:var(--ok);background:rgba(61,220,132,.12)}}
  .c1{{border-top:3px solid var(--hi)}}.c2{{border-top:3px solid var(--mid)}}.c3{{border-top:3px solid var(--accent)}}
  .find{{background:var(--panel);border:1px solid var(--line);border-left:3px solid var(--line);border-radius:10px;padding:12px 14px;margin:10px 0}}
  .find.hi{{border-left-color:var(--hi)}}.find.mid{{border-left-color:var(--mid)}}.find.lo{{border-left-color:var(--lo)}}
  .find .loc{{font-family:monospace;font-size:12.5px;color:var(--accent);word-break:break-all}}
  .find .prob{{margin:6px 0 4px}}
  .find .sug{{font-size:14px;color:var(--muted)}}
  .find .ev{{font-size:13px;color:var(--muted);margin-top:3px}}
  .find .sug b,.find .ev b{{color:var(--text)}}
  .row{{display:flex;align-items:center;gap:8px;flex-wrap:wrap}}
  .note{{background:var(--panel2);border:1px dashed var(--line);border-radius:10px;padding:12px 14px;font-size:14px;margin:14px 0}}
  .note .ok{{color:var(--ok);font-weight:600}}
  .ba{{display:grid;grid-template-columns:1fr 1fr;border:1px solid var(--line);border-radius:10px;overflow:hidden;margin:10px 0}}
  @media(max-width:720px){{.ba{{grid-template-columns:1fr}}}}
  .ba .h{{font-size:12px;font-weight:700;letter-spacing:.05em;padding:7px 12px;border-bottom:1px solid var(--line)}}
  .ba .before .h{{background:var(--del-bg);color:var(--del-text)}}
  .ba .after .h{{background:var(--add-bg);color:var(--add-text)}}
  .ba .before{{border-right:1px solid var(--line)}}
  @media(max-width:720px){{.ba .before{{border-right:none;border-bottom:1px solid var(--line)}}}}
  pre{{margin:0;padding:12px;overflow-x:auto;font-size:12.5px;line-height:1.55;background:var(--panel)}}
  .before pre{{background:var(--del-bg)}}.after pre{{background:var(--add-bg)}}
  details{{background:var(--panel);border:1px solid var(--line);border-radius:10px;margin:12px 0;overflow:hidden}}
  summary{{cursor:pointer;padding:12px 14px;font-weight:600;list-style:none;display:flex;align-items:center;gap:10px}}
  summary::-webkit-details-marker{{display:none}}
  summary::before{{content:"▸";color:var(--muted);transition:transform .15s}}
  details[open] summary::before{{transform:rotate(90deg)}}
  summary .id{{font-family:monospace;color:var(--accent)}}
  details .body{{padding:0 14px 14px}}
  .conf{{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:12px 14px;margin:10px 0}}
  .conf .vs{{color:var(--mid);font-weight:600}}.conf .lean{{color:var(--ok)}}
  table{{width:100%;border-collapse:collapse;margin:12px 0;font-size:14px}}
  th,td{{text-align:left;padding:9px 11px;border-bottom:1px solid var(--line)}}
  th{{color:var(--muted);font-weight:600;font-size:13px}}
  tr:hover td{{background:var(--panel2)}}
  .yes{{color:var(--ok);font-weight:700}}.no{{color:var(--lo)}}
  .footer{{color:var(--muted);font-size:12.5px;margin-top:40px;text-align:center}}
</style>
</head>
<body>
<script type="application/json" id="redteam-source">{embed}</script>
<div class="wrap">
  <h1>紅隊審查與最佳設計</h1>
  <div class="meta">專案 <b>{project}</b> ・ 日期 <b>{date}</b> ・ 型態 <b>{ptype}</b> ・ 三面向 <b>{dims}</b></div>
  {banner}
  <h2>① 三隊各自的審視角度</h2>
  <div class="cards">
{cards}
  </div>
  <div class="note">三隊共用同一份「已查證事實基準」，且都被告知刻意的設計鐵則不可當 bug 誤報。{cross}</div>
  <h2>② 各隊關鍵發現</h2>
{findings}
  <h2>③ 衝突裁決</h2>
{conflicts}
  <h2>④ 前後比較（before→after）</h2>
{before_after}
  <h2>⑤ 排序行動項</h2>
  <table>
    <thead><tr><th>#</th><th>行動</th><th>信心</th><th>風險</th><th>可自動套用</th></tr></thead>
    <tbody>
{actions}
    </tbody>
  </table>
{redo}
  <div class="footer">由 project-redteam-review skill 產出 ・ 單一自包含 HTML，離線可開</div>
</div>
</body>
</html>'''


if __name__ == "__main__":
    main()
