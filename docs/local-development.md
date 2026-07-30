# Local development

## Docker workflow

Docker Compose is the supported cross-platform workflow:

```bash
docker compose up --build -d
docker compose ps
docker compose logs -f backend worker frontend
docker compose down
```

Use `docker compose down --volumes` only when intentionally discarding local
PostgreSQL and Redis data.

The production-like UI is on port 8080. To use Vite hot reload:

```bash
docker compose --profile dev up --build frontend-dev
```

## Native backend

Use Python 3.12:

```bash
cd backend
python -m venv .venv
.venv/Scripts/pip install -e ".[dev]"
.venv/Scripts/uvicorn cloudwise.main:app --reload
```

On macOS or Linux, executables are under `.venv/bin/`.

## Native frontend

Use Node.js 22 or newer:

```bash
cd frontend
npm ci
npm run dev
```

## Configuration

Copy `.env.example` to `.env` for local overrides. Startup validation fails
fast for unsupported environments, invalid database drivers, invalid URLs, or
unsafe request-size values. Production secrets must not be stored in `.env`.

