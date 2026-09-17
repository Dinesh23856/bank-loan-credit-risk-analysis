# Render deployment

## API service
Build: `pip install --upgrade pip && pip install -r requirements.txt`
Start: `python -m uvicorn backend.main:app --host 0.0.0.0 --port $PORT`
Health: `/health`

Set backend environment variables:
- `DATABASE_URL` — MySQL SQLAlchemy URL using `mysql+pymysql://`
- `JWT_SECRET_KEY` — random secret, 32+ characters
- `FRONTEND_ORIGINS` — deployed React origin(s), comma separated

Initialize the database once:
`python -m backend.init_db`

Create the first administrator from a secure environment:
`python scripts/create_admin.py`

## Frontend
Build:
`npm ci && npm run build`
Publish directory: `dist`

Set `VITE_API_URL` to the deployed FastAPI URL.

No SQLite, PostgreSQL, MongoDB, or Streamlit is used.
