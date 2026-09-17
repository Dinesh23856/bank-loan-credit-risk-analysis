# Project Update Report

Updated the existing Bank Loan Approval & Customer Credit Risk Analysis project in place.

## Preserved
The four existing production model artifacts were not retrained or replaced:
- `models/loan_amount.joblib`
- `models/loan_approval.joblib`
- `models/credit_score.joblib`
- `models/credit_risk.joblib`

## Updated
- Render Blueprint now includes FastAPI backend + React/Vite static frontend with SPA rewrite.
- Added JWT expiry environment configuration.
- Added admin drift monitoring endpoint using PSI and KS monitoring signals.
- Added explicit risk request/response schemas.
- Expanded Admin Dashboard with task-specific model metrics, confusion matrices, richer KPIs, and drift monitoring.
- Updated the Jupyter notebook with the instructor's full-stack integration requirements and submission checklist.
- Kept controlled retraining behavior; production model artifacts are not automatically overwritten.

## Validation
- Python compileall: PASS
- Pytest: 21 passed, 1 skipped
- Frontend build: not run because `frontend/node_modules` is not included and no network installation was performed.
- Real MySQL/Render deployment: not tested in this environment.

## Important
Model performance values are read from `reports/training_metrics.json`; no metrics were fabricated.
