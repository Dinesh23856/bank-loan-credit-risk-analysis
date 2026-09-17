# Bank Loan Approval & Customer Credit Risk Analysis
**Enterprise Machine Learning Platform for Credit Risk Assessment & Automated Underwriting**

---

## 1. Abstract & Executive Overview
In contemporary retail and commercial banking, assessing applicant creditworthiness and pricing loan risk requires balancing operational throughput, algorithmic precision, regulatory compliance, and interpretability. Traditional credit scorecards often rely on static heuristics that fail to capture non-linear financial interactions or adapt to macroeconomic drift.

This project delivers an end-to-end, full-stack Machine Learning and Model Governance platform for automated loan eligibility determination, loan amount pricing, credit score estimation, and multi-tier credit risk classification. Built on an enterprise stack comprising **FastAPI**, **React 18**, **MySQL 8**, **SQLAlchemy ORM**, **MultiFernet Field Encryption**, and **scikit-learn**, the system wraps four immutable, mathematically audited machine learning models within an asynchronous, role-governed underwriting architecture.

The platform provides localized feature attribution via **SHAP (SHapley Additive exPlanations)**, actionable **What-If Counterfactual Recourse**, deterministic reducing-balance **EMI & Amortization schedules**, an academic **Key Fact Statement (KFS)** generator, automated **Data & Concept Drift monitoring** (Kolmogorov-Smirnov test and Population Stability Index), **Fairness & Disparate Impact auditing**, and a grounded **Banking AI Assistant** powered by Google Gemini 3.5 Flash Lite with deterministic offline fallbacks.

---

## 2. Problem Statement & Objectives
### Problem Statement
Lending institutions process thousands of loan applications daily. Manual underwriting creates processing bottlenecks, human error, subjective biases, and inconsistent risk thresholds. Conversely, unconstrained black-box AI models introduce regulatory liability under the Equal Credit Opportunity Act (ECOA) and Fair Credit Reporting Act (FCRA) by failing to provide legally defensible adverse action notices or audit trails.

### Primary Objectives
1. **Multi-Task Predictive Intelligence**: Predict binary loan approval, recommend optimal approved loan amounts, predict standardized credit scores (300–850), and classify customer credit risk into calibrated risk tiers (Low, Medium, High).
2. **Transparent & Actionable Explainability**: Provide transparent local SHAP waterfall attributions for every automated inference and compute feasible counterfactual recourse recommendations for declined applicants.
3. **Enterprise Guarded Workflow & RBAC**: Enforce a strict 12-state underwriting lifecycle protected by Role-Based Access Control (RBAC) across four distinct roles (`CUSTOMER`, `UNDERWRITER`, `RISK_ANALYST`, `ADMIN`).
4. **Model Governance & Integrity Tracking**: Maintain a persistent Model Registry recording immutable SHA-256 artifact hashes, model cards, lifecycle status, dataset provenance, and data/concept drift monitoring.
5. **Data Protection & Regulatory Compliance**: Protect applicant Personally Identifiable Information (PII) using AES-128 MultiFernet encryption at rest, secure JWT authentication with HttpOnly refresh cookies, and comprehensive immutable audit logging.

---

## 3. Technology Stack

| Layer | Technologies | Role & Implementation |
|---|---|---|
| **Frontend UI / SPA** | React 18, Vite 6, Tailwind CSS, Lucide Icons, Recharts | Dynamic single-page application with dark-mode aesthetic, responsive layouts, real-time charts, and PWA manifest. |
| **Backend API Gateway** | FastAPI (Python 3.11/3.13), Uvicorn, Pydantic v2 | High-performance asynchronous REST API, strict request validation schemas, custom exception handling, and SlowAPI rate limiting. |
| **Machine Learning** | scikit-learn, joblib, NumPy, Pandas | Serialized immutable pipeline models utilizing Random Forest and Gradient Boosting algorithms. |
| **Model Explainability** | SHAP (`shap.TreeExplainer`) | Localized feature contribution values, adverse action reason extraction, and base-value delta computation. |
| **Database & ORM** | MySQL 8.0, SQLAlchemy 2.0, PyMySQL | Relational persistence, connection pooling, transactional consistency, and encrypted column types. |
| **Database Migrations** | Alembic | Version-controlled schema evolutions tracked to single linear head `004_phase2_model_registry_and_governance`. |
| **Security & Auth** | bcrypt, python-jose (JWT), Cryptography (Fernet) | Bcrypt password hashing, short-lived JWT access tokens, HttpOnly rotating refresh tokens, and deterministic/random AES encryption. |
| **Document Generation** | ReportLab | Deterministic server-side PDF generation for Key Fact Statements (KFS) and Sanction Letters. |
| **Generative AI** | Google Gemini 3.5 Flash Lite (via REST/SDK) | Grounded natural-language banking assistant operating with strict ECOA safety guardrails and offline fallback engine. |
| **Testing & Quality** | pytest, pytest-asyncio, HTTPX TestClient | 148 automated unit, regression, RBAC, financial, drift, and E2E integration test suites. |

---

## 4. System Architecture

```
                                  +---------------------------------------+
                                  |     React 18 + Vite Frontend SPA      |
                                  | (Customer / UW / Analyst / Admin)     |
                                  +-------------------+-------------------+
                                                      |
                                             HTTPS / JSON REST
                                                      |
                                  +-------------------v-------------------+
                                  |       FastAPI Application Core        |
                                  |  - Route Guards & RBAC Middleware     |
                                  |  - SlowAPI Rate Limiter               |
                                  |  - Pydantic v2 Input Validation       |
                                  +---------+-------------------+---------+
                                            |                   |
               +----------------------------+                   +----------------------------+
               |                                                                             |
+--------------v---------------+                                              +--------------v---------------+
|     Persistence Layer        |                                              |   Machine Learning Engine    |
| - MySQL 8.0 Engine           |                                              | - 4 Immutable .joblib Models |
| - SQLAlchemy 2.0 ORM         |                                              | - SHAP TreeExplainer Engine  |
| - Deterministic Fernet (PII) |                                              | - Counterfactual Recourse    |
| - 10 Relational Tables       |                                              | - Drift & Fairness Service   |
+--------------+---------------+                                              +--------------+---------------+
               |                                                                             |
               +----------------------------+                   +----------------------------+
                                            |                   |
                                  +---------v-------------------v---------+
                                  |        External & Auxiliary           |
                                  | - ReportLab PDF Engine (Academic KFS) |
                                  | - Gemini 3.5 Flash Lite (Chatbot)     |
                                  | - Multi-Head Alembic Migrations       |
                                  +---------------------------------------+
```

---

## 5. Dataset Description & Feature Engineering

### 1. Loan Approval & Amount Dataset (`data/raw/loan_data.csv`)
- **Records**: 4,269 applicant profiles
- **SHA-256**: `cee57f9c187a4cfd97ccf40030a279d6ab41bdd3c78bb80704c118a2ecf0554a`
- **Features**: `no_of_dependents`, `education`, `self_employed`, `income_annum`, `loan_amount`, `loan_term`, `cibil_score`, `residential_assets_value`, `commercial_assets_value`, `luxury_assets_value`, `bank_asset_value`, `loan_status`.

### 2. Credit Risk & Score Dataset (`data/raw/credit_risk_data.csv`)
- **Records**: 32,581 applicant records
- **SHA-256**: `f579fb61724b5abf61e1af563ba3b3e6b71657bb949042ac315d68f3f4d22c2c`
- **Features**: `person_age`, `person_income`, `person_home_ownership`, `person_emp_length`, `loan_intent`, `loan_grade`, `loan_amnt`, `loan_int_rate`, `loan_status`, `loan_percent_income`, `cb_person_default_on_file`, `cb_person_cred_hist_length`.

### Preprocessing & Leakage Elimination
- **Imputation & Scaling**: Numerical features are processed using `SimpleImputer(strategy='median')` and `StandardScaler()`. Categorical features are encoded using `OneHotEncoder(handle_unknown='ignore')`.
- **Target Leakage Prevention**: To prevent artificial data leakage, the `credit_risk` model was trained strictly without observed `credit_score` or derived `credit_strength` variables, ensuring genuine out-of-sample risk discrimination.

---

## 6. Immutable Machine Learning Models & Performance

All four production models are serialized as `.joblib` pipelines and mathematically validated against baseline cryptographic hashes:

```
+---------------------+---------------------------+----------------+--------------+------------------+
| Model Identifier    | Algorithm Architecture    | Hyperparams    | Target       | Metric Score     |
+---------------------+---------------------------+----------------+--------------+------------------+
| loan_approval       | RandomForestClassifier    | n_est=350, d=18| loan_status  | Acc: 98.7%, F1: 0.99, AUC: 0.998|
| loan_amount         | RandomForestRegressor     | n_est=300, d=18| loan_amount  | R2: 0.892, MAE: 18,420 INR     |
| credit_score        | GradientBoostingRegressor | n_est=250, d=3 | credit_score | R2: 0.741, MAE: 24.3, RMSE: 31.8|
| credit_risk         | RandomForestClassifier    | n_est=400, d=20| risk_level   | Acc: 94.2%, Macro F1: 0.938    |
+---------------------+---------------------------+----------------+--------------+------------------+
```

### Immutable SHA-256 Hashes
- `models/loan_amount.joblib`: `963bff7f4317a6d373fd0aa0e324f698a32cabee2d7a4d12d9fdef5048fcabe6`
- `models/loan_approval.joblib`: `b70d0fd7ef583b3492e0ac57acf4cea5b0689844ad6615a3cbd6a46466c02f26`
- `models/credit_score.joblib`: `897948653b3982012b327746955a79b8487834f2bb0dcefa02dd0b9f3a553f59`
- `models/credit_risk.joblib`: `044aa75d7741d1bb6b448d3795b145350cacc65c8c6e598cff6e6df219d55922`

---

## 7. Model Explainability & What-If Recourse

### Localized SHAP Attributions
In compliance with regulatory adverse action transparency, every inference triggers `shap.TreeExplainer`. The platform computes log-odds contributions for every input feature, automatically extracting:
- **Top Adverse Drivers**: Features pushing the prediction toward denial (e.g., high debt-to-income ratio, low collateral value).
- **Positive Compensating Drivers**: Offsetting strengths (e.g., long employment tenure, substantial liquid savings).

### What-If Counterfactual Recourse Studio
Declined applicants receive algorithmic recourse recommendations identifying the minimum actionable delta required to reach an approval threshold (e.g., increasing collateral by ₹50,000 or extending tenure by 12 months), while locking immutable demographic characteristics.

---

## 8. Guarded Workflow Lifecycle & Underwriting Portal

Applications progress through a strictly audited 12-state workflow machine:
`SUBMITTED` -> `IN_REVIEW` -> `AUTO_APPROVED` / `MANUAL_REVIEW` / `AUTO_REJECTED` -> `UNDERWRITER_APPROVED` / `UNDERWRITER_REJECTED` -> `OFFER_GENERATED` -> `OFFER_ACCEPTED` / `EXPIRED` / `WITHDRAWN` -> `DISBURSED`

### Borderline Queue & Human-in-the-Loop Underwriting
- Inferences resulting in probabilities between `0.40` and `0.60` automatically transition to `MANUAL_REVIEW`.
- Only credentialed `UNDERWRITER` or `ADMIN` roles can access the review queue (`GET /underwriter/queue`) and render final credit determinations with mandatory audit comments.

---

## 9. Authentication, Security & RBAC Architecture

### Authentication Mechanism
The application enforces standard enterprise password-based authentication:
- **Password Protection**: Salted and hashed using `bcrypt` (12 work-factor rounds).
- **Session Tokens**: Stateless short-lived JWT access tokens signed with HMAC-SHA256 (`JWT_SECRET_KEY`).
- **Refresh Flow**: Rotating, cryptographically signed refresh tokens stored exclusively in `HttpOnly`, `SameSite=Lax` cookies.

> [!IMPORTANT]
> **Authentication Notice**: The current project implements Email + Password with bcrypt hashing, JWT tokens, and RBAC. **Email OTP / MFA is not implemented in the current academic version.**

### Role-Based Access Control (RBAC) Matrix
- `CUSTOMER`: Submit loan applications, view personal history, compute EMI, chat with AI assistant. Protected against IDOR/BOLA.
- `UNDERWRITER`: Access pending review queue, examine model outputs and SHAP drivers, approve or reject applications.
- `RISK_ANALYST`: Inspect Model Registry, execute on-demand SHA-256 integrity audits, monitor population drift and fairness metrics.
- `ADMIN`: Global user management, role reassignment, system-wide configuration, and immutable security audit log review.

---

## 10. Financial Computations & Academic Key Fact Statement (KFS)
- **Deterministic EMI Engine**: Standalone calculation using standard reducing-balance amortization formulas ($E = P \cdot r \cdot rac{(1+r)^n}{(1+r)^n - 1}$). Zero ML or LLM hallucinations.
- **Academic KFS Generator**: ReportLab-powered PDF generation providing transparency on principal, interest rate, tenure, monthly installment, and 12-month payment schedules.

---

## 11. Risk Analyst Dashboard, Drift & Fairness Monitoring
- **Data Drift Detection**: Automated Kolmogorov-Smirnov (KS) two-sample test and Population Stability Index (PSI) benchmarking live production inferences against training baselines over 7, 30, and 90-day rolling windows.
- **Fairness & Bias Auditing**: Calculates Demographic Parity Difference and Disparate Impact ratios across demographic attributes (gender, marital status) to alert analysts to potential disparate impacts.

---

## 12. Local Installation & Development Setup

### Prerequisites
- Python 3.11 or 3.13 (Anaconda / venv)
- Node.js 18+ and npm 9+
- MySQL Server 8.0+

### Step-by-Step Backend Setup
```bash
# 1. Clone repository and navigate to root
cd bank-loan-credit-risk-analysis

# 2. Create and activate virtual environment
python -m venv venv
# On Windows:
venv\Scriptsctivate
# On Linux/macOS:
source venv/bin/activate

# 3. Install backend dependencies
pip install -r requirements.txt

# 4. Configure environment variables
copy .env.example .env
# Edit .env with your MySQL credentials and a 32+ character JWT_SECRET_KEY

# 5. Run database migrations to linear head
python -m alembic upgrade head

# 6. (Optional) Bootstrap default admin user
python scripts/create_admin.py

# 7. Start FastAPI development server
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```

### Step-by-Step Frontend Setup
```bash
# 1. Navigate to frontend directory
cd frontend

# 2. Install npm packages
npm install

# 3. Start Vite dev server
npm run dev
# Frontend runs at http://localhost:5173
```

---

## 13. Verification, Automated Testing & Build

### Running Automated Test Suite
```bash
# Run complete test suite (148 tests)
pytest -q
# Expected result: 148 passed in ~35s
```

### Building Frontend for Production
```bash
npm --prefix frontend run build
# Expected result: 2,346 modules transformed, dist/ generated with 0 errors
```

---

## 14. Academic Limitations & Future Scope

### Academic & Demonstration Disclaimers
This platform is developed strictly as an engineering capstone and academic research project. The following boundaries are explicitly established:
1. **No Real Financial Integration**: Does not integrate with live banking cores, RBI/NPCI payment gateways, or live credit bureaus (e.g., CIBIL, Experian, Equifax).
2. **No KYC Verification**: Does not perform real Aadhaar, PAN, or DigiLocker verification.
3. **Demo Legal Notice**: The generated Key Fact Statements and Sanction Letters are for demonstration and compliance simulation purposes only; they do not constitute legal financial contracts.
4. **No Real Disbursement**: The `DISBURSED` state is a workflow simulation; no actual funds transfer occurs.
5. **No Autonomous Underwriting**: All credit assessments are algorithmic decision-support recommendations; human underwriting oversight is mandated for sensitive credit tiers.

### Future Scope
- Integration with Account Aggregator (AA) framework for automated bank statement analysis.
- Multi-Factor Authentication (TOTP via Authenticator Apps / WebAuthn).
- Distributed async workers using Celery and Redis message brokers for large-scale enterprise deployments.
- CI/CD automated model retraining pipelines via MLflow or Kubeflow.

---

## 15. License & Authorship
Developed for Academic Engineering Capstone Submission.  
Department of Computer Science & Engineering / Information Technology.  
© 2026. All rights reserved.
