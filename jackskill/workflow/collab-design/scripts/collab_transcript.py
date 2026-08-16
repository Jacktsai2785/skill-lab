#!/usr/bin/env python3
"""Build a human-readable HTML transcript of a collab-orchestrator run,
showing every model call (proposal / review / synthesis / ...) and the
orchestrator's own audit log (rejections, pauses, budget extensions),
in chronological order. Auto-refreshes so it can be left open in a browser
while the run continues in the background."""
import html
import json
import os
import re
import sqlite3
import sys
from pathlib import Path

LEDGER = Path.home() / ".collab-orchestrator" / "ledger.db"
ARTIFACTS = Path.home() / ".collab-orchestrator" / "artifacts"
DASHBOARD_URL = os.environ.get(
    "COLLAB_DASHBOARD_URL", "http://127.0.0.1:8787"
).rstrip("/")

ROLE_LABEL = {
    "scout": "外部證據蒐集 (Scout)",
    "proposer": "提案 (Proposal)",
    "dissenter": "異議 (Dissent)",
    "reviewer": "交叉審查 (Review)",
    "normalizer": "議題正規化 (Normalize)",
    "reviser": "修訂 (Revision)",
    "verifier": "驗證 (Verification)",
    "judge": "裁決 (Judge)",
    "auditor": "最終稽核 (Final Audit)",
    "synthesizer": "整合定案 (Synthesis)",
}
MODEL_LABEL = {"claude": "Claude", "codex": "Codex"}
STATUS_BADGE = {
    "committed": ("ok", "已接受"),
    "invalid_output": ("bad", "被拒絕"),
    "started": ("pending", "進行中"),
    "unknown_outcome": ("pending", "結果未知"),
}

TERMINAL_STATES = {
    "completed",
    "completed_with_unverified_hard_ac",
    "cancelled_by_user",
    "escalated_for_redesign",
    "failed_preflight",
    "failed_integrity_check",
}

TERMINAL_LABEL = {
    "completed": "本輪已完成，成果已可交付",
    "completed_with_unverified_hard_ac": "本輪規劃流程已完成",
    "cancelled_by_user": "本輪已取消",
    "escalated_for_redesign": "本輪已停止，需重新設計",
    "failed_preflight": "本輪未啟動，前置檢查失敗",
    "failed_integrity_check": "本輪已停止，完整性檢查失敗",
}


def esc(s):
    return html.escape(str(s if s is not None else ""))


def load_artifact(artifact_id):
    if not artifact_id:
        return None
    p = ARTIFACTS / f"{artifact_id}.artifact"
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text())
    except Exception:
        return None


def render_list_field(items, label):
    if not items:
        return ""
    lis = "".join(f"<li>{esc(x)}</li>" for x in items)
    return f"<div class='subfield'><span class='k'>{esc(label)}</span><ul>{lis}</ul></div>"


def render_proposal(payload):
    out = [f"<div class='design'>{esc(payload.get('design', ''))}</div>"]
    decisions = payload.get("decisions") or []
    if decisions:
        out.append("<h4>決策</h4>")
        for d in decisions:
            out.append("<div class='decision-card'>")
            out.append(f"<div class='decision-head'>[{esc(d.get('domain',''))}] {esc(d.get('choice',''))}</div>")
            if d.get("rationale"):
                out.append(f"<div class='rationale'>{esc(d['rationale'])}</div>")
            refs = (d.get("constraint_refs") or []) + (d.get("criterion_refs") or [])
            if refs:
                out.append(f"<div class='refs'>refs: {esc(', '.join(refs))}</div>")
            out.append(render_list_field(d.get("tradeoffs"), "取捨"))
            out.append("</div>")
    risks = payload.get("risks") or []
    if risks:
        out.append("<h4>風險</h4><ul class='risks'>")
        for r in risks:
            sev = esc(r.get("severity", ""))
            out.append(
                f"<li><span class='sev sev-{sev}'>{sev}</span> "
                f"{esc(r.get('description',''))}"
                + (f" — <i>{esc(r.get('mitigation'))}</i>" if r.get("mitigation") else "")
                + "</li>"
            )
        out.append("</ul>")
    return "".join(out)


def _render_finding_card(f):
    sev = esc(f.get("severity", ""))
    ftype = esc(f.get("finding_type", ""))
    out = ["<div class='finding-card'>"]
    out.append(
        f"<div class='finding-head'>"
        f"<span class='sev sev-{sev}'>{sev}</span>"
        f"<span class='ftype'>{ftype}</span>"
        f"<span class='domain'>{esc(f.get('domain',''))} / {esc(f.get('subject',''))}</span>"
        f"</div>"
    )
    out.append(f"<div class='claim'><b>主張：</b>{esc(f.get('claim',''))}</div>")
    if f.get("evidence_quote"):
        source = f.get("evidence_source_id")
        out.append(
            f"<div class='quote'>引用：「{esc(f['evidence_quote'])}」"
            + (f" <span class='refs'>[{esc(source)}]</span>" if source else "")
            + "</div>"
        )
    if f.get("impact"):
        out.append(f"<div><b>影響：</b>{esc(f['impact'])}</div>")
    if f.get("resolution_condition"):
        out.append(f"<div><b>解決條件：</b>{esc(f['resolution_condition'])}</div>")
    basis = f.get("basis") or {}
    refs = (basis.get("constraint_refs") or []) + (basis.get("criterion_refs") or [])
    if refs:
        out.append(f"<div class='refs'>refs: {esc(', '.join(refs))}</div>")
    conf = f.get("confidence")
    if conf is not None:
        out.append(f"<div class='conf'>信心度：{conf}</div>")
    out.append("</div>")
    return "".join(out)


def render_review(payload):
    findings = payload.get("findings") or []
    if not findings:
        return "<p class='muted'>沒有提出任何 finding（對另一方提案沒有異議）。</p>"
    out = [f"<p class='muted'>對另一方提案提出 {len(findings)} 項意見／不認同點：</p>"]
    out.extend(_render_finding_card(f) for f in findings)
    return "".join(out)


def render_normalize(payload):
    clusters = payload.get("clusters") or []
    if not clusters:
        return "<p class='muted'>沒有提出分群建議。</p>"
    out = []
    for c in clusters:
        out.append("<div class='decision-card'>")
        out.append(f"<div class='decision-head'>{esc(c.get('existing_issue_id') or '(新議題)')}</div>")
        out.append(f"<div>finding_ids: {esc(', '.join(c.get('finding_ids') or []))}</div>")
        out.append(f"<div>confidence: {esc(c.get('confidence'))}</div>")
        if c.get("reason"):
            out.append(f"<div>{esc(c['reason'])}</div>")
        out.append("</div>")
    return "".join(out)


def render_synthesis(payload):
    out = [f"<div class='design'>{esc(payload.get('recommendation',''))}</div>"]
    dl = payload.get("decision_log") or []
    if dl:
        out.append("<h4>決策紀錄</h4><ul>")
        for d in dl:
            out.append(f"<li>{esc(d.get('decision',''))} <span class='refs'>(source: {esc(d.get('source',''))})</span></li>")
        out.append("</ul>")
    acs = payload.get("ac_results") or []
    if acs:
        out.append("<h4>驗收條件</h4><ul>")
        for a in acs:
            out.append(f"<li>{esc(a.get('criterion_ref',''))}: {esc(a.get('status',''))}"
                       f" — {esc((a.get('detail') or {}).get('explanation',''))}</li>")
        out.append("</ul>")
    tr = payload.get("test_recommendations") or []
    out.append(render_list_field(tr, "測試建議"))
    return "".join(out)


def render_scout(payload):
    sources = payload.get("sources") or []
    out = []
    if sources:
        out.append(f"<p class='muted'>蒐集到 {len(sources)} 筆外部證據來源：</p>")
        for s in sources:
            out.append("<div class='decision-card'>")
            out.append(
                f"<div class='decision-head'>"
                f"<a href='{esc(s.get('source_url',''))}' target='_blank' rel='noopener'>"
                f"{esc(s.get('title') or s.get('source_url',''))}</a>"
                f" <span class='refs'>[{esc(s.get('source_type',''))}]</span></div>"
            )
            if s.get("claim"):
                out.append(f"<div class='claim'><b>主張：</b>{esc(s['claim'])}</div>")
            if s.get("excerpt"):
                out.append(f"<div class='quote'>摘錄：「{esc(s['excerpt'])}」</div>")
            out.append("</div>")
    else:
        out.append("<p class='muted'>沒有找到可用的外部證據來源。</p>")
    out.append(render_list_field(payload.get("unresolved_questions"), "未解決的問題"))
    return "".join(out)


def render_dissent(payload):
    dissents = payload.get("dissents") or []
    if not dissents:
        return "<p class='muted'>沒有提出異議。</p>"
    out = [f"<p class='muted'>對 {len(dissents)} 項議題提出異議：</p>"]
    for d in dissents:
        out.append("<div class='finding-card'>")
        out.append(f"<div class='finding-head'><span class='domain'>{esc(d.get('issue_ref',''))}</span></div>")
        if d.get("unproven_assumption"):
            out.append(f"<div class='claim'><b>未證實假設：</b>{esc(d['unproven_assumption'])}</div>")
        if d.get("falsifier"):
            out.append(f"<div><b>可證偽條件：</b>{esc(d['falsifier'])}</div>")
        if d.get("irreversible_outcome"):
            out.append(f"<div><b>不可逆後果：</b>{esc(d['irreversible_outcome'])}</div>")
        if d.get("recovery_plan"):
            out.append(f"<div><b>復原計畫：</b>{esc(d['recovery_plan'])}</div>")
        refs = d.get("evidence_refs") or []
        if refs:
            out.append(f"<div class='refs'>evidence: {esc(', '.join(refs))}</div>")
        out.append("</div>")
    return "".join(out)


def render_verification(payload):
    # Two shapes share the "verifier" role: the collab-design batch verdict
    # ({"verdicts": [...], "reasoning": ...}) and the engineering-review
    # single-finding verdict ({"verdict": "confirmed|rejected", ...}).
    if "verdicts" in payload:
        verdicts = payload.get("verdicts") or []
        if not verdicts:
            return "<p class='muted'>沒有驗證結果。</p>"
        out = []
        for v in verdicts:
            verdict = esc(v.get("verdict", ""))
            cls = "ok" if verdict == "passed" else "bad"
            out.append(
                f"<div class='decision-card'><div class='decision-head'>"
                f"<span class='badge badge-{cls}'>{verdict}</span> {esc(v.get('issue_id',''))}"
                f"</div></div>"
            )
        if payload.get("reasoning"):
            out.append(f"<div class='rationale' style='margin-top:8px'><b>理由：</b>{esc(payload['reasoning'])}</div>")
        return "".join(out)
    verdict = esc(payload.get("verdict", ""))
    cls = "ok" if verdict == "confirmed" else "bad"
    out = [f"<div class='decision-card'><div class='decision-head'><span class='badge badge-{cls}'>{verdict}</span></div>"]
    if payload.get("evidence_quote"):
        out.append(
            f"<div class='quote'>引用：「{esc(payload['evidence_quote'])}」"
            + (f" <span class='refs'>[{esc(payload.get('evidence_source_id'))}]</span>"
               if payload.get("evidence_source_id") else "")
            + "</div>"
        )
    if payload.get("reason"):
        out.append(f"<div><b>理由：</b>{esc(payload['reason'])}</div>")
    out.append("</div>")
    return "".join(out)


def render_judge(payload):
    disp = esc(payload.get("disposition", ""))
    out = [f"<div class='decision-card'><div class='decision-head'>裁決：{disp}</div>"]
    if payload.get("issue_ref"):
        out.append(f"<div class='refs'>issue: {esc(payload['issue_ref'])}</div>")
    refs = (payload.get("constraint_refs") or []) + (payload.get("criterion_refs") or [])
    if refs:
        out.append(f"<div class='refs'>refs: {esc(', '.join(refs))}</div>")
    if payload.get("reason"):
        out.append(f"<div class='rationale'><b>理由：</b>{esc(payload['reason'])}</div>")
    conf = payload.get("confidence")
    if conf is not None:
        out.append(f"<div class='conf'>信心度：{conf}</div>")
    out.append("</div>")
    coverage = payload.get("evidence_coverage") or []
    if coverage:
        out.append("<h4>證據覆蓋</h4>")
        for c in coverage:
            out.append("<div class='finding-card'>")
            out.append(f"<div class='claim'><b>主張：</b>{esc(c.get('claim',''))}</div>")
            basis = c.get("basis_refs") or []
            if basis:
                out.append(f"<div class='refs'>依據: {esc(', '.join(basis))}</div>")
            ev = c.get("evidence_refs") or []
            if ev:
                out.append(f"<div class='refs'>證據: {esc(', '.join(ev))}</div>")
            out.append("</div>")
    return "".join(out)


def render_audit(payload):
    blockers = payload.get("new_blockers") or []
    if not blockers:
        return "<p class='muted'>沒有新增 blocker（候選結論通過最終稽核）。</p>"
    out = [f"<p class='muted'>最終稽核提出 {len(blockers)} 項新 blocker：</p>"]
    out.extend(_render_finding_card(b) for b in blockers)
    return "".join(out)


def render_evidence_repair(payload):
    # Not tied to one role: both "reviewer" and "auditor" calls fall back to
    # EVIDENCE_QUOTE_REPAIR_SCHEMA when their evidence_quote couldn't be
    # located verbatim in the source text (see engine.py
    # _invoke_with_evidence_repair). The card header's repair-attempt badge
    # already explains why; this only needs to show what got resubmitted.
    repairs = payload.get("repairs") or []
    if not repairs:
        return "<p class='muted'>沒有引用修復內容。</p>"
    out = [f"<p class='muted'>針對 {len(repairs)} 筆對不到原文的引用重新提交精確文字：</p>"]
    for r in repairs:
        out.append("<div class='decision-card'>")
        out.append(f"<div class='decision-head'>finding #{esc(r.get('finding_index',''))}</div>")
        if r.get("evidence_source_id"):
            out.append(f"<div class='refs'>來源: {esc(r['evidence_source_id'])}</div>")
        out.append(f"<div class='quote'>「{esc(r.get('evidence_quote',''))}」</div>")
        out.append("</div>")
    return "".join(out)


def render_revision(payload):
    revisions = payload.get("revisions") or []
    if not revisions:
        return "<p class='muted'>沒有提出任何修訂。</p>"
    out = [f"<p class='muted'>本次修訂涵蓋 {len(revisions)} 項議題：</p>"]
    for r in revisions:
        out.append("<div class='decision-card'>")
        out.append(f"<div class='decision-head'>{esc(r.get('issue_id',''))}</div>")
        if r.get("change_summary"):
            out.append(f"<div class='rationale'><b>變更摘要：</b>{esc(r['change_summary'])}</div>")
        if r.get("revised_content"):
            out.append(f"<div class='design' style='margin-top:6px'>{esc(r['revised_content'])}</div>")
        out.append("</div>")
    return "".join(out)


RENDERERS = {
    "scout": render_scout,
    "proposer": render_proposal,
    "dissenter": render_dissent,
    "reviewer": render_review,
    "normalizer": render_normalize,
    "reviser": render_revision,
    "verifier": render_verification,
    "judge": render_judge,
    "auditor": render_audit,
    "synthesizer": render_synthesis,
}


def render_generic(payload):
    return f"<pre class='raw'>{esc(json.dumps(payload, ensure_ascii=False, indent=2))}</pre>"


def _json_list(value):
    try:
        parsed = json.loads(value or "[]")
    except (TypeError, json.JSONDecodeError):
        return []
    return parsed if isinstance(parsed, list) else []


def render_pending_decisions(rows, run_id):
    """Render the human gate that the read-only transcript cannot answer.

    The dashboard is deliberately the mutation surface: this page can make a
    pending decision impossible to miss, but never submits an answer itself.
    """
    if not rows:
        return ""
    cards = []
    for row in rows:
        options = _json_list(row["options_json"])
        options_html = []
        for option in options:
            option_id = str(option.get("option_id", ""))
            recommended = option_id == (row["recommended_option_id"] or "")
            options_html.append(
                "<li{}><code>{}</code>{} — {}{}</li>".format(
                    " class='recommended'" if recommended else "",
                    esc(option_id),
                    "（工具預設建議）" if recommended else "",
                    esc(option.get("impact", "")),
                    ("<div class='tradeoff'>" + esc(option.get("tradeoff", ""))
                     + "</div>") if option.get("tradeoff") else "",
                ))
        cards.append(
            "<section class='decision-card'>"
            f"<div class='decision-trigger'>{esc(row['trigger'])}</div>"
            f"<h3>{esc(row['question'])}</h3>"
            + (f"<p>{esc(row['why_now'])}</p>" if row["why_now"] else "")
            + "<ul>" + "".join(options_html) + "</ul>"
            + "</section>")
    return (
        "<section class='decision-alert' role='alert'>"
        "<div><strong>⏸ 需要你的決策</strong><p>模型已無法再以證據自行收斂。"
        "此即時頁唯讀，不會替你選擇；請在 dashboard 檢視完整依據並按鈕作答。</p></div>"
        f"<a class='decision-link' href='{esc(DASHBOARD_URL)}' target='_blank'"
        " rel='noopener'>開啟決策 dashboard</a>"
        "<div class='decision-run'>run: <code>" + esc(run_id) + "</code></div>"
        + "".join(cards) + "</section>")


def render_terminal_delivery(run_status, run_id, ac_rows):
    """Render the durable handoff in the same tab the user has been watching."""
    if run_status not in TERMINAL_STATES:
        return ""

    successful = run_status in {"completed", "completed_with_unverified_hard_ac"}
    hard_unverified = [
        row for row in ac_rows
        if row["criticality"] == "hard"
        and row["status"] not in {"satisfied", "accepted_risk"}
    ]
    accepted_risks = [row for row in ac_rows if row["status"] == "accepted_risk"]
    soft_unverified = [
        row for row in ac_rows
        if row["criticality"] != "hard" and row["status"] != "satisfied"
    ]
    report_href = f"./{run_id}.html"
    title = TERMINAL_LABEL.get(run_status, "本輪已結束")
    icon = "✓" if successful else "!"

    def render_group(rows, heading, css_class):
        if not rows:
            return ""
        details = []
        for row in rows:
            try:
                detail = json.loads(row["detail_json"] or "{}")
            except (TypeError, json.JSONDecodeError):
                detail = {}
            explanation = detail.get("explanation") or "尚未提供說明。"
            recommendation = detail.get("test_recommendation") or ""
            details.append(
                "<li>"
                f"<strong>{esc(row['criterion_ref'])}</strong>"
                f" <span class='badge badge-pending'>{esc(row['status'])}</span>"
                f"<div>{esc(explanation)}</div>"
                + (f"<div class='delivery-test'><b>建議驗證：</b>{esc(recommendation)}</div>"
                   if recommendation else "")
                + "</li>"
            )
        return (
            f"<section class='delivery-group {esc(css_class)}'>"
            f"<h3>{esc(heading)}（{len(rows)}）</h3>"
            "<ul class='delivery-details'>" + "".join(details) + "</ul></section>"
        )

    if successful:
        message = "最終整合稿與 Decision Record 已產生；以下是進入實作前的驗證清單。"
    else:
        message = "本輪已進入終止狀態，請查看報告確認原因與可保留成果。"

    return (
        "<dialog class='completion-dialog' open aria-labelledby='completion-title'>"
        "<form method='dialog' class='completion-dialog-inner'>"
        f"<div class='completion-icon'>{icon}</div>"
        f"<h2 id='completion-title'>{esc(title)}</h2>"
        f"<p>{esc(message)}</p>"
        + ("<div class='delivery-warning'><strong>規劃流程已完成：</strong>"
           f"{len(hard_unverified)} 項硬性驗收需在實作前補證；"
           f"另有 {len(accepted_risks)} 項已接受風險、"
           f"{len(soft_unverified)} 項軟性驗證建議。</div>"
           if hard_unverified or accepted_risks or soft_unverified else "")
        + render_group(hard_unverified, "硬性驗收待補證", "delivery-hard")
        + render_group(accepted_risks, "已接受風險", "delivery-risk")
        + render_group(soft_unverified, "軟性驗證建議", "delivery-soft")
        + "<div class='delivery-actions'>"
        f"<a class='delivery-primary' href='{esc(report_href)}' target='_blank'>查看成果報告</a>"
        f"<a class='delivery-secondary' href='{esc(DASHBOARD_URL)}' target='_blank' rel='noopener'>查看協作摘要</a>"
        "<button value='close'>關閉通知，留在討論紀錄</button>"
        "</div>"
        f"<div class='decision-run'>run: <code>{esc(run_id)}</code></div>"
        "</form></dialog>"
    )


def _latest_brief_prompt(cur, run_id: str) -> str | None:
    # The brief itself has no dedicated table — it travels inside every
    # checkpoint snapshot. Any checkpoint has the same brief.prompt (the
    # brief doesn't change mid-run), so the most recent one is fine.
    cur.execute(
        "SELECT artifact_id FROM artifacts WHERE run_id = ?"
        " AND kind = 'checkpoint_snapshot' ORDER BY created_at DESC LIMIT 1",
        (run_id,))
    row = cur.fetchone()
    if not row:
        return None
    snap = load_artifact(row["artifact_id"])
    if not snap:
        return None
    return ((snap.get("brief") or {}).get("prompt") or "").strip() or None


def build(run_id: str, topic: str | None = None) -> str:
    con = sqlite3.connect(str(LEDGER))
    con.row_factory = sqlite3.Row
    cur = con.cursor()

    cur.execute(
        "SELECT call_id, adapter, role, status, output_artifact_id, attempt_count,"
        " idempotency_key, started_at, committed_at FROM model_calls WHERE run_id = ?"
        " ORDER BY started_at", (run_id,))
    calls = cur.fetchall()

    cur.execute(
        "SELECT event_type, actor, payload_redacted_json, created_at"
        " FROM audit_events WHERE run_id = ? ORDER BY created_at", (run_id,))
    events = cur.fetchall()

    cur.execute("SELECT * FROM runs WHERE run_id = ?", (run_id,))
    run_row = cur.fetchone()
    run_status = run_row["status"] if run_row else "?"
    cur.execute(
        "SELECT criterion_ref, criticality, status, detail_json"
        " FROM ac_results WHERE run_id = ?"
        " ORDER BY CASE criticality WHEN 'hard' THEN 0 ELSE 1 END, criterion_ref",
        (run_id,))
    ac_rows = cur.fetchall()
    cur.execute(
        "SELECT card_id, trigger, question, why_now, options_json,"
        " recommended_option_id, recommendation_reasoning"
        " FROM decision_cards WHERE run_id = ? AND status = 'pending'"
        " ORDER BY created_at, card_id",
        (run_id,))
    pending_decisions = cur.fetchall()

    if not topic:
        prompt = _latest_brief_prompt(cur, run_id)
        if prompt:
            topic = (prompt[:100] + "…") if len(prompt) > 100 else prompt
    topic_html = (
        f'<div class="topic">{esc(topic)}</div>' if topic else ""
    )
    terminal = run_status in TERMINAL_STATES
    refresh_meta = "" if terminal else '<meta http-equiv="refresh" content="12">'
    page_title = (
        f"✓ collab {run_id} 成果已可交付"
        if run_status in {"completed", "completed_with_unverified_hard_ac"}
        else f"collab {run_id} 即時討論記錄"
    )
    status_help = (
        "本輪已停止自動刷新；請由成果交付面板開啟正式報告。"
        if terminal
        else "每 12 秒自動整頁重新整理（run 仍在背景執行中可持續看到新內容）"
    )
    terminal_delivery = render_terminal_delivery(run_status, run_id, ac_rows)

    chips = []
    cards = []
    for idx, c in enumerate(calls):
        role = c["role"]
        model = c["adapter"]
        anchor = f"call-{idx}"
        badge_cls, badge_txt = STATUS_BADGE.get(c["status"], ("pending", c["status"]))
        # A transcript preserves failed attempts for auditability.  Once the
        # same model/role has later submitted a valid result, a red historical
        # badge reads like the run is still broken.  Keep the failed attempt,
        # but label its current meaning plainly.
        superseded_rejection = (
            c["status"] == "invalid_output"
            and any(later["adapter"] == model and later["role"] == role
                    and later["status"] == "committed"
                    for later in calls[idx + 1:])
        )
        if superseded_rejection:
            badge_cls, badge_txt = "resolved", "曾被拒絕，後續已修正"
        # A ":repairN:" segment in the idempotency key means this call is
        # NOT a fresh, independent call of this role — it's the orchestrator
        # asking the SAME model to fix specific bad evidence-quote citations
        # from its own immediately-preceding call in this role (see
        # engine.py's _invoke_with_evidence_repair). Rendered as a plain
        # extra card it reads as "this model did the step twice", which is
        # misleading — labelling it distinctly makes the true call count and
        # sequence legible at a glance.
        repair_match = re.search(r":repair(\d+):", c["idempotency_key"] or "")
        label = ROLE_LABEL.get(role, role)
        if repair_match:
            label += f" · 引用修復重試 (第 {repair_match.group(1)} 次)"
        chips.append(
            f'<a class="chip chip-{badge_cls}{" chip-repair" if repair_match else ""}" href="#{anchor}">'
            f'<span class="chip-model model-{esc(model)}">{esc(MODEL_LABEL.get(model, model))}</span>'
            f' {esc(label)}</a>'
        )
        artifact = load_artifact(c["output_artifact_id"]) if c["status"] == "committed" else None
        payload = (artifact or {}).get("payload") if artifact else None
        if payload is None:
            body = "<p class='muted'>(尚無已提交內容"
            if c["status"] == "invalid_output":
                body += (" — 這次輸出被拒絕；後續同一角色已成功提交修正版"
                         if superseded_rejection
                         else " — 這次輸出被拒絕，見下方稽核紀錄")
            body += ")</p>"
        else:
            # A ":repairN:" call replaces its role's normal schema with
            # EVIDENCE_QUOTE_REPAIR_SCHEMA (see render_evidence_repair) —
            # route on payload shape, not role, so this doesn't silently
            # fall through to render_review/render_audit and print "no
            # findings" for what is actually a quote resubmission.
            if isinstance(payload, dict) and "repairs" in payload:
                renderer = render_evidence_repair
            else:
                renderer = RENDERERS.get(role, render_generic)
            try:
                body = renderer(payload)
            except Exception as e:
                body = f"<p class='muted'>(渲染失敗: {esc(e)})</p>" + render_generic(payload)
        # <details> defaults to closed so the page opens as a scannable
        # task list; click any card (or its matching chip above) to expand.
        cards.append(f"""
        <details class="card{' card-repair' if repair_match else ''}" id="{anchor}">
          <summary class="card-head">
            <span class="model model-{esc(model)}">{esc(MODEL_LABEL.get(model, model))}</span>
            <span class="role">{esc(label)}</span>
            <span class="badge badge-{badge_cls}">{esc(badge_txt)}</span>
            <span class="ts">{esc(c['started_at'])}</span>
            <span class="attempt">第 {c['attempt_count']} 次嘗試</span>
          </summary>
          {"<div class='repair-note'>⚠ 這不是一次全新的" + esc(ROLE_LABEL.get(role, role)) + "——是同一個模型上一次呼叫因為引用了對不到原文的證據文字，被要求只修正那些引用後重新提交，其餘內容延續前一次。</div>" if repair_match else ""}
          <div class="card-body">{body}</div>
        </details>""")

    log_rows = []
    for e in events:
        try:
            payload = json.loads(e["payload_redacted_json"])
        except Exception:
            payload = {}
        log_rows.append(
            f"<tr><td class='ts'>{esc(e['created_at'])}</td>"
            f"<td>{esc(e['event_type'])}</td>"
            f"<td><code>{esc(json.dumps(payload, ensure_ascii=False))}</code></td></tr>"
        )

    return f"""<!doctype html>
<html lang="zh-Hant"><head>
<meta charset="utf-8">
{refresh_meta}
<title>{esc(page_title)}</title>
<style>
  :root {{
    --bg:#0f1115; --panel:#171a21; --border:#2a2e38; --fg:#e6e8ec; --muted:#9aa1ad;
    --accent:#7aa2f7; --claude:#c98a4b; --codex:#4bc9a0;
    --ok:#3fb950; --bad:#f85149; --pending:#d29922;
  }}
  @media (prefers-color-scheme: light) {{
    :root {{ --bg:#f6f7f9; --panel:#ffffff; --border:#e2e5ea; --fg:#1b1f27; --muted:#5b6472; }}
  }}
  * {{ box-sizing:border-box; }}
  body {{ background:var(--bg); color:var(--fg); font-family:-apple-system,"Segoe UI",Roboto,sans-serif;
         margin:0; padding:24px; line-height:1.55; }}
  h1 {{ font-size:1.3rem; margin:0 0 4px; }}
  .topic {{ font-size:1rem; color:var(--fg); background:var(--panel); border:1px solid var(--border);
            border-left:3px solid var(--accent); border-radius:0 8px 8px 0; padding:10px 14px;
            margin-bottom:14px; }}
  .run-meta {{ color:var(--muted); font-size:0.85rem; margin-bottom:16px; }}
  .status-pill {{ display:inline-block; padding:2px 10px; border-radius:999px; background:var(--panel);
                  border:1px solid var(--border); font-size:0.8rem; }}
  .chips {{ display:flex; gap:8px; flex-wrap:wrap; margin-bottom:20px; }}
  .chip {{ display:inline-flex; gap:6px; align-items:center; padding:4px 10px; border-radius:999px;
           border:1px solid var(--border); background:var(--panel); color:var(--fg); font-size:0.78rem;
           text-decoration:none; }}
  .chip:hover {{ border-color:var(--accent); }}
  .chip-bad {{ border-color:color-mix(in srgb, var(--bad) 50%, var(--border)); }}
  .chip-resolved {{ border-color:color-mix(in srgb, var(--ok) 50%, var(--border)); opacity:0.78; }}
  .chip-pending {{ border-color:color-mix(in srgb, var(--pending) 50%, var(--border)); }}
  .chip-repair {{ border-style:dashed; opacity:0.8; }}
  .chip-model {{ font-weight:700; }}
  .card {{ background:var(--panel); border:1px solid var(--border); border-radius:10px;
           padding:16px 18px; margin-bottom:16px; margin-top:0; }}
  .card-repair {{ border-style:dashed; margin-left:22px; }}
  .repair-note {{ font-size:0.8rem; color:var(--pending); background:color-mix(in srgb, var(--pending) 12%, transparent);
                   border-radius:6px; padding:8px 10px; margin-bottom:10px; }}
  .card[open] {{ border-color:var(--accent); }}
  .card summary {{ list-style:none; cursor:pointer; }}
  .card summary::-webkit-details-marker {{ display:none; }}
  .card summary::before {{ content:"▸"; color:var(--muted); margin-right:8px; display:inline-block;
                            transition:transform .15s; }}
  .card[open] summary::before {{ transform:rotate(90deg); }}
  .card-head {{ display:flex; gap:10px; align-items:center; flex-wrap:wrap; }}
  .card[open] .card-head {{ margin-bottom:10px; }}
  .model {{ font-weight:700; padding:2px 8px; border-radius:6px; }}
  .model-claude {{ background:color-mix(in srgb, var(--claude) 25%, transparent); color:var(--claude); }}
  .model-codex {{ background:color-mix(in srgb, var(--codex) 25%, transparent); color:var(--codex); }}
  .role {{ color:var(--accent); font-weight:600; }}
  .badge {{ padding:1px 8px; border-radius:6px; font-size:0.75rem; }}
  .badge-ok {{ background:color-mix(in srgb, var(--ok) 20%, transparent); color:var(--ok); }}
  .badge-bad {{ background:color-mix(in srgb, var(--bad) 20%, transparent); color:var(--bad); }}
  .badge-resolved {{ background:color-mix(in srgb, var(--ok) 16%, transparent); color:var(--ok); }}
  .badge-pending {{ background:color-mix(in srgb, var(--pending) 20%, transparent); color:var(--pending); }}
  .ts {{ color:var(--muted); margin-left:auto; }}
  .attempt {{ color:var(--muted); }}
  .card-body {{ font-size:0.92rem; }}
  .design {{ white-space:pre-wrap; }}
  h4 {{ margin:14px 0 6px; font-size:0.9rem; color:var(--muted); text-transform:uppercase; letter-spacing:.04em; }}
  .decision-card, .finding-card {{ border-left:3px solid var(--border); padding:8px 12px; margin:8px 0;
                                    background:color-mix(in srgb, var(--fg) 4%, transparent); border-radius:0 6px 6px 0; }}
  .decision-head {{ font-weight:600; }}
  .rationale {{ color:var(--muted); margin-top:4px; }}
  .refs {{ font-size:0.8rem; color:var(--accent); margin-top:4px; }}
  .finding-head {{ display:flex; gap:8px; align-items:center; margin-bottom:6px; font-size:0.85rem; }}
  .sev {{ padding:1px 7px; border-radius:5px; font-weight:700; font-size:0.75rem; }}
  .sev-critical {{ background:color-mix(in srgb, var(--bad) 30%, transparent); color:var(--bad); }}
  .sev-high {{ background:color-mix(in srgb, var(--bad) 20%, transparent); color:var(--bad); }}
  .sev-medium {{ background:color-mix(in srgb, var(--pending) 20%, transparent); color:var(--pending); }}
  .sev-low {{ background:color-mix(in srgb, var(--muted) 20%, transparent); color:var(--muted); }}
  .ftype {{ color:var(--muted); font-style:italic; }}
  .domain {{ color:var(--muted); }}
  .quote {{ font-style:italic; color:var(--muted); margin:4px 0; }}
  .conf {{ color:var(--muted); font-size:0.8rem; margin-top:4px; }}
  .subfield {{ margin-top:6px; }}
  .subfield .k {{ font-weight:600; color:var(--muted); font-size:0.8rem; }}
  .muted {{ color:var(--muted); }}
  .raw {{ white-space:pre-wrap; font-size:0.78rem; background:color-mix(in srgb, var(--fg) 5%, transparent);
          padding:10px; border-radius:6px; overflow-x:auto; }}
  table {{ width:100%; border-collapse:collapse; font-size:0.82rem; }}
  td {{ border-top:1px solid var(--border); padding:6px 8px; vertical-align:top; }}
  code {{ color:var(--muted); }}
  .audit-details {{ margin-top:28px; }}
  .audit-details summary {{ cursor:pointer; color:var(--muted); }}
  .decision-alert {{ position:sticky; top:12px; z-index:10; background:var(--panel);
      border:2px solid var(--pending); border-radius:10px; padding:16px 18px; margin:0 0 20px;
      box-shadow:0 12px 30px color-mix(in srgb, #000 36%, transparent); }}
  .decision-alert strong {{ color:var(--pending); font-size:1.08rem; }}
  .decision-alert p {{ margin:5px 0 10px; }}
  .decision-link {{ display:inline-block; background:var(--pending); color:#16110a;
      border-radius:6px; padding:7px 12px; font-weight:700; text-decoration:none; }}
  .decision-run {{ color:var(--muted); font-size:0.8rem; margin:8px 0; }}
  .decision-card {{ border-left:3px solid var(--pending); background:color-mix(in srgb, var(--pending) 10%, transparent);
      border-radius:0 6px 6px 0; padding:9px 12px; margin-top:10px; }}
  .decision-card h3 {{ margin:3px 0 6px; font-size:0.95rem; }}
  .decision-card ul {{ margin:5px 0 0; padding-left:20px; }}
  .decision-card li {{ margin:4px 0; }}
  .decision-card .recommended {{ color:var(--pending); }}
  .decision-trigger, .tradeoff {{ color:var(--muted); font-size:0.8rem; }}
  .completion-dialog {{ position:fixed; inset:0; z-index:100; width:min(760px, calc(100% - 32px));
      max-height:calc(100vh - 32px); overflow:auto; margin:auto; color:var(--fg); background:var(--panel);
      border:2px solid var(--ok); border-radius:14px; padding:0;
      box-shadow:0 24px 80px rgba(0,0,0,.72); }}
  .completion-dialog::backdrop {{ background:rgba(5,8,14,.78); backdrop-filter:blur(3px); }}
  .completion-dialog-inner {{ padding:24px; }}
  .completion-dialog h2 {{ margin:4px 0 8px; }}
  .completion-icon {{ width:42px; height:42px; display:grid; place-items:center; border-radius:50%;
      color:#07130d; background:var(--ok); font-size:1.45rem; font-weight:800; }}
  .delivery-warning {{ border-left:3px solid var(--pending); padding:9px 12px; margin:16px 0;
      background:color-mix(in srgb, var(--pending) 10%, transparent); }}
  .delivery-group {{ margin-top:14px; }}
  .delivery-group h3 {{ margin:0 0 6px; font-size:.92rem; }}
  .delivery-hard h3 {{ color:var(--pending); }}
  .delivery-risk h3 {{ color:var(--muted); }}
  .delivery-soft h3 {{ color:var(--accent); }}
  .delivery-details {{ max-height:240px; overflow:auto; padding-left:22px; }}
  .delivery-details li {{ margin:10px 0; }}
  .delivery-test {{ color:var(--muted); margin-top:3px; font-size:.86rem; }}
  .delivery-actions {{ display:flex; flex-wrap:wrap; gap:9px; margin-top:20px; }}
  .delivery-actions a, .delivery-actions button {{ border:1px solid var(--border); border-radius:7px;
      padding:8px 12px; color:var(--fg); background:transparent; text-decoration:none; cursor:pointer;
      font:inherit; }}
  .delivery-actions .delivery-primary {{ color:#07130d; background:var(--ok); border-color:var(--ok);
      font-weight:750; }}
  .delivery-actions .delivery-secondary {{ border-color:var(--accent); }}
</style>
</head>
<body>
  <h1>collab design — {esc(run_id)}</h1>
  {topic_html}
  <div class="run-meta">
    狀態：<span class="status-pill">{esc(run_status)}</span>
    · {esc(status_help)}
  </div>
  {terminal_delivery}
  {render_pending_decisions(pending_decisions, run_id)}
  <nav class="chips">{"".join(chips)}</nav>
  {"".join(cards)}
  <details class="audit-details">
    <summary>稽核事件記錄（暫停原因／預算調整／狀態轉換）</summary>
    <table>{"".join(log_rows)}</table>
  </details>
</body></html>"""


if __name__ == "__main__":
    run_id = sys.argv[1]
    out_path = sys.argv[2]
    topic = sys.argv[3].strip() if len(sys.argv) > 3 and sys.argv[3].strip() else None
    Path(out_path).write_text(build(run_id, topic), encoding="utf-8")
    print(f"wrote {out_path}")
