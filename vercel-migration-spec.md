# Vercel Migration Spec

## Overview

Migrate the Solvo FastAPI backend from Render (Docker) to Vercel Serverless Functions.

---

## Current State

| Component | Detail |
|-----------|--------|
| **Framework** | FastAPI (Python 3.11) |
| **Current host** | Render (Docker, `master` branch, auto-deploy) |
| **Key file** | `main.py` — FastAPI app with Mangum adapter already present |
| **Endpoints** | `GET /`, `POST /analyze` (file upload), `POST /calculate` (base64 image + JSON) |
| **AI provider** | Google Gemini 1.5 Flash via `google-generativeai==0.8.5` |
| **Env var** | `GEMINI_API_KEY` |
| **CORS origins** | `localhost:5173`, `localhost:3000`, `solvo-frontend.vercel.app`, `solvoai.vercel.app` |
| **Render config** | `render.yaml` + `Dockerfile` (to be removed) |

---

## Target State

### Hosting
- **Platform**: Vercel (Hobby / Free plan)
- **Runtime**: Python Serverless Functions via `@vercel/python`
- **URL**: Default Vercel-assigned `.vercel.app` domain (no custom domain)
- **Branch**: `master` (auto-deploy)

### Plan Constraints (Hobby)
- Function timeout: **10 seconds**
- Memory: **1024 MB** (default)
- Bundle size: **< 500 MB** uncompressed
- Bandwidth: **100 GB / month**
- No WebSockets
- Read-only filesystem (no writing temp files to disk)

---

## Migration Tasks

### 1. Project Restructuring

Move the FastAPI entrypoint into the `api/` directory as expected by Vercel:

```
vercel-migration-spec.md
├── api/
│   └── index.py          # Entrypoint (wraps FastAPI app with Mangum)
├── apps/
│   └── calculator/
│       ├── route.py      # Calculator router (unchanged)
│       └── utils.py      # Gemini image analysis (modified — in-memory)
├── constants.py          # Config (unchanged)
├── schema.py             # Pydantic models (unchanged)
├── vercel.json           # NEW — Vercel build/rewrite config
├── requirements.txt      # Dependencies (unchanged)
├── .gitignore            # Updated to exclude .vercel/
└── README.md
```

**Files to remove:**
- `Dockerfile` — no longer needed (serverless, not containerized)
- `render.yaml` — Render deployment config

### 2. Create `vercel.json`

```json
{
  "builds": [
    {
      "src": "api/index.py",
      "use": "@vercel/python"
    }
  ],
  "rewrites": [
    {
      "source": "/(.*)",
      "destination": "api/index.py"
    }
  ]
}
```

### 3. Create `api/index.py`

This is the new entrypoint. It must:
- Import and expose the FastAPI `app` instance
- Wrap with `Mangum(handler)`
- Import all routers and configure CORS

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from mangum import Mangum
from apps.calculator.route import router as calculator_router
from apps.calculator.utils import analyze_image
from constants import GEMINI_API_KEY
import os, io

@asynccontextmanager
async def lifespan(app: FastAPI):
    yield

app = FastAPI(lifespan=lifespan)

# CORS — allow frontend + backend Vercel URLs
origins = [
    "http://localhost:5173",
    "http://localhost:3000",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:3000",
    "https://solvo-frontend.vercel.app",
    "https://solvoai.vercel.app",
    "https://solvo-backend.vercel.app",  # Add backend URL after first deploy
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["*"],
    max_age=600,
)

@app.get("/")
async def read_root():
    return {"message": "Welcome to the Math Solver API"}

@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "solvo-backend"}

@app.post("/analyze")
async def analyze(file: UploadFile = File(...)):
    try:
        content = await file.read()
        # In-memory processing — no temp files
        image_bytes = io.BytesIO(content)
        from PIL import Image
        image = Image.open(image_bytes)
        result = analyze_image(image, dict_of_vars={})
        return JSONResponse(content=result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

app.include_router(calculator_router, prefix="/calculate", tags=["calculate"])

# Vercel serverless adapter
handler = Mangum(app)
```

### 4. Fix File System Issue in `/analyze`

**Current code** (in `main.py`) writes temp files to disk:
```python
temp_file_path = f"temp_{file.filename}"
with open(temp_file_path, "wb") as buffer:
    content = await file.read()
    buffer.write(content)
result = analyze_image(temp_file_path)
os.remove(temp_file_path)
```

**New approach** — process entirely in memory:
```python
content = await file.read()
image = Image.open(io.BytesIO(content))
result = analyze_image(image, dict_of_vars={})
```

**Note:** The `analyze_image()` function in `utils.py` currently accepts a file path string OR a PIL Image. Verify it works with PIL Image directly (it does — the calculator route already passes PIL Image objects).

### 5. Environment Variables

Set in Vercel Dashboard (Settings → Environment Variables):

| Variable | Value | Environment |
|----------|-------|-------------|
| `GEMINI_API_KEY` | `<your-key>` | Production, Preview, Development |

### 6. Logging & Observability

Add structured logging to the API entrypoint:

```python
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("solvo-backend")

# Add to each endpoint
logger.info(f"Processing request: {file.filename}")
```

Add structured error responses with error codes:

```python
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    logger.error(f"Unhandled error: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error", "detail": str(exc)}
    )
```

### 7. Rate Limiting

Implement basic rate limiting using Vercel's built-in features or a lightweight in-memory approach:

**Option A — Vercel Edge Config (recommended for production):**
- Use Vercel's rate limiting middleware or a lightweight decorator

**Option B — Simple in-memory rate limiter (for Hobby):**
```python
from collections import defaultdict
import time

RATE_LIMIT = 30  # requests per minute
rate_limit_store = defaultdict(list)

def rate_limit(client_ip: str):
    now = time.time()
    rate_limit_store[client_ip] = [
        t for t in rate_limit_store[client_ip] if now - t < 60
    ]
    if len(rate_limit_store[client_ip]) >= RATE_LIMIT:
        raise HTTPException(status_code=429, detail="Rate limit exceeded")
    rate_limit_store[client_ip].append(now)
```

**Note:** In-memory rate limiting resets per cold start on serverless. For true rate limiting, use an external store (Upstash Redis) or Vercel's built-in rate limiting.

### 8. Remove Render Configuration

- Delete `Dockerfile`
- Delete `render.yaml`
- Update `.gitignore` to add `.vercel/`

### 9. Update CORS After Deploy

After first Vercel deploy, update CORS origins to include the new backend URL:
```python
"https://<your-project>.vercel.app"
```

---

## Endpoint Summary (Post-Migration)

| Method | Path | Description | Request | Response |
|--------|------|-------------|---------|----------|
| `GET` | `/` | Health/welcome | — | `{"message": "..."}` |
| `GET` | `/health` | Health check | — | `{"status": "ok", ...}` |
| `POST` | `/analyze` | Image analysis | `multipart/form-data` with `file` | `[{expr, result, assign}]` |
| `POST` | `/calculate` | Calculator | JSON `{image, dict_of_vars}` | `{message, type, data}` |

---

## Files Changed

| File | Action | Notes |
|------|--------|-------|
| `api/index.py` | **CREATE** | New Vercel entrypoint |
| `vercel.json` | **CREATE** | Vercel build config |
| `Dockerfile` | **DELETE** | No longer needed |
| `render.yaml` | **DELETE** | No longer needed |
| `.gitignore` | **MODIFY** | Add `.vercel/` |
| `main.py` | **DELETE** | Replaced by `api/index.py` |
| `apps/calculator/utils.py` | **NO CHANGE** | Already accepts PIL Image |
| `apps/calculator/route.py` | **NO CHANGE** | Already works with PIL Image |
| `constants.py` | **NO CHANGE** | Environment variable loading unchanged |
| `schema.py` | **NO CHANGE** | Pydantic models unchanged |
| `requirements.txt` | **NO CHANGE** | Same dependencies |

---

## Verification Checklist

- [ ] `vercel dev` runs locally without errors
- [ ] `GET /` returns welcome message
- [ ] `GET /health` returns `{"status": "ok"}`
- [ ] `POST /analyze` processes image without writing temp files
- [ ] `POST /calculate` returns calculation results
- [ ] CORS headers present on responses
- [ ] `GEMINI_API_KEY` loaded from environment
- [ ] No temp files created during `/analyze`
- [ ] Cold start time under 10 seconds
- [ ] Deploy successfully via `vercel --prod`
- [ ] All endpoints accessible on production URL

---

## Open Questions

1. **Rate limiting strategy**: In-memory is ephemeral (resets on cold start). Need external store (Upstash Redis) for persistent rate limiting?
2. **CORS backend URL**: Exact backend URL TBD after first deploy — needs to be added to CORS origins.
3. **Monitoring/alerting**: Any specific tools or dashboards for monitoring serverless function performance?
