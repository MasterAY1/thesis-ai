"""
PDF Report Generator
Produces a downloadable evaluation report using reportlab.

Generates:
- Cover page with score and document type
- Section-by-section score breakdown with progress bars
- Deductions table with evidence and fix recommendations
- Cross-validation results
- AI confidence summary
"""
import io
import logging
from typing import Dict, Any, List

logger = logging.getLogger("thesis_ai.report")


def _try_import_reportlab():
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import cm
        from reportlab.lib import colors
        from reportlab.platypus import (
            SimpleDocTemplate, Paragraph, Spacer, Table,
            TableStyle, HRFlowable, KeepTogether
        )
        from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
        return True
    except ImportError:
        return False


def generate_pdf_report(evaluation_data: Dict[str, Any], filename: str = "thesis") -> bytes:
    """
    Generates a complete PDF evaluation report.

    Args:
        evaluation_data: The full evaluation result from evaluate_thesis()
        filename: Original thesis filename (for the report title)

    Returns:
        PDF as raw bytes ready for HTTP streaming.
    """
    if not _try_import_reportlab():
        raise ImportError(
            "reportlab is not installed. Add 'reportlab' to requirements.txt and redeploy."
        )

    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.lib import colors
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table,
        TableStyle, HRFlowable, KeepTogether
    )
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT

    # ── Colour palette ─────────────────────────────────────────────────────────
    NAVY      = colors.HexColor("#1E3A5F")
    BLUE      = colors.HexColor("#2563EB")
    LIGHT_BG  = colors.HexColor("#F1F5F9")
    GREEN     = colors.HexColor("#16A34A")
    AMBER     = colors.HexColor("#D97706")
    RED       = colors.HexColor("#DC2626")
    PURPLE    = colors.HexColor("#7C3AED")
    WHITE     = colors.white
    LIGHT_GREY = colors.HexColor("#E2E8F0")

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=2 * cm,
        leftMargin=2 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
        title=f"ThesisAI Evaluation Report — {filename}",
    )

    styles = getSampleStyleSheet()
    story = []

    # ── Custom styles ──────────────────────────────────────────────────────────
    title_style = ParagraphStyle(
        "Title", parent=styles["Normal"],
        fontSize=26, textColor=NAVY, spaceAfter=6,
        fontName="Helvetica-Bold", alignment=TA_CENTER,
    )
    subtitle_style = ParagraphStyle(
        "Subtitle", parent=styles["Normal"],
        fontSize=12, textColor=colors.grey, spaceAfter=4,
        fontName="Helvetica", alignment=TA_CENTER,
    )
    h2_style = ParagraphStyle(
        "H2", parent=styles["Normal"],
        fontSize=14, textColor=NAVY, spaceBefore=16, spaceAfter=8,
        fontName="Helvetica-Bold",
    )
    body_style = ParagraphStyle(
        "Body", parent=styles["Normal"],
        fontSize=10, textColor=colors.HexColor("#374151"),
        spaceAfter=4, leading=14,
    )
    small_style = ParagraphStyle(
        "Small", parent=styles["Normal"],
        fontSize=8, textColor=colors.grey,
        spaceAfter=2,
    )
    italic_style = ParagraphStyle(
        "Italic", parent=styles["Normal"],
        fontSize=9, textColor=colors.HexColor("#4B5563"),
        spaceAfter=4, fontName="Helvetica-Oblique",
    )

    # ── Helper: score colour ───────────────────────────────────────────────────
    def score_color(score, max_score):
        pct = score / max_score if max_score else 0
        if pct >= 0.70:
            return GREEN
        elif pct >= 0.50:
            return AMBER
        return RED

    # ── Helper: confidence badge ───────────────────────────────────────────────
    def confidence_label(c):
        if c is None:
            return "N/A"
        if c >= 0.75:
            return f"High ({int(c*100)}%)"
        elif c >= 0.55:
            return f"Medium ({int(c*100)}%)"
        return f"Low ({int(c*100)}%)"

    def confidence_color(c):
        if c is None:
            return colors.grey
        if c >= 0.75:
            return GREEN
        elif c >= 0.55:
            return AMBER
        return RED

    # ========== COVER PAGE ==========

    story.append(Spacer(1, 1.5 * cm))
    story.append(Paragraph("ThesisAI", title_style))
    story.append(Paragraph("AI-Powered Academic Evaluation Report", subtitle_style))
    story.append(Spacer(1, 0.3 * cm))

    # Coloured score circle via table
    overall   = evaluation_data.get("overall_score", 0)
    total_max = evaluation_data.get("total_marks", 100)
    doc_type  = evaluation_data.get("document_type", {}).get("document_type", "thesis").title()
    institution = evaluation_data.get("institution", "nmcn").upper()

    score_color_val = score_color(overall, total_max)
    score_table = Table(
        [[Paragraph(f"{overall}/{total_max}", ParagraphStyle(
            "ScoreNum", fontSize=36, fontName="Helvetica-Bold",
            textColor=score_color_val, alignment=TA_CENTER,
        ))]],
        colWidths=[8 * cm],
    )
    score_table.setStyle(TableStyle([
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ROUNDEDCORNERS", [12]),
        ("BOX", (0, 0), (-1, -1), 2, score_color_val),
        ("BACKGROUND", (0, 0), (-1, -1), LIGHT_BG),
        ("TOPPADDING", (0, 0), (-1, -1), 12),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
    ]))

    story.append(Table([[score_table]], colWidths=[doc.width]))
    story.append(Spacer(1, 0.4 * cm))

    # Meta row
    meta_data = [
        ["Document", filename],
        ["Type Detected", doc_type],
        ["Institution", institution],
        ["Total Deductions", f"-{total_max - overall} marks"],
    ]
    meta_table = Table(meta_data, colWidths=[4 * cm, doc.width - 4 * cm])
    meta_table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("TEXTCOLOR", (0, 0), (0, -1), NAVY),
        ("TEXTCOLOR", (1, 0), (1, -1), colors.HexColor("#374151")),
        ("ROWBACKGROUNDS", (0, 0), (-1, -1), [WHITE, LIGHT_BG]),
        ("GRID", (0, 0), (-1, -1), 0.25, LIGHT_GREY),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
    ]))
    story.append(meta_table)
    story.append(HRFlowable(width="100%", thickness=1, color=LIGHT_GREY, spaceAfter=10))

    # Document type notice for proposals
    if doc_type.lower() == "proposal":
        notice = evaluation_data.get("document_type", {}).get("reason", "")
        if notice:
            notice_table = Table(
                [[Paragraph(f"ℹ️  <b>Proposal Mode Active:</b> {notice}", body_style)]],
                colWidths=[doc.width],
            )
            notice_table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#EFF6FF")),
                ("BOX", (0, 0), (-1, -1), 1, BLUE),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("ROUNDEDCORNERS", [6]),
            ]))
            story.append(notice_table)
            story.append(Spacer(1, 0.3 * cm))

    # ========== SCORE BREAKDOWN ==========
    story.append(Paragraph("Section Score Breakdown", h2_style))

    breakdown = evaluation_data.get("breakdown", {})
    if breakdown:
        breakdown_rows = [
            [
                Paragraph("<b>Section</b>", small_style),
                Paragraph("<b>Score</b>", small_style),
                Paragraph("<b>Max</b>", small_style),
                Paragraph("<b>%</b>", small_style),
            ]
        ]
        for section, data in breakdown.items():
            s = data.get("score", 0)
            m = data.get("max", 0)
            pct = f"{int((s/m)*100)}%" if m else "N/A"
            breakdown_rows.append([
                Paragraph(section, body_style),
                Paragraph(str(s), ParagraphStyle("S", fontSize=10, textColor=score_color(s, m), fontName="Helvetica-Bold")),
                Paragraph(str(m), body_style),
                Paragraph(pct, body_style),
            ])

        bt = Table(breakdown_rows, colWidths=[9 * cm, 2 * cm, 2 * cm, 2.5 * cm])
        bt.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), NAVY),
            ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, LIGHT_BG]),
            ("GRID", (0, 0), (-1, -1), 0.25, LIGHT_GREY),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ]))
        story.append(bt)

    story.append(Spacer(1, 0.4 * cm))

    # ========== DEDUCTIONS ==========
    story.append(Paragraph("Deductions & Evidence", h2_style))

    deductions: List[Dict] = evaluation_data.get("deductions", [])
    if not deductions:
        story.append(Paragraph("No major deductions identified. Excellent work!", body_style))
    else:
        for i, d in enumerate(deductions, 1):
            sev = d.get("severity", "medium")
            sev_color = RED if sev == "high" else AMBER if sev == "medium" else BLUE
            conf = d.get("confidence")

            header = [
                Paragraph(
                    f"<b>{i}. {d.get('issue_title', 'Issue')}</b>",
                    ParagraphStyle("IH", fontSize=10, fontName="Helvetica-Bold", textColor=NAVY),
                ),
                Paragraph(
                    f"<b>-{d.get('deduction', 0)} mark(s)</b>",
                    ParagraphStyle("IScore", fontSize=10, textColor=RED, fontName="Helvetica-Bold", alignment=TA_RIGHT),
                ),
            ]
            header_table = Table([header], colWidths=[doc.width - 3 * cm, 3 * cm])
            header_table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), LIGHT_BG),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("BOX", (0, 0), (-1, -1), 0.5, LIGHT_GREY),
            ]))

            items = [header_table]

            # Rubric ref
            rubric = d.get("rubric", {})
            if rubric.get("expected_requirement"):
                items.append(Paragraph(
                    f"📋 <b>Rubric ({rubric.get('section', '')} — {rubric.get('max_marks', 0)} marks):</b> {rubric['expected_requirement']}",
                    ParagraphStyle("Rubric", fontSize=9, textColor=PURPLE, spaceAfter=3, leading=13),
                ))

            # Reasoning
            if d.get("deduction_reasoning"):
                items.append(Paragraph(f"❓ {d['deduction_reasoning']}", italic_style))

            # Supervisor note
            if d.get("supervisor_note"):
                items.append(Paragraph(f"🎓 <b>Supervisor:</b> {d['supervisor_note']}", body_style))

            # Evidence
            evidence = d.get("evidence", {})
            if evidence.get("quote"):
                items.append(Paragraph(f'📌 <i>"{evidence["quote"]}"</i>', italic_style))

            # Suggested fix
            if d.get("suggested_fix"):
                fix_t = Table(
                    [[Paragraph(f"💡 <b>Fix:</b> {d['suggested_fix']}", ParagraphStyle("Fix", fontSize=9, textColor=GREEN, leading=13))]],
                    colWidths=[doc.width],
                )
                fix_t.setStyle(TableStyle([
                    ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F0FDF4")),
                    ("TOPPADDING", (0, 0), (-1, -1), 5),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                    ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ]))
                items.append(fix_t)

            # Confidence badge
            if conf is not None:
                items.append(Paragraph(
                    f"🧠 AI Confidence: {confidence_label(conf)}",
                    ParagraphStyle("Conf", fontSize=8, textColor=confidence_color(conf), spaceAfter=2),
                ))

            items.append(Spacer(1, 0.25 * cm))
            story.append(KeepTogether(items))

    # ========== CROSS-VALIDATION ==========
    cv = evaluation_data.get("cross_validation", {})
    cv_validations = cv.get("validations", [])
    if cv_validations:
        story.append(Paragraph("Cross-Section Consistency", h2_style))
        story.append(Paragraph(cv.get("summary", ""), body_style))
        story.append(Spacer(1, 0.2 * cm))

        for v in cv_validations:
            status = v.get("status", "unknown")
            icon   = "✅" if status == "pass" else "❌" if status == "fail" else "⚠️"
            clr    = GREEN if status == "pass" else RED if status == "fail" else AMBER
            story.append(Paragraph(
                f"{icon} <b>{v.get('rule', '')}</b> — {status.upper()}" +
                (f" (-{v['deduction']} marks)" if v.get("deduction", 0) > 0 else ""),
                ParagraphStyle("CV", fontSize=10, textColor=clr, spaceAfter=4, fontName="Helvetica-Bold"),
            ))
            if v.get("explanation"):
                story.append(Paragraph(v["explanation"], body_style))
            if v.get("suggested_fix"):
                story.append(Paragraph(f"💡 {v['suggested_fix']}", italic_style))
            story.append(Spacer(1, 0.15 * cm))

    # ========== FOOTER ==========
    story.append(Spacer(1, 1 * cm))
    story.append(HRFlowable(width="100%", thickness=0.5, color=LIGHT_GREY))
    story.append(Spacer(1, 0.2 * cm))
    story.append(Paragraph(
        "Generated by ThesisAI · AI-Powered Academic Evaluation · thesis-ai-delta.vercel.app",
        ParagraphStyle("Footer", fontSize=7, textColor=colors.grey, alignment=TA_CENTER),
    ))

    doc.build(story)
    buffer.seek(0)
    return buffer.read()
