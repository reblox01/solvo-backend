FROM python:3.11-slim

# Prevents Python from writing .pyc files to disc and buffers stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install system deps required for some Python packages (Pillow, wheels)
RUN apt-get update && \
    apt-get install -y --no-install-recommends build-essential libjpeg-dev zlib1g-dev && \
    rm -rf /var/lib/apt/lists/*

# Copy only requirements first to leverage Docker cache
COPY requirements.txt ./

RUN python -m pip install --upgrade pip setuptools wheel && \
    pip install -r requirements.txt

# Copy app code
COPY . .

# Expose default port (Render will provide PORT env var at runtime)
EXPOSE 8000

# Run the FastAPI app with Uvicorn, allowing Render to override the port via $PORT
CMD ["sh", "-lc", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}"]


