from __future__ import annotations
import math
from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, Any, List, Optional
from datetime import datetime
from fastapi import HTTPException

# Mandatory Academic / Demo Disclaimers
KFS_DISCLAIMER_HEADER = "ACADEMIC/DEMO — NOT A LEGAL OR REGULATORY DOCUMENT"
KFS_DISCLAIMER_TEXT = (
    "This document and its associated financial schedules are generated strictly for "
    "academic demonstration, fintech simulation, and educational coursework. It does "
    "NOT constitute a legally binding credit agreement, official bank commitment, or "
    "regulatory disclosure under RBI, CFPB, or any financial authority."
)

def _quantize_currency(value: float | Decimal) -> float:
    """Safely round monetary figures to 2 decimal places using standard ROUND_HALF_UP."""
    d = Decimal(str(value)) if not isinstance(value, Decimal) else value
    return float(d.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))

def validate_financial_inputs(principal: float, annual_interest_rate: float, loan_term_months: int) -> None:
    """
    Validates numeric boundaries and safety for loan calculations.
    Raises HTTPException(422) on invalid input.
    """
    if principal is None or not isinstance(principal, (int, float)):
        raise HTTPException(status_code=422, detail="Principal must be a valid numeric value.")
    if not math.isfinite(principal):
        raise HTTPException(status_code=422, detail="Principal must be finite (not NaN or Infinity).")
    if principal <= 0:
        raise HTTPException(status_code=422, detail="Principal must be greater than 0.")
    if principal > 100_000_000:
        raise HTTPException(status_code=422, detail="Principal exceeds allowable maximum limit of 100,000,000.")

    if annual_interest_rate is None or not isinstance(annual_interest_rate, (int, float)):
        raise HTTPException(status_code=422, detail="Annual interest rate must be a valid numeric value.")
    if not math.isfinite(annual_interest_rate):
        raise HTTPException(status_code=422, detail="Annual interest rate must be finite (not NaN or Infinity).")
    if annual_interest_rate < 0:
        raise HTTPException(status_code=422, detail="Annual interest rate cannot be negative.")
    if annual_interest_rate > 100:
        raise HTTPException(status_code=422, detail="Annual interest rate exceeds allowable maximum limit of 100%.")

    if loan_term_months is None or not isinstance(loan_term_months, int):
        raise HTTPException(status_code=422, detail="Loan term in months must be an integer.")
    if loan_term_months <= 0:
        raise HTTPException(status_code=422, detail="Loan term in months must be greater than 0.")
    if loan_term_months > 480:
        raise HTTPException(status_code=422, detail="Loan term in months exceeds allowable maximum limit of 480 months (40 years).")

def calculate_emi(principal: float, annual_interest_rate: float, loan_term_months: int) -> Dict[str, Any]:
    """
    Computes deterministic Equated Monthly Installment (EMI), total interest,
    and total repayment amount for a reducing-balance loan.
    """
    validate_financial_inputs(principal, annual_interest_rate, loan_term_months)

    P = Decimal(str(principal))
    R = Decimal(str(annual_interest_rate))
    n = loan_term_months

    # Monthly periodic rate: r = R / (12 * 100)
    if R == Decimal("0"):
        r = Decimal("0")
        emi_dec = P / Decimal(n)
        total_payment_dec = P
        total_interest_dec = Decimal("0")
    else:
        r = R / Decimal("1200")
        # EMI = P * r * (1+r)^n / ((1+r)^n - 1)
        one_plus_r = Decimal("1") + r
        pow_factor = one_plus_r ** n
        numerator = P * r * pow_factor
        denominator = pow_factor - Decimal("1")
        emi_dec = numerator / denominator

    emi = _quantize_currency(emi_dec)
    # Total payment must reconcile with the actual schedule installments paid by the borrower
    total_payment = _quantize_currency(Decimal(str(emi)) * Decimal(n))
    total_interest = _quantize_currency(Decimal(str(total_payment)) - P)

    return {
        "principal": _quantize_currency(P),
        "annual_interest_rate": float(R),
        "monthly_interest_rate": round(float(r), 6),
        "loan_term_months": n,
        "emi": emi,
        "total_payment": total_payment,
        "total_interest": total_interest
    }

def generate_amortization_schedule(principal: float, annual_interest_rate: float, loan_term_months: int) -> Dict[str, Any]:
    """
    Generates a deterministic month-by-month loan amortization schedule.
    Absorbs accumulated fractional-cent rounding in the final installment
    to guarantee closing balance is exactly 0.00.
    """
    calc = calculate_emi(principal, annual_interest_rate, loan_term_months)
    P = Decimal(str(calc["principal"]))
    n = calc["loan_term_months"]
    r = Decimal(str(calc["monthly_interest_rate"]))
    standard_emi = Decimal(str(calc["emi"]))

    schedule: List[Dict[str, Any]] = []
    current_balance = P
    cumulative_interest = Decimal("0")
    cumulative_principal = Decimal("0")
    cumulative_payment = Decimal("0")

    for month in range(1, n + 1):
        opening_balance = current_balance
        interest_comp = opening_balance * r
        interest_comp_rounded = interest_comp.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        if month < n:
            principal_comp_rounded = standard_emi - interest_comp_rounded
            closing_balance_dec = opening_balance - principal_comp_rounded
            emi_month_rounded = standard_emi

            # Safeguard against accidental negative balance
            if closing_balance_dec < Decimal("0"):
                principal_comp_rounded = opening_balance
                closing_balance_dec = Decimal("0")
                emi_month_rounded = principal_comp_rounded + interest_comp_rounded
        else:
            # Final month: Absorb rounding differences so balance reaches exactly 0.00
            principal_comp_rounded = opening_balance
            closing_balance_dec = Decimal("0.00")
            emi_month_rounded = principal_comp_rounded + interest_comp_rounded

        current_balance = closing_balance_dec
        cumulative_interest += interest_comp_rounded
        cumulative_principal += principal_comp_rounded
        cumulative_payment += emi_month_rounded

        schedule.append({
            "month": month,
            "opening_balance": _quantize_currency(opening_balance),
            "emi": _quantize_currency(emi_month_rounded),
            "principal_component": _quantize_currency(principal_comp_rounded),
            "interest_component": _quantize_currency(interest_comp_rounded),
            "closing_balance": _quantize_currency(closing_balance_dec)
        })

    return {
        "principal": _quantize_currency(P),
        "annual_interest_rate": calc["annual_interest_rate"],
        "monthly_interest_rate": calc["monthly_interest_rate"],
        "loan_term_months": n,
        "emi": calc["emi"],
        "total_payment": _quantize_currency(cumulative_payment),
        "total_interest": _quantize_currency(cumulative_interest),
        "schedule": schedule
    }

def get_application_financial_summary(application: Any) -> Dict[str, Any]:
    """
    Extracts financial terms from a LoanApplication record and computes official terms.
    """
    is_approved_like = (
        (application.status in ("APPROVED", "OFFERED", "ACCEPTED")) or
        (application.approval_status == "Approved")
    )

    if is_approved_like and application.predicted_loan_amount and application.predicted_loan_amount > 0:
        principal = float(application.predicted_loan_amount)
    else:
        principal = float(application.loan_amount)

    rate = float(application.interest_rate) if application.interest_rate is not None else 10.5
    tenure = int(application.loan_term_months) if application.loan_term_months is not None else 36

    calc = calculate_emi(principal=principal, annual_interest_rate=rate, loan_term_months=tenure)

    return {
        "application_id": application.id,
        "loan_amount": calc["principal"],
        "requested_amount": float(application.loan_amount),
        "approved_amount": float(application.predicted_loan_amount) if application.predicted_loan_amount else None,
        "interest_rate": calc["annual_interest_rate"],
        "loan_term_months": calc["loan_term_months"],
        "emi": calc["emi"],
        "total_interest": calc["total_interest"],
        "total_payment": calc["total_payment"],
        "loan_status": application.status or "SUBMITTED",
        "approval_status": application.approval_status or "Pending",
        "is_approved_offer": is_approved_like
    }

def generate_kfs_data(application: Any, applicant_name: str) -> Dict[str, Any]:
    """
    Builds the structured Academic/Demo Key Fact Statement (KFS) payload for an eligible application.
    Rejects REJECTED applications with HTTP 400.
    """
    status_str = (application.status or "").upper()
    approval_str = (application.approval_status or "").title()

    if status_str == "REJECTED" or approval_str == "Rejected":
        raise HTTPException(
            status_code=400,
            detail=(
                f"Application #{application.id} is REJECTED. An Academic/Demo Key Fact Statement (KFS) "
                "cannot be issued or generated for a rejected loan application. "
                "Please refer to the Statement of Adverse Action."
            )
        )

    summary = get_application_financial_summary(application)
    schedule_data = generate_amortization_schedule(
        principal=summary["loan_amount"],
        annual_interest_rate=summary["interest_rate"],
        loan_term_months=summary["loan_term_months"]
    )

    now_iso = datetime.utcnow().isoformat() + "Z"

    return {
        "document_type": "ACADEMIC_DEMO_KFS",
        "document_title": "Key Fact Statement (KFS) — Academic / Demo Loan Summary",
        "disclaimer_header": KFS_DISCLAIMER_HEADER,
        "disclaimer_text": KFS_DISCLAIMER_TEXT,
        "application_id": application.id,
        "reference_number": f"KFS-APP-{application.id:06d}",
        "applicant_name": applicant_name,
        "city": application.city or "N/A",
        "region": application.region or "N/A",
        "loan_type": getattr(application, "loan_type", "Standard Loan"),
        "loan_amount": summary["loan_amount"],
        "requested_amount": summary["requested_amount"],
        "interest_rate": summary["interest_rate"],
        "interest_type": "Reducing Balance (Standard Periodic)",
        "loan_term_months": summary["loan_term_months"],
        "repayment_frequency": "Monthly",
        "emi": summary["emi"],
        "total_interest": summary["total_interest"],
        "total_repayment": summary["total_payment"],
        "loan_status": summary["loan_status"],
        "approval_status": summary["approval_status"],
        "reviewed_at": application.reviewed_at.isoformat() if application.reviewed_at else None,
        "reviewer_role": application.reviewer_role or "AUTOMATED_OR_UNDERWRITER",
        "generated_at": now_iso,
        "first_year_schedule": schedule_data["schedule"][:12]
    }
