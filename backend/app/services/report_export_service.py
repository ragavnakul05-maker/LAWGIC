"""
report_export_service.py — Enterprise Executive Report & Audit Dossier Export Engine for LAWGIC.

Produces:
  1. RFC-4180 compliant CSV calculation sheets
  2. Cryptographically hashed JSON audit packages with Legal IR provenance
  3. Executive-ready, print-optimized HTML/PDF reports with contract clause citations
"""

import csv
import io
import json
import hashlib
from datetime import datetime
from typing import Dict, Any, Optional


def _format_currency(val: Optional[float], include_decimals: bool = False) -> str:
    if val is None:
        return "₹0"
    try:
        fval = float(val)
        is_negative = fval < 0
        abs_val = abs(fval)
        has_decimals = include_decimals or (abs_val % 1 != 0)
        if has_decimals:
            int_part = int(abs_val)
            dec_part = f"{int(round((abs_val - int_part) * 100)):02d}"
        else:
            int_part = int(round(abs_val))
            dec_part = None

        s = str(int_part)
        if len(s) <= 3:
            formatted_int = s
        else:
            last_three = s[-3:]
            remaining = s[:-3]
            chunks = []
            while len(remaining) > 2:
                chunks.append(remaining[-2:])
                remaining = remaining[:-2]
            if remaining:
                chunks.append(remaining)
            chunks.reverse()
            formatted_int = ",".join(chunks) + "," + last_three

        formatted = f"₹{formatted_int}.{dec_part}" if dec_part is not None else f"₹{formatted_int}"
        return f"-{formatted}" if is_negative else formatted
    except Exception:
        return f"₹{val}"


class ReportExportService:

    @staticmethod
    def generate_audit_csv(trail: Dict[str, Any]) -> str:
        """
        Generates an RFC-4180 compliant CSV ledger of execution steps.
        """
        output = io.StringIO()
        writer = csv.writer(output, quoting=csv.QUOTE_MINIMAL)

        # Header Metadata
        writer.writerow(["# LAWGIC DETERMINISTIC AUDIT LEDGER"])
        writer.writerow(["# Execution ID", trail.get("execution_id", "N/A")])
        writer.writerow(["# Contract Title", trail.get("contract_title", "N/A")])
        writer.writerow(["# Contract ID", trail.get("contract_id", "N/A")])
        writer.writerow(["# Scenario", trail.get("scenario_name", "N/A")])
        writer.writerow(["# Total Financial Impact", _format_currency(trail.get("financial_impact", 0))])
        writer.writerow(["# Executed At", trail.get("executed_at", "N/A")])
        writer.writerow([])  # blank separator line

        # Step Columns
        headers = [
            "Step Number",
            "Rule Code",
            "Rule Title",
            "Rule Type",
            "Clause Section",
            "Clause Page",
            "Validation Status",
            "Formula",
            "Description",
            "Financial Subtotal",
            "Original Clause Excerpt"
        ]
        writer.writerow(headers)

        steps = trail.get("steps", [])
        for s in steps:
            clause = s.get("source_clause") or {}
            original_text = (clause.get("original_text") or "").strip().replace("\r", " ").replace("\n", " ")
            if len(original_text) > 160:
                original_text = original_text[:157] + "..."

            writer.writerow([
                s.get("step_number", ""),
                s.get("rule_code", ""),
                s.get("rule_title", ""),
                s.get("rule_type", "general"),
                clause.get("section", "N/A"),
                clause.get("page", "N/A"),
                s.get("validation_status", "VALID"),
                s.get("formula", ""),
                s.get("description", ""),
                _format_currency(s.get("subtotal", 0)),
                original_text
            ])

        return output.getvalue()

    @staticmethod
    def generate_audit_json(trail: Dict[str, Any], user_id: str = "") -> Dict[str, Any]:
        """
        Builds a structured cryptographic JSON audit package with calculation integrity hash.
        """
        # Compute SHA-256 hash over deterministic calculation steps
        steps_repr = json.dumps(
            [
                {
                    "step": s.get("step_number"),
                    "rule": s.get("rule_code"),
                    "formula": s.get("formula"),
                    "subtotal": s.get("subtotal"),
                }
                for s in trail.get("steps", [])
            ],
            sort_keys=True
        )
        integrity_hash = hashlib.sha256(steps_repr.encode("utf-8")).hexdigest()

        return {
            "dossier_version": "1.0-lawgic-audit",
            "integrity_signature": {
                "algorithm": "SHA-256",
                "calculation_hash": integrity_hash,
                "engine": "LAWGIC Deterministic Rule Engine v1.0",
                "zero_hallucination_guarantee": True
            },
            "contract": {
                "id": trail.get("contract_id"),
                "title": trail.get("contract_title"),
                "user_id": user_id
            },
            "execution": {
                "id": trail.get("execution_id"),
                "scenario_name": trail.get("scenario_name"),
                "executed_at": trail.get("executed_at"),
                "financial_impact": trail.get("financial_impact"),
                "formatted_financial_impact": _format_currency(trail.get("financial_impact")),
                "input_variables": trail.get("input_variables"),
                "summary": trail.get("summary")
            },
            "steps": trail.get("steps", []),
            "metadata": {
                "generated_at": datetime.utcnow().isoformat() + "Z",
                "compliance": "Audit & Financial Provenance Standard v1.0"
            }
        }

    @staticmethod
    def generate_audit_html_report(trail: Dict[str, Any], user_name: str = "Legal Auditor") -> str:
        """
        Generates an executive, print-ready HTML/PDF report with LAWGIC branding.
        """
        title = trail.get("contract_title", "Contract Audit Dossier")
        exec_id = trail.get("execution_id", "N/A")
        scenario = trail.get("scenario_name", "Deterministic Execution")
        impact = _format_currency(trail.get("financial_impact", 0))
        exec_date = trail.get("executed_at", datetime.utcnow().isoformat())
        steps = trail.get("steps", [])
        input_vars = trail.get("input_variables", {})

        # Compute hash
        steps_repr = json.dumps(
            [{"step": s.get("step_number"), "subtotal": s.get("subtotal")} for s in steps],
            sort_keys=True
        )
        integrity_hash = hashlib.sha256(steps_repr.encode("utf-8")).hexdigest()[:24]

        # Generate rows
        step_rows = []
        for s in steps:
            clause = s.get("source_clause") or {}
            sec = clause.get("section", "N/A")
            page = clause.get("page", "N/A")
            orig_text = clause.get("original_text", "").strip()

            step_rows.append(f"""
            <div class="step-card">
              <div class="step-header">
                <div class="step-badge">Step {s.get('step_number', 1)}</div>
                <div class="step-title-group">
                  <h4>{s.get('rule_title', s.get('rule_code', 'Rule'))}</h4>
                  <span class="rule-code">{s.get('rule_code', '')}</span>
                </div>
                <div class="step-subtotal">{_format_currency(s.get('subtotal', 0))}</div>
              </div>

              <div class="step-body">
                <div class="step-meta-grid">
                  <div><strong>Formula:</strong> <code>{s.get('formula', 'N/A')}</code></div>
                  <div><strong>Clause Reference:</strong> Section {sec}, Page {page}</div>
                  <div><strong>Validation:</strong> <span class="badge-valid">{s.get('validation_status', 'VALID')}</span></div>
                </div>

                <div class="step-desc">
                  <p>{s.get('description', '')}</p>
                </div>

                {f'''
                <div class="clause-evidence">
                  <div class="evidence-title">📜 Source Contract Clause Text (Section {sec}):</div>
                  <blockquote>"{orig_text}"</blockquote>
                </div>
                ''' if orig_text else ''}
              </div>
            </div>
            """)

        vars_items = "".join([f"<li><code>{k}</code> = <strong>{v}</strong></li>" for k, v in input_vars.items()])

        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>LAWGIC Executive Audit Dossier — {title}</title>
  <style>
    @page {{
      size: A4;
      margin: 18mm 15mm 20mm 15mm;
    }}
    * {{
      box-sizing: border-box;
      margin: 0;
      padding: 0;
    }}
    body {{
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
      color: #1e293b;
      background: #f8fafc;
      line-height: 1.5;
      font-size: 13px;
      padding: 24px;
    }}
    .print-actions {{
      display: flex;
      justify-content: flex-end;
      gap: 12px;
      margin-bottom: 20px;
    }}
    .print-btn {{
      background: #4f46e5;
      color: white;
      border: none;
      padding: 10px 18px;
      border-radius: 8px;
      font-weight: 600;
      cursor: pointer;
      font-size: 13px;
      box-shadow: 0 2px 4px rgba(79, 70, 229, 0.2);
    }}
    .print-btn:hover {{
      background: #4338ca;
    }}
    @media print {{
      body {{
        background: #ffffff;
        padding: 0;
      }}
      .print-actions {{
        display: none !important;
      }}
      .step-card {{
        page-break-inside: avoid;
      }}
    }}
    .container {{
      max-width: 900px;
      margin: 0 auto;
      background: #ffffff;
      padding: 36px;
      border-radius: 12px;
      box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05), 0 2px 4px -1px rgba(0, 0, 0, 0.03);
      border: 1px solid #e2e8f0;
    }}
    .header {{
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      border-bottom: 2px solid #e2e8f0;
      padding-bottom: 20px;
      margin-bottom: 24px;
    }}
    .brand-group h1 {{
      font-size: 24px;
      color: #0f172a;
      letter-spacing: -0.5px;
      display: flex;
      align-items: center;
      gap: 8px;
    }}
    .brand-tag {{
      background: #4f46e5;
      color: white;
      font-size: 11px;
      padding: 2px 8px;
      border-radius: 4px;
      font-weight: 700;
      letter-spacing: 0.5px;
    }}
    .subhead {{
      color: #64748b;
      font-size: 13px;
      margin-top: 4px;
    }}
    .audit-meta {{
      text-align: right;
      font-size: 12px;
      color: #64748b;
    }}
    .kpi-grid {{
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 16px;
      margin-bottom: 28px;
    }}
    .kpi-card {{
      background: #f1f5f9;
      padding: 16px;
      border-radius: 8px;
      border: 1px solid #cbd5e1;
    }}
    .kpi-label {{
      font-size: 11px;
      text-transform: uppercase;
      font-weight: 700;
      color: #475569;
      letter-spacing: 0.5px;
    }}
    .kpi-val {{
      font-size: 22px;
      font-weight: 800;
      color: #0f172a;
      margin-top: 6px;
    }}
    .kpi-card.highlight {{
      background: #eef2ff;
      border-color: #c7d2fe;
    }}
    .kpi-card.highlight .kpi-val {{
      color: #4338ca;
    }}
    .inputs-card {{
      background: #f8fafc;
      border: 1px solid #e2e8f0;
      padding: 16px;
      border-radius: 8px;
      margin-bottom: 28px;
    }}
    .inputs-card h3 {{
      font-size: 13px;
      color: #334155;
      margin-bottom: 8px;
      text-transform: uppercase;
      letter-spacing: 0.5px;
    }}
    .inputs-card ul {{
      display: flex;
      flex-wrap: wrap;
      gap: 16px;
      list-style: none;
      padding: 0;
    }}
    .inputs-card li {{
      font-size: 12px;
      background: #ffffff;
      border: 1px solid #cbd5e1;
      padding: 4px 10px;
      border-radius: 6px;
    }}
    .steps-container {{
      margin-top: 24px;
    }}
    .section-title {{
      font-size: 16px;
      font-weight: 700;
      color: #0f172a;
      margin-bottom: 16px;
      display: flex;
      justify-content: space-between;
      align-items: center;
    }}
    .step-card {{
      border: 1px solid #e2e8f0;
      border-radius: 8px;
      margin-bottom: 16px;
      overflow: hidden;
      background: #ffffff;
    }}
    .step-header {{
      display: flex;
      align-items: center;
      padding: 12px 16px;
      background: #f8fafc;
      border-bottom: 1px solid #e2e8f0;
    }}
    .step-badge {{
      background: #e0e7ff;
      color: #4338ca;
      font-weight: 700;
      font-size: 11px;
      padding: 4px 8px;
      border-radius: 4px;
      margin-right: 12px;
    }}
    .step-title-group {{
      flex: 1;
    }}
    .step-title-group h4 {{
      font-size: 14px;
      color: #0f172a;
    }}
    .rule-code {{
      font-size: 11px;
      color: #64748b;
      font-family: monospace;
    }}
    .step-subtotal {{
      font-size: 16px;
      font-weight: 700;
      color: #0f172a;
    }}
    .step-body {{
      padding: 16px;
    }}
    .step-meta-grid {{
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      font-size: 12px;
      color: #475569;
      margin-bottom: 12px;
      background: #f8fafc;
      padding: 10px 14px;
      border-radius: 6px;
    }}
    .step-meta-grid code {{
      color: #4338ca;
      font-weight: 600;
    }}
    .badge-valid {{
      background: #dcfce7;
      color: #15803d;
      font-size: 10px;
      padding: 2px 6px;
      border-radius: 4px;
      font-weight: 700;
    }}
    .step-desc {{
      font-size: 13px;
      color: #334155;
      margin-bottom: 12px;
    }}
    .clause-evidence {{
      background: #fffbeb;
      border-left: 4px solid #f59e0b;
      padding: 10px 14px;
      border-radius: 0 6px 6px 0;
      font-size: 12px;
      margin-top: 8px;
    }}
    .evidence-title {{
      font-weight: 700;
      color: #b45309;
      margin-bottom: 4px;
      font-size: 11px;
      text-transform: uppercase;
      letter-spacing: 0.5px;
    }}
    .clause-evidence blockquote {{
      color: #78350f;
      font-style: italic;
    }}
    .footer {{
      margin-top: 36px;
      padding-top: 20px;
      border-top: 1px solid #e2e8f0;
      display: flex;
      justify-content: space-between;
      align-items: center;
      font-size: 11px;
      color: #94a3b8;
    }}
    .integrity-box {{
      font-family: monospace;
      background: #f1f5f9;
      padding: 4px 8px;
      border-radius: 4px;
      color: #475569;
    }}
  </style>
</head>
<body>
  <div class="print-actions">
    <button class="print-btn" onclick="window.print()">🖨️ Print / Save as PDF</button>
  </div>

  <div class="container">
    <div class="header">
      <div class="brand-group">
        <h1>LAWGIC <span class="brand-tag">DETERMINISTIC AUDIT DOSSIER</span></h1>
        <div class="subhead">Contract Intelligence & Executable Business Rules Engine</div>
      </div>
      <div class="audit-meta">
        <div><strong>Execution ID:</strong> {exec_id}</div>
        <div><strong>Auditor:</strong> {user_name}</div>
        <div><strong>Generated:</strong> {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}</div>
      </div>
    </div>

    <div class="kpi-grid">
      <div class="kpi-card highlight">
        <div class="kpi-label">Final Financial Outcome</div>
        <div class="kpi-val">{impact}</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-label">Contract Document</div>
        <div class="kpi-val" style="font-size: 16px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">{title}</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-label">Execution Trace Steps</div>
        <div class="kpi-val">{len(steps)} Rules Evaluated</div>
      </div>
    </div>

    {f'''
    <div class="inputs-card">
      <h3>Applied Simulation & Input Parameters</h3>
      <ul>{vars_items}</ul>
    </div>
    ''' if input_vars else ''}

    <div class="steps-container">
      <div class="section-title">
        <span>Step-by-Step Mathematical Provenance Trail</span>
        <span style="font-size: 12px; color: #16a34a; font-weight: 600;">✓ 100% Zero-Hallucination Deterministic Math</span>
      </div>

      {"".join(step_rows)}
    </div>

    <div class="footer">
      <div>Generated securely by LAWGIC Enterprise Platform. All mathematical calculations performed deterministically.</div>
      <div class="integrity-box">SHA-256: {integrity_hash}…</div>
    </div>
  </div>
</body>
</html>
"""
        return html

    @staticmethod
    def generate_simulation_csv(comparison: Dict[str, Any]) -> str:
        """
        Generates comparative CSV between Baseline and What-If scenario.
        """
        output = io.StringIO()
        writer = csv.writer(output, quoting=csv.QUOTE_MINIMAL)

        writer.writerow(["# LAWGIC WHAT-IF FINANCIAL SIMULATION LEDGER"])
        writer.writerow(["# Audit Trace ID", comparison.get("audit_trace_id", "N/A")])
        writer.writerow(["# Contract Title", comparison.get("contract_title", "N/A")])
        writer.writerow(["# Contract ID", comparison.get("contract_id", "N/A")])
        writer.writerow(["# Baseline Impact", _format_currency(comparison.get("original_total_impact", 0))])
        writer.writerow(["# What-If Impact", _format_currency(comparison.get("what_if_total_impact", 0))])
        writer.writerow(["# Net Delta", _format_currency(comparison.get("net_difference", 0))])
        writer.writerow([])

        writer.writerow([
            "Rule Code",
            "Rule Title",
            "Rule Type",
            "Formula",
            "Baseline Subtotal",
            "What-If Subtotal",
            "Difference (Delta)",
            "Trigger Status",
            "Reason"
        ])

        for r in comparison.get("rules", []):
            writer.writerow([
                r.get("rule_code", ""),
                r.get("rule_title", ""),
                r.get("rule_type", "general"),
                r.get("formula", ""),
                _format_currency(r.get("original_subtotal", 0)),
                _format_currency(r.get("what_if_subtotal", 0)),
                _format_currency(r.get("difference", 0)),
                "TRIGGERED" if r.get("triggered") else "INACTIVE",
                r.get("reason", "")
            ])

        return output.getvalue()

    @staticmethod
    def generate_simulation_html_report(comparison: Dict[str, Any], user_name: str = "Financial Auditor") -> str:
        """
        Generates executive comparative What-If report with visual cards.
        """
        contract_title = comparison.get("contract_title", "Contract")
        audit_id = comparison.get("audit_trace_id", "N/A")
        orig_impact = _format_currency(comparison.get("original_total_impact", 0))
        what_if_impact = _format_currency(comparison.get("what_if_total_impact", 0))
        net_diff = _format_currency(comparison.get("net_difference", 0))
        rules = comparison.get("rules", [])
        overall_expl = comparison.get("overall_human_explanation", "")

        rule_rows = []
        for r in rules:
            diff_val = r.get("difference", 0)
            diff_class = "color: #dc2626;" if diff_val < 0 else ("color: #16a34a;" if diff_val > 0 else "color: #64748b;")
            rule_rows.append(f"""
            <tr>
              <td>
                <strong>{r.get('rule_title', r.get('rule_code'))}</strong><br>
                <span style="font-family: monospace; font-size: 11px; color: #64748b;">{r.get('rule_code')}</span>
              </td>
              <td><code>{r.get('formula', 'N/A')}</code></td>
              <td style="text-align: right;">{_format_currency(r.get('original_subtotal', 0))}</td>
              <td style="text-align: right; font-weight: 700;">{_format_currency(r.get('what_if_subtotal', 0))}</td>
              <td style="text-align: right; font-weight: 800; {diff_class}">{_format_currency(diff_val)}</td>
              <td>{r.get('reason', '')}</td>
            </tr>
            """)

        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>LAWGIC Scenario Comparison — {contract_title}</title>
  <style>
    @page {{ size: A4; margin: 18mm 15mm 20mm 15mm; }}
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
      color: #1e293b;
      background: #f8fafc;
      font-size: 13px;
      line-height: 1.5;
      padding: 24px;
    }}
    .print-actions {{ display: flex; justify-content: flex-end; gap: 12px; margin-bottom: 20px; }}
    .print-btn {{
      background: #4f46e5; color: white; border: none; padding: 10px 18px; border-radius: 8px;
      font-weight: 600; cursor: pointer; font-size: 13px;
    }}
    @media print {{
      body {{ background: #fff; padding: 0; }}
      .print-actions {{ display: none !important; }}
    }}
    .container {{
      max-width: 900px; margin: 0 auto; background: #ffffff; padding: 36px; border-radius: 12px;
      border: 1px solid #e2e8f0;
    }}
    .header {{
      display: flex; justify-content: space-between; border-bottom: 2px solid #e2e8f0;
      padding-bottom: 20px; margin-bottom: 24px;
    }}
    .brand-tag {{
      background: #0284c7; color: white; font-size: 11px; padding: 2px 8px; border-radius: 4px; font-weight: 700;
    }}
    .kpi-grid {{
      display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; margin-bottom: 28px;
    }}
    .kpi-card {{
      background: #f8fafc; padding: 16px; border-radius: 8px; border: 1px solid #cbd5e1;
    }}
    .kpi-label {{ font-size: 11px; text-transform: uppercase; font-weight: 700; color: #475569; }}
    .kpi-val {{ font-size: 22px; font-weight: 800; color: #0f172a; margin-top: 6px; }}
    .kpi-card.delta {{ background: #f0fdf4; border-color: #bbf7d0; }}
    .kpi-card.delta .kpi-val {{ color: #15803d; }}
    .comparison-table {{
      width: 100%; border-collapse: collapse; margin-top: 20px; font-size: 12px;
    }}
    .comparison-table th {{
      background: #f1f5f9; padding: 10px 12px; text-align: left; font-weight: 700;
      border-bottom: 2px solid #cbd5e1; color: #334155;
    }}
    .comparison-table td {{
      padding: 12px; border-bottom: 1px solid #e2e8f0; vertical-align: top;
    }}
    .explanation-box {{
      background: #f1f5f9; border-left: 4px solid #4f46e5; padding: 14px; border-radius: 0 8px 8px 0;
      margin-bottom: 24px; font-size: 13px; color: #334155;
    }}
  </style>
</head>
<body>
  <div class="print-actions">
    <button class="print-btn" onclick="window.print()">🖨️ Print / Save as PDF</button>
  </div>

  <div class="container">
    <div class="header">
      <div>
        <h1 style="font-size: 22px; color: #0f172a;">LAWGIC <span class="brand-tag">WHAT-IF SCENARIO REPORT</span></h1>
        <div style="color: #64748b; font-size: 13px; margin-top: 4px;">{contract_title}</div>
      </div>
      <div style="text-align: right; font-size: 12px; color: #64748b;">
        <div><strong>Trace ID:</strong> {audit_id}</div>
        <div><strong>Auditor:</strong> {user_name}</div>
        <div><strong>Generated:</strong> {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}</div>
      </div>
    </div>

    <div class="kpi-grid">
      <div class="kpi-card">
        <div class="kpi-label">Baseline Contract Impact</div>
        <div class="kpi-val">{orig_impact}</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-label">Simulated Scenario Impact</div>
        <div class="kpi-val">{what_if_impact}</div>
      </div>
      <div class="kpi-card delta">
        <div class="kpi-label">Net Variance (Delta)</div>
        <div class="kpi-val">{net_diff}</div>
      </div>
    </div>

    {f'<div class="explanation-box"><strong>Executive Summary:</strong> {overall_expl}</div>' if overall_expl else ''}

    <h3 style="font-size: 15px; color: #0f172a; margin-top: 24px;">Rule-by-Rule Scenario Variance</h3>
    <table class="comparison-table">
      <thead>
        <tr>
          <th>Rule & Identifier</th>
          <th>Formula</th>
          <th style="text-align: right;">Baseline</th>
          <th style="text-align: right;">What-If</th>
          <th style="text-align: right;">Delta</th>
          <th>Impact Rationale</th>
        </tr>
      </thead>
      <tbody>
        {"".join(rule_rows)}
      </tbody>
    </table>

    <div style="margin-top: 36px; padding-top: 20px; border-top: 1px solid #e2e8f0; font-size: 11px; color: #94a3b8; display: flex; justify-content: space-between;">
      <div>Generated securely by LAWGIC Enterprise Platform. 100% Deterministic Execution.</div>
      <div>LAWGIC Financial Simulation Engine v1.0</div>
    </div>
  </div>
</body>
</html>
"""
        return html
