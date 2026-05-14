from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import os

app = FastAPI(title="IP Echo App")

@app.get("/")
async def get_ip(request: Request):
    """Return the client's originating IP address"""
    # Check for X-Forwarded-For header (common behind proxies/load balancers)
    x_forwarded_for = request.headers.get("x-forwarded-for")
    if x_forwarded_for:
        ip = x_forwarded_for.split(",")[0].strip()
    else:
        ip = request.client.host if request.client else "unknown"
    
    return JSONResponse({"ip": ip})

@app.get("/health")
async def health():
    """Liveness probe"""
    return JSONResponse({"status": "ok"})

@app.get("/ready")
async def ready():
    """Readiness probe"""
    return JSONResponse({"status": "ready"})

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)