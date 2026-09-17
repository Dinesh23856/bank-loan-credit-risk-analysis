"""
Adverse Action & Positive Factor Mapping Engine.

Provides model-derived adverse-action reasons based on factors that materially influenced
this specific prediction. These descriptions are algorithmically mapped from localized TreeSHAP
feature contributions and reflect the individual model decision rather than generic templates.

Note: Displaying a maximum of 4 reasons is a user interface presentation choice for clarity
and readability, not a statutory constraint.
"""

from __future__ import annotations
from typing import Optional

FEATURE_REASON_MAP = {
    "debt_to_income_ratio": "Total monthly debt obligations are high relative to gross monthly income.",
    "dti_ratio": "Total monthly debt obligations are high relative to gross monthly income.",
    "previous_defaults": "Past delinquent or defaulted credit obligations negatively impacted creditworthiness.",
    "credit_utilization": "Revolving credit line utilization is high relative to available credit limits.",
    "credit_score": "External consumer credit bureau score does not meet standard threshold.",
    "bank_balance": "Available liquid deposit reserves are low relative to requested borrowing amount.",
    "savings": "Dedicated savings and emergency cash reserves are insufficient for the requested liability.",
    "annual_income": "Total reported annual earnings are insufficient to support requested debt service.",
    "requested_loan_amount": "The requested financing amount is high relative to applicant income and collateral profile.",
    "collateral_value": "Appraised value of pledged collateral is insufficient to mitigate loan principal exposure.",
    "payment_history": "History of past-due payments or inconsistent repayment schedules impacted the decision.",
    "previous_loans": "Number of active or past loan commitments affects total outstanding leverage.",
    "loan_term": "Selected loan repayment duration increases risk exposure over the life of the loan.",
    "interest_rate": "Applicable interest rate structure results in elevated debt service burden.",
    "assets": "Total verifiable asset base is low relative to requested credit exposure.",
    "employment_type": "Current employment profile or tenure provides insufficient stability for the requested obligation.",
    "credit_history": "Length or depth of established credit history does not meet underwriting criteria."
}

POSITIVE_FACTOR_MAP = {
    "debt_to_income_ratio": "Favorable debt-to-income ratio indicates strong capacity to handle monthly obligations.",
    "previous_defaults": "Clean credit history with zero or minimal past defaults supports creditworthiness.",
    "credit_utilization": "Prudent and low revolving credit utilization demonstrates disciplined credit management.",
    "credit_score": "Strong consumer credit score demonstrates established credit reliability.",
    "bank_balance": "Substantial liquid bank balance provides strong liquidity buffer.",
    "savings": "Healthy accumulated savings and cash reserves strengthen repayment security.",
    "annual_income": "High annual income provides robust cash flow for servicing the obligation.",
    "collateral_value": "Substantial collateral valuation provides strong security for the loan.",
    "payment_history": "Consistent on-time payment track record confirms repayment reliability.",
    "assets": "Substantial verifiable personal assets bolster overall financial standing."
}

def map_adverse_reason(feature_name: str) -> str:
    cleaned = feature_name.lower().strip()
    if "__" in cleaned:
        cleaned = cleaned.split("__", 1)[1]
    for key in FEATURE_REASON_MAP:
        if cleaned.startswith(key):
            return FEATURE_REASON_MAP[key]
    return f"Feature '{cleaned.replace('_', ' ').capitalize()}' did not meet favorable underwriting criteria."

def map_positive_factor(feature_name: str) -> str:
    cleaned = feature_name.lower().strip()
    if "__" in cleaned:
        cleaned = cleaned.split("__", 1)[1]
    for key in POSITIVE_FACTOR_MAP:
        if cleaned.startswith(key):
            return POSITIVE_FACTOR_MAP[key]
    return f"Favorable positioning in {cleaned.replace('_', ' ')} positively influenced the decision."
