# QuantLab

Interactive quantitative research and backtesting platform.

Built with **FastAPI · Python 3.11 · Next.js 14 · React 18 · Tailwind CSS · Recharts**.

---

## Quick start — Docker (recommended)

Requires Docker Desktop (or Docker Engine + Docker Compose V2).

```bash
docker compose up --build
```

| Service | URL |
|---|---|
| Frontend dashboard | http://localhost:3000 |
| Backend API | http://localhost:8000 |
| Interactive API docs | http://localhost:8000/docs |

The first build pulls base images and installs all dependencies; subsequent
`docker compose up` reuses cached layers and starts in seconds.

### Stop

```
Ctrl+C
```

then clean up containers:

```bash
docker compose down
```

---

## Quick start — local development (no Docker)

### Prerequisites

- Python 3.11+
- Node.js 20+
- A virtual environment at `.venv/` (or activate your own)

### 1 — Backend

```powershell
# activate the virtual environment (Windows PowerShell)
.venv\Scripts\Activate.ps1

# install Python dependencies
pip install -r backend\requirements.txt

# start the API server
cd backend
uvicorn app.main:app --reload --port 8000
```

Backend is now at http://localhost:8000  
Swagger docs at http://localhost:8000/docs

### 2 — Frontend

Open a second terminal:

```powershell
cd frontend
npm install           # first time only
npm run dev
```

Frontend is now at http://localhost:3000

---

## Running the backend test suite

```powershell
cd backend
python -m pytest -q
```

All tests use synthetic price data — no network calls are made.

---

## Project layout

```
quantlab/
├── backend/
│   ├── app/
│   │   ├── main.py          FastAPI routes
│   │   ├── strategies.py    Signal generation (lookahead-bias-free)
│   │   ├── backtest.py      Vectorised backtest engine
│   │   ├── metrics.py       Sharpe, CAGR, drawdown, …
│   │   ├── schemas.py       Pydantic request/response models
│   │   ├── data.py          yfinance OHLCV download layer
│   │   └── utils.py         Shared helpers
│   ├── tests/               pytest test suite (325+ tests)
│   ├── Dockerfile
│   ├── .dockerignore
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── app/             Next.js App Router pages
│   │   ├── components/      React components
│   │   └── lib/             API client, types, formatters
│   ├── Dockerfile
│   ├── .dockerignore
│   └── package.json
├── .github/
│   └── workflows/
│       └── ci.yml           GitHub Actions: backend tests + frontend build
├── docker-compose.yml
└── README.md
```

---

## How Docker networking works

```
Browser  →  http://localhost:3000/api/*
               │
         Next.js server (frontend container)
               │  rewrites /api/* → http://backend:8000/*
               │  (Docker-internal DNS resolves "backend")
               ▼
         FastAPI server (backend container)
               │  port 8000 (not exposed to browser directly)
               ▼
         Response flows back to browser
```

The browser never calls the backend directly.
`BACKEND_URL=http://backend:8000` is baked into the Next.js production build
at `docker compose up --build` time via a Docker `ARG`.

---

## Troubleshooting

### Port 3000 is already in use

```bash
# find and kill the process using the port (macOS/Linux)
lsof -ti:3000 | xargs kill

# Windows PowerShell
Stop-Process -Id (Get-NetTCPConnection -LocalPort 3000).OwningProcess -Force
```

Or change the port mapping in `docker-compose.yml`:

```yaml
ports:
  - "3001:3000"   # host:container
```

### Port 8000 is already in use

Same approach as above, substituting `8000`.

### Frontend shows "Backend request failed"

1. Confirm both containers are running: `docker compose ps`
2. Confirm the backend is healthy: `curl http://localhost:8000/health`
3. Check container logs: `docker compose logs backend`
4. If you changed `docker-compose.yml`, rebuild: `docker compose up --build`

### Changes to source code are not reflected

The Docker image is built once.  After editing source code, rebuild:

```bash
docker compose up --build
```

For a faster inner loop, use the local development workflow (`npm run dev` +
`uvicorn --reload`) instead of Docker.

---

## CI

GitHub Actions runs on every push and pull request to `main`:

- **backend-tests** — installs Python deps, runs `pytest -q`
- **frontend-build** — installs Node deps, runs `next build`

See `.github/workflows/ci.yml`.
