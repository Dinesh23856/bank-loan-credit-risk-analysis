# Quickstart

## Requirements
- Python 3.11.9 (recorded in `.python-version`)
- Node.js 20+ recommended for the React/Vite frontend
- MySQL 8.x

## 1. Backend dependencies
```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

## 2. Start MySQL
Docker option:
```bash
docker run --name bank-loan-mysql -e MYSQL_ROOT_PASSWORD=change-me -e MYSQL_DATABASE=bank_loan_db -e MYSQL_USER=loanapp -e MYSQL_PASSWORD=change-me -p 3306:3306 -d mysql:8.4
```

Set `DATABASE_URL=mysql+pymysql://loanapp:change-me@127.0.0.1:3306/bank_loan_db`.

## 3. Backend environment
Copy `.env.example` to your local environment and set:
- `DATABASE_URL`
- `JWT_SECRET_KEY` (at least 32 random characters)
- `JWT_EXPIRE_MINUTES=60`
- `FRONTEND_ORIGINS=http://localhost:5173`
- `ADMIN_EMAIL`, `ADMIN_PASSWORD`, `ADMIN_NAME`

## 4. Initialize DB and create admin
```bash
python -m backend.init_db
python scripts/create_admin.py
```

## 5. Run API
```bash
python -m uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
```

Health: `http://127.0.0.1:8000/health`
Swagger: `http://127.0.0.1:8000/docs`

## 6. Run frontend
```bash
cd frontend
npm install
# create frontend/.env.local with VITE_API_URL=http://localhost:8000
npm run dev
```

Production builds require `VITE_API_URL`; the frontend intentionally fails fast if it is missing from a production build.

## 7. Tests
From the repository root:
```bash
python -m compileall .
pytest -q
```

## Render
Backend environment: `ENVIRONMENT=production`, `DATABASE_URL`, `JWT_SECRET_KEY`, `JWT_EXPIRE_MINUTES`, `FRONTEND_ORIGINS`.
Frontend environment: `VITE_API_URL`.
Admin bootstrap: `ADMIN_EMAIL`, `ADMIN_PASSWORD`, `ADMIN_NAME`.
See `DEPLOY_RENDER_AND_DEVICES.md` for deployment and device checks.
