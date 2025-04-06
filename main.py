from contextlib import asynccontextmanager
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uvicorn
from apps.calculator.route import router as calculator_router
from constants import SERVER_URL, PORT, ENV
from mangum import Mangum
from apps.calculator.utils import analyze_image
import os

@asynccontextmanager
async def lifespan(app: FastAPI):
    yield

app = FastAPI(lifespan=lifespan)

# Configure CORS with specific origins
origins = [
    "http://localhost:5173",    # Local development
    "http://localhost:3000",    # Alternative local port
    "http://127.0.0.1:5173",   # Local development alternative
    "http://127.0.0.1:3000",   # Alternative local port
    "https://solvo-frontend.vercel.app",  # Your frontend Vercel domain
    "https://solvoai.vercel.app",         # Alternative frontend domain
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

@app.post("/analyze")
async def analyze(file: UploadFile = File(...)):
    try:
        # Save the uploaded file temporarily
        temp_file_path = f"temp_{file.filename}"
        with open(temp_file_path, "wb") as buffer:
            content = await file.read()
            buffer.write(content)
        
        # Analyze the image
        result = analyze_image(temp_file_path)
        
        # Clean up the temporary file
        os.remove(temp_file_path)
        
        return JSONResponse(content=result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

app.include_router(calculator_router, prefix="/calculate", tags=["calculate"])

# Create handler for Vercel
handler = Mangum(app)

# For local development
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
