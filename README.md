# Urban Pulse — Crowdsourced Civic Infrastructure Prioritization Platform

Urban Pulse is a full-stack Django and PostgreSQL (Supabase) web application connecting urban residents with Local Government Units (LGUs) to report neighborhood infrastructure hazards, prioritize urgent repairs via community "Power-Up" voting, and track transparent dispatch resolutions.

## Tech Stack
- **Backend & Frontend:** Full-Stack Django 6.1 (Django Templates + CSS)
- **Database:** PostgreSQL (Supabase) via `psycopg` & `dj-database-url`

## Local Setup

1. **Create and activate a virtual environment:**
   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```
2. **Install dependencies:**
   ```powershell
   pip install -r requirements.txt
   ```
3. **Configure environment variables:**
   Copy `.env.example` to `.env` and fill in your values (never commit `.env`):
   ```env
   SECRET_KEY=your-django-secret-key
   DEBUG=True
   ALLOWED_HOSTS=127.0.0.1,localhost
   DATABASE_URL=postgresql://postgres.[PROJECT-REF]:[PASSWORD]@aws-1-ap-northeast-1.pooler.supabase.com:5432/postgres
   ```
4. **Apply migrations and run the development server:**
   ```powershell
   py manage.py migrate
   py manage.py createsuperuser
   py manage.py runserver
   ```
   *(If testing custom `404` / `500` error pages locally with `DEBUG=False` in `.env`, run `py manage.py runserver --insecure` so static stylesheets continue serving.)*

## Running Automated Tests

Run the full Django test suite:
```powershell
python manage.py test
```

Run tests for a specific app:
```powershell
python manage.py test reports
python manage.py test accounts dashboard
```

> **Note on Supabase test databases:** Running `python manage.py test` against Supabase attempts to `CREATE DATABASE test_postgres`, which requires superuser DB privileges that managed Supabase poolers restrict. If your Supabase user cannot create a temporary test database, pass a local PostgreSQL test database or run `manage.py test` with a dedicated test `DATABASE_URL` in `.env`.

## Git Branching Workflow
- `main`: Stable production-ready releases only (no direct commits)
- `develop`: Integration branch
- Work branches from `develop`: `fix/*`, `hardening/*`, `test/*`, `feature/*`
