# Deployment & Device Verification

## Backend — Render
1. Push this repository to GitHub.
2. Create a Render Web Service from the repository (the included `render.yaml` can be used as a Blueprint).
3. Build command: `pip install --upgrade pip && pip install -r requirements.txt`
4. Start command: `python -m uvicorn backend.main:app --host 0.0.0.0 --port $PORT`
5. Health check: `/health`
6. Set these backend environment variables: `ENVIRONMENT=production`, `DATABASE_URL`, `JWT_SECRET_KEY`, `JWT_EXPIRE_MINUTES`, `FRONTEND_ORIGINS`.
7. Run the DB initialization once against the production MySQL database: `python -m backend.init_db`.
8. Bootstrap the administrator once with `ADMIN_EMAIL`, `ADMIN_PASSWORD`, `ADMIN_NAME` and `python scripts/create_admin.py`.

## Frontend
From `frontend/`:
```bash
npm install
npm run build
```
Deploy the resulting `dist/` to a static host such as Render Static Site, Vercel, or Netlify. Set `VITE_API_URL` to the deployed API URL at build time.

Recommended local versions: Python 3.11.9 and Node 20–22.

## Local MySQL
If Docker is available:
```bash
docker compose up -d mysql
```
Then set:
`DATABASE_URL=mysql+pymysql://loanapp:change-me@127.0.0.1:3306/bank_loan_db`

## Android / iOS
The UI is responsive and PWA-enabled. Verify on a real Android Chrome and iOS Safari device after deployment. Check login, application submission, history/detail, admin tables/charts, orientation changes, and PWA installation. Real-device testing is environment-dependent and is not claimed by this repository audit.
