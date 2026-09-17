from __future__ import annotations
import io
from datetime import datetime
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable

def generate_adverse_action_pdf(application, reasons: list[dict], applicant_name: str) -> io.BytesIO:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=40, leftMargin=40, topMargin=40, bottomMargin=40)
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        "DocTitle",
        parent=styles["Heading1"],
        fontSize=18,
        leading=22,
        textColor=colors.HexColor("#0f172a"),
        spaceAfter=6
    )
    subtitle_style = ParagraphStyle(
        "DocSubtitle",
        parent=styles["Normal"],
        fontSize=10,
        leading=14,
        textColor=colors.HexColor("#64748b"),
        spaceAfter=12
    )
    heading_style = ParagraphStyle(
        "SectionHeading",
        parent=styles["Heading2"],
        fontSize=12,
        leading=16,
        textColor=colors.HexColor("#1e293b"),
        spaceBefore=10,
        spaceAfter=6
    )
    body_style = ParagraphStyle(
        "Body",
        parent=styles["Normal"],
        fontSize=9,
        leading=13,
        textColor=colors.HexColor("#334155")
    )
    disclaimer_style = ParagraphStyle(
        "Disclaimer",
        parent=styles["Normal"],
        fontSize=8,
        leading=11,
        textColor=colors.HexColor("#94a3b8")
    )

    story = []

    # Institution header
    story.append(Paragraph("<b>BANK LOAN & CREDIT RISK UNDERWRITING SYSTEM</b>", title_style))
    story.append(Paragraph("Statement of Adverse Action & Credit Decision Notification", subtitle_style))
    story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#e2e8f0"), spaceAfter=14))

    # Demo Notice
    demo_box = [[Paragraph("<b>DEMO & AUDIT NOTICE:</b> This document was generated for demonstration, compliance simulation, and audit verification purposes only.", disclaimer_style)]]
    t_box = Table(demo_box, colWidths=[530])
    t_box.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#f8fafc")),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor("#cbd5e1")),
        ('PADDING', (0,0), (-1,-1), 8),
    ]))
    story.append(t_box)
    story.append(Spacer(1, 14))

    # Reference Details Table
    now_str = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    info_data = [
        [Paragraph("<b>Applicant Name:</b>", body_style), Paragraph(str(applicant_name), body_style),
         Paragraph("<b>Date of Notice:</b>", body_style), Paragraph(now_str, body_style)],
        [Paragraph("<b>Application ID:</b>", body_style), Paragraph(f"APP-{application.id:06d}", body_style),
         Paragraph("<b>Credit Decision:</b>", body_style), Paragraph("<font color='#dc2626'><b>REJECTED / DECLINED</b></font>", body_style)],
        [Paragraph("<b>Requested Amount:</b>", body_style), Paragraph(f"INR {application.loan_amount:,.2f}", body_style),
         Paragraph("<b>Stated Loan Term:</b>", body_style), Paragraph(f"{application.loan_term_months} Months", body_style)],
    ]
    t_info = Table(info_data, colWidths=[120, 145, 120, 145])
    t_info.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#ffffff")),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#e2e8f0")),
        ('PADDING', (0,0), (-1,-1), 6),
    ]))
    story.append(t_info)
    story.append(Spacer(1, 14))

    # Principal Adverse Action Reasons
    story.append(Paragraph("<b>Principal Adverse Action Reasons</b>", heading_style))
    story.append(Paragraph("In accordance with credit underwriting standards and localized TreeSHAP factor attribution, the primary factors contributing negatively to this decision are listed below:", body_style))
    story.append(Spacer(1, 8))

    reasons_table_data = [
        [Paragraph("<b>#</b>", body_style), Paragraph("<b>Contributing Feature</b>", body_style), Paragraph("<b>Detailed Explanation / Consideration</b>", body_style)]
    ]
    if reasons:
        for idx, r in enumerate(reasons[:4], start=1):
            feat = r.get("feature", "N/A").replace("_", " ").title()
            desc = r.get("description", "Evaluation metric did not satisfy minimum credit parameters.")
            reasons_table_data.append([
                Paragraph(str(idx), body_style),
                Paragraph(feat, body_style),
                Paragraph(desc, body_style)
            ])
    else:
        reasons_table_data.append([
            Paragraph("1", body_style),
            Paragraph("Overall Debt Service", body_style),
            Paragraph("Combined leverage and risk profile did not meet credit threshold criteria.", body_style)
        ])

    t_reasons = Table(reasons_table_data, colWidths=[25, 140, 365])
    t_reasons.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#f1f5f9")),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#cbd5e1")),
        ('PADDING', (0,0), (-1,-1), 6),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
    ]))
    story.append(t_reasons)
    story.append(Spacer(1, 16))

    # Consumer Credit Disclosures
    story.append(Paragraph("<b>Credit Score & Scoring Information</b>", heading_style))
    score_val = application.predicted_credit_score if application.predicted_credit_score else application.credit_score
    story.append(Paragraph(f"External Consumer Credit Bureau Score Evaluated: <b>{score_val:.0f}</b> (Score Range: 300 - 850).", body_style))
    story.append(Spacer(1, 6))
    story.append(Paragraph("Under federal/state consumer credit protection principles, you have the right to request a free copy of your credit report from the reporting agencies within 60 days of receiving this notice.", body_style))
    story.append(Spacer(1, 20))

    # Footer
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#cbd5e1"), spaceAfter=8))
    story.append(Paragraph(f"Document Reference: ADVERSE-NOTICE-{application.id:06d} | Generated: {now_str} | Regulated Model Version: v2.0-enterprise", disclaimer_style))

    doc.build(story)
    buffer.seek(0)
    return buffer


def generate_approval_letter_pdf(application, terms: dict, applicant_name: str) -> io.BytesIO:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=40, leftMargin=40, topMargin=40, bottomMargin=40)
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        "DocTitle",
        parent=styles["Heading1"],
        fontSize=18,
        leading=22,
        textColor=colors.HexColor("#065f46"),
        spaceAfter=6
    )
    subtitle_style = ParagraphStyle(
        "DocSubtitle",
        parent=styles["Normal"],
        fontSize=10,
        leading=14,
        textColor=colors.HexColor("#047857"),
        spaceAfter=12
    )
    heading_style = ParagraphStyle(
        "SectionHeading",
        parent=styles["Heading2"],
        fontSize=12,
        leading=16,
        textColor=colors.HexColor("#1e293b"),
        spaceBefore=10,
        spaceAfter=6
    )
    body_style = ParagraphStyle(
        "Body",
        parent=styles["Normal"],
        fontSize=9,
        leading=13,
        textColor=colors.HexColor("#334155")
    )
    disclaimer_style = ParagraphStyle(
        "Disclaimer",
        parent=styles["Normal"],
        fontSize=8,
        leading=11,
        textColor=colors.HexColor("#94a3b8")
    )

    story = []

    # Institution header
    story.append(Paragraph("<b>BANK LOAN & CREDIT RISK UNDERWRITING SYSTEM</b>", title_style))
    story.append(Paragraph("Official Loan Approval & Commitment Letter", subtitle_style))
    story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#059669"), spaceAfter=14))

    # Reference Details Table
    now_str = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    approved_amt = application.predicted_loan_amount or application.loan_amount
    interest_rate = application.interest_rate or 10.0
    term_months = application.loan_term_months or 36

    # Calculate approximate monthly payment
    r = (interest_rate / 100.0) / 12.0
    if r > 0 and term_months > 0:
        monthly_pmt = approved_amt * (r * ((1 + r) ** term_months)) / (((1 + r) ** term_months) - 1)
    else:
        monthly_pmt = approved_amt / max(term_months, 1)

    info_data = [
        [Paragraph("<b>Applicant Name:</b>", body_style), Paragraph(str(applicant_name), body_style),
         Paragraph("<b>Date of Issuance:</b>", body_style), Paragraph(now_str, body_style)],
        [Paragraph("<b>Application ID:</b>", body_style), Paragraph(f"APP-{application.id:06d}", body_style),
         Paragraph("<b>Approval Status:</b>", body_style), Paragraph("<font color='#059669'><b>CONDITIONALLY APPROVED</b></font>", body_style)],
        [Paragraph("<b>Approved Amount:</b>", body_style), Paragraph(f"INR {approved_amt:,.2f}", body_style),
         Paragraph("<b>Loan Term:</b>", body_style), Paragraph(f"{term_months} Months", body_style)],
        [Paragraph("<b>Interest Rate (APR):</b>", body_style), Paragraph(f"{interest_rate:.2f}%", body_style),
         Paragraph("<b>Est. Monthly Payment:</b>", body_style), Paragraph(f"INR {monthly_pmt:,.2f}", body_style)],
    ]
    t_info = Table(info_data, colWidths=[130, 135, 130, 135])
    t_info.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#ecfdf5")),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#a7f3d0")),
        ('PADDING', (0,0), (-1,-1), 6),
    ]))
    story.append(t_info)
    story.append(Spacer(1, 14))

    # Terms & Conditions
    story.append(Paragraph("<b>Underwriting Terms & Conditions of Approval</b>", heading_style))
    story.append(Paragraph("This conditional approval is based on the credit profile and representations submitted in your application, subject to fulfillment of the following verification requirements prior to disbursement:", body_style))
    story.append(Spacer(1, 6))

    conditions = [
        "1. Satisfactory verification of reported annual income and current employment tenure.",
        "2. Verification of available liquid bank balances and pledged collateral documentation where required.",
        "3. Absence of material adverse changes in credit bureau score or additional debt obligations prior to closing.",
        "4. Execution of the definitive promissory note and loan agreement documents."
    ]
    for cond in conditions:
        story.append(Paragraph(cond, body_style))
        story.append(Spacer(1, 3))

    story.append(Spacer(1, 14))

    # Disclaimer
    story.append(Paragraph("<b>Commitment Expiration & Project Notice</b>", heading_style))
    story.append(Paragraph("This commitment is valid for 30 calendar days from the date of issuance. This document is part of a verified FinTech credit underwriting project demonstration.", body_style))
    story.append(Spacer(1, 20))

    # Footer
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#cbd5e1"), spaceAfter=8))
    story.append(Paragraph(f"Document Reference: APPROVAL-COMMITMENT-{application.id:06d} | Issued: {now_str} | Underwriting Model: v2.0-enterprise", disclaimer_style))

    doc.build(story)
    buffer.seek(0)
    return buffer


def generate_kfs_pdf(application, applicant_name: str, kfs_data: dict, schedule: list[dict] = None) -> io.BytesIO:
    """
    Generates an Academic/Demo Key Fact Statement (KFS) PDF document.
    Includes mandatory academic simulation disclaimer, core loan terms,
    and first-year amortization breakdown.
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36
    )
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        "KfsTitle",
        parent=styles["Heading1"],
        fontSize=16,
        leading=20,
        textColor=colors.HexColor("#0f172a"),
        spaceAfter=4
    )
    subtitle_style = ParagraphStyle(
        "KfsSubtitle",
        parent=styles["Normal"],
        fontSize=10,
        leading=14,
        textColor=colors.HexColor("#475569"),
        spaceAfter=8
    )
    disclaimer_title_style = ParagraphStyle(
        "KfsDisclaimerTitle",
        parent=styles["Normal"],
        fontSize=9,
        leading=12,
        textColor=colors.HexColor("#991b1b"),
        fontName="Helvetica-Bold",
        spaceAfter=2
    )
    disclaimer_body_style = ParagraphStyle(
        "KfsDisclaimerBody",
        parent=styles["Normal"],
        fontSize=8,
        leading=11,
        textColor=colors.HexColor("#7f1d1d")
    )
    heading_style = ParagraphStyle(
        "KfsHeading",
        parent=styles["Heading2"],
        fontSize=11,
        leading=15,
        textColor=colors.HexColor("#1e293b"),
        spaceBefore=8,
        spaceAfter=4
    )
    body_style = ParagraphStyle(
        "KfsBody",
        parent=styles["Normal"],
        fontSize=8.5,
        leading=12,
        textColor=colors.HexColor("#334155")
    )
    table_header_style = ParagraphStyle(
        "KfsTableHeader",
        parent=styles["Normal"],
        fontSize=8,
        leading=11,
        textColor=colors.HexColor("#0f172a"),
        fontName="Helvetica-Bold",
        alignment=1  # Centered
    )
    table_cell_style = ParagraphStyle(
        "KfsTableCell",
        parent=styles["Normal"],
        fontSize=8,
        leading=11,
        textColor=colors.HexColor("#334155"),
        alignment=1
    )
    footer_style = ParagraphStyle(
        "KfsFooter",
        parent=styles["Normal"],
        fontSize=7.5,
        leading=10,
        textColor=colors.HexColor("#94a3b8")
    )

    story = []

    # Institution header
    story.append(Paragraph("<b>BANK LOAN & CREDIT RISK UNDERWRITING SYSTEM</b>", title_style))
    story.append(Paragraph("Key Fact Statement (KFS) — Academic & Simulation Loan Summary", subtitle_style))
    story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#2563eb"), spaceAfter=10))

    # Mandatory Academic / Demo Disclaimer Box
    disclaimer_box = [
        [Paragraph(f"<b>{kfs_data.get('disclaimer_header', 'ACADEMIC/DEMO — NOT A LEGAL OR REGULATORY DOCUMENT')}</b>", disclaimer_title_style)],
        [Paragraph(kfs_data.get("disclaimer_text", (
            "This document is generated strictly for academic coursework demonstration and fintech simulation. "
            "It does NOT constitute an official loan agreement, legally binding credit contract, or regulatory disclosure "
            "under RBI or any banking authority."
        )), disclaimer_body_style)]
    ]
    t_disclaimer = Table(disclaimer_box, colWidths=[540])
    t_disclaimer.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#fef2f2")),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor("#f87171")),
        ('PADDING', (0,0), (-1,-1), 6),
    ]))
    story.append(t_disclaimer)
    story.append(Spacer(1, 10))

    # Reference Identification Table
    now_str = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    ref_data = [
        [Paragraph("<b>Applicant Name:</b>", body_style), Paragraph(str(applicant_name), body_style),
         Paragraph("<b>Date Generated:</b>", body_style), Paragraph(now_str, body_style)],
        [Paragraph("<b>Application ID:</b>", body_style), Paragraph(f"APP-{application.id:06d}", body_style),
         Paragraph("<b>Document Reference:</b>", body_style), Paragraph(kfs_data.get("reference_number", f"KFS-APP-{application.id:06d}"), body_style)],
        [Paragraph("<b>Loan Type:</b>", body_style), Paragraph(str(kfs_data.get("loan_type", getattr(application, "loan_type", "Standard"))), body_style),
         Paragraph("<b>Workflow Status:</b>", body_style), Paragraph(f"<font color='#047857'><b>{kfs_data.get('loan_status', application.status or 'APPROVED')}</b></font>", body_style)],
    ]
    t_ref = Table(ref_data, colWidths=[130, 140, 130, 140])
    t_ref.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#f8fafc")),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#e2e8f0")),
        ('PADDING', (0,0), (-1,-1), 5),
    ]))
    story.append(t_ref)
    story.append(Spacer(1, 10))

    # Core Financial Terms Table
    story.append(Paragraph("<b>Core Sanctioned Financial Terms</b>", heading_style))
    terms_data = [
        [Paragraph("<b>Approved Principal:</b>", body_style), Paragraph(f"INR {kfs_data.get('loan_amount', 0):,.2f}", body_style),
         Paragraph("<b>Interest Rate (p.a.):</b>", body_style), Paragraph(f"{kfs_data.get('interest_rate', 0):.2f}% (Reducing)", body_style)],
        [Paragraph("<b>Loan Tenure:</b>", body_style), Paragraph(f"{kfs_data.get('loan_term_months', 0)} Months", body_style),
         Paragraph("<b>Repayment Frequency:</b>", body_style), Paragraph("Monthly", body_style)],
        [Paragraph("<b>Monthly EMI:</b>", body_style), Paragraph(f"<b>INR {kfs_data.get('emi', 0):,.2f}</b>", body_style),
         Paragraph("<b>Total Interest Payable:</b>", body_style), Paragraph(f"INR {kfs_data.get('total_interest', 0):,.2f}", body_style)],
        [Paragraph("<b>Total Amount Repayable:</b>", body_style), Paragraph(f"<b>INR {kfs_data.get('total_repayment', 0):,.2f}</b>", body_style),
         Paragraph("<b>Calculation Method:</b>", body_style), Paragraph("Standard Reducing Balance", body_style)],
    ]
    t_terms = Table(terms_data, colWidths=[135, 135, 135, 135])
    t_terms.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#ffffff")),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#cbd5e1")),
        ('PADDING', (0,0), (-1,-1), 5),
    ]))
    story.append(t_terms)
    story.append(Spacer(1, 10))

    # First-Year Amortization Schedule Breakdown
    story.append(Paragraph("<b>Amortization Schedule Breakdown (First 12 Months)</b>", heading_style))
    sched_rows = schedule or kfs_data.get("first_year_schedule", [])
    table_rows = [
        [
            Paragraph("Month", table_header_style),
            Paragraph("Opening Balance", table_header_style),
            Paragraph("Monthly EMI", table_header_style),
            Paragraph("Principal", table_header_style),
            Paragraph("Interest", table_header_style),
            Paragraph("Closing Balance", table_header_style),
        ]
    ]

    for item in sched_rows[:12]:
        table_rows.append([
            Paragraph(str(item.get("month", "")), table_cell_style),
            Paragraph(f"INR {item.get('opening_balance', 0):,.2f}", table_cell_style),
            Paragraph(f"INR {item.get('emi', 0):,.2f}", table_cell_style),
            Paragraph(f"INR {item.get('principal_component', 0):,.2f}", table_cell_style),
            Paragraph(f"INR {item.get('interest_component', 0):,.2f}", table_cell_style),
            Paragraph(f"INR {item.get('closing_balance', 0):,.2f}", table_cell_style),
        ])

    t_sched = Table(table_rows, colWidths=[45, 100, 95, 100, 100, 100])
    t_sched.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#f1f5f9")),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#cbd5e1")),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.HexColor("#ffffff"), colors.HexColor("#f8fafc")]),
        ('PADDING', (0,0), (-1,-1), 4),
    ]))
    story.append(t_sched)
    story.append(Spacer(1, 12))

    # Academic Notice Footer
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#cbd5e1"), spaceAfter=6))
    story.append(Paragraph(
        f"KFS Reference: {kfs_data.get('reference_number', f'KFS-APP-{application.id:06d}')} | "
        f"Generated: {now_str} | Academic FinTech Simulation Platform — Not a Legal Document",
        footer_style
    ))

    doc.build(story)
    buffer.seek(0)
    return buffer

