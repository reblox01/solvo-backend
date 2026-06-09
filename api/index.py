import io
import logging
import time
from collections import defaultdict
from contextlib import asynccontextmanager

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from mangum import Mangum
from PIL import Image

from apps.calculator.route import router as calculator_router
from apps.calculator.utils import analyze_image

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("solvo-backend")

# ---------------------------------------------------------------------------
# Rate limiting (in-memory — resets on cold start)
# ---------------------------------------------------------------------------
RATE_LIMIT = 30  # requests per minute per client IP
_rate_limit_store: dict[str, list[float]] = defaultdict(list)


def _rate_limit(client_ip: str) -> None:
    now = time.time()
    _rate_limit_store[client_ip] = [
        t for t in _rate_limit_store[client_ip] if now - t < 60
    ]
    if len(_rate_limit_store[client_ip]) >= RATE_LIMIT:
        raise HTTPException(status_code=429, detail="Rate limit exceeded")
    _rate_limit_store[client_ip].append(now)


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

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
    "https://solvo-backend.vercel.app",
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


# ---------------------------------------------------------------------------
# Rate limiting middleware (applies to all routes)
@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    # Exempt health check and root endpoints
    if request.method not in ("POST", "PUT", "DELETE"):
        return await call_next(request)
    client_ip = request.headers.get("x-forwarded-for", "anonymous").split(",")[0].strip()
    _rate_limit(client_ip)
    response = await call_next(request)
    return response


# ---------------------------------------------------------------------------
# Exception handler
# ---------------------------------------------------------------------------
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error("Unhandled error: %s", exc, exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error", "detail": str(exc)},
    )


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@app.get("/")
async def read_root():
    return {"message": "Welcome to the Math Solver API"}


@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "solvo-backend"}


@app.post("/analyze")
async def analyze(file: UploadFile = File(...)):
    logger.info("Processing /analyze request: %s", file.filename)
    try:
        content = await file.read()
        if len(content) > 10 * 1024 * 1024:
            raise HTTPException(status_code=413, detail="File too large. Max 10MB.")
        # Validate file is a valid image (OWASP: validate inputs on backend)
        try:
            image = Image.open(io.BytesIO(content))
            image.verify()
            image = Image.open(io.BytesIO(content))  # Re-open after verify
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid image file")
        result = analyze_image(image, dict_of_vars={})
        logger.info("Analyzed %s — %d results", file.filename, len(result))
        return JSONResponse(content=result)
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to analyze image: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


app.include_router(calculator_router, prefix="/calculate", tags=["calculate"])


# ---------------------------------------------------------------------------
# Vercel serverless adapter
# ---------------------------------------------------------------------------
handler = Mangum(app)

# For local development
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
