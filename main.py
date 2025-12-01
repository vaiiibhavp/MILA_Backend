import asyncio
import os
from fastapi import FastAPI, Request
from api.routes import adminauth_route
from api.routes import user_profile_api, files_api

from core.utils.exceptions import CustomValidationError, custom_validation_error_handler, validation_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from tasks import send_email_task
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime, timedelta, timezone
from config.db_config import create_indexes, user_collection
import requests
import json
import logging
from json import JSONEncoder
from pydantic import Field
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from config.db_seeder.AdminSeeder import seed_admin


from starlette.middleware.base import BaseHTTPMiddleware
app = FastAPI()

# Make sure your uploads folder exists
UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# Mount the uploads folder as static
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")


# Health check endpoints
@app.get("/health")
async def health_check():
    """Basic health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "service": "Go Bet Backend"
    }

@app.get("/health/detailed")
async def detailed_health_check():
    """Detailed health check with database connectivity"""
    import time
    start_time = time.time()
    
    health_status = {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "service": "Go Bet Backend",
        "checks": {}
    }
    
    # Check database connectivity
    try:
        from config.db_config import mongodb_client
        db_start = time.time()
        is_connected = await mongodb_client.ping()
        db_duration = time.time() - db_start
        
        health_status["checks"]["database"] = {
            "status": "healthy" if is_connected else "unhealthy",
            "response_time": f"{db_duration:.3f}s",
            "connected": is_connected
        }
        
        if not is_connected:
            health_status["status"] = "degraded"
            
    except Exception as e:
        health_status["checks"]["database"] = {
            "status": "unhealthy",
            "error": str(e)
        }
        health_status["status"] = "unhealthy"
    
    # Check Redis connectivity
    try:
        from core.utils.redis_helper import redis_client
        redis_start = time.time()
        await redis_client.ping()
        redis_duration = time.time() - redis_start
        
        health_status["checks"]["redis"] = {
            "status": "healthy",
            "response_time": f"{redis_duration:.3f}s"
        }
        
    except Exception as e:
        health_status["checks"]["redis"] = {
            "status": "unhealthy",
            "error": str(e)
        }
        health_status["status"] = "degraded"
    
    # Add performance metrics
    from core.utils.logging_config import db_monitor, api_monitor
    health_status["metrics"] = {
        "database": db_monitor.get_stats(),
        "api": api_monitor.get_stats()
    }
    
    total_duration = time.time() - start_time
    health_status["response_time"] = f"{total_duration:.3f}s"
    
    return health_status

@app.get("/health/ready")
async def readiness_check():
    """Readiness check for Kubernetes/container orchestration"""
    try:
        from config.db_config import mongodb_client
        is_connected = await mongodb_client.ping()
        
        if is_connected:
            return {"status": "ready"}
        else:
            return {"status": "not_ready", "reason": "database_not_connected"}
            
    except Exception as e:
        return {"status": "not_ready", "reason": f"database_error: {str(e)}"}

@app.get("/health/live")
async def liveness_check():
    """Liveness check for Kubernetes/container orchestration"""
    return {"status": "alive"}


# Define the base directory and static directory
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")

# Ensure the static directory exists
if not os.path.exists(STATIC_DIR):
    os.makedirs(STATIC_DIR)

# Mount the static files directory
app.mount("/static", StaticFiles(directory="static"), name="static")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,  # Allow cookies and credentials
    allow_methods=["*"],  # Allow all HTTP methods (GET, POST, etc.)
    allow_headers=["*"],  # Allow all headers
)

# Add request monitoring middleware
@app.middleware("http")
async def monitor_requests(request: Request, call_next):
    import time
    start_time = time.time()
    
    # Log request start
    logger.info(f"[START] {request.method} {request.url.path}")
    
    try:
        response = await call_next(request)
        duration = time.time() - start_time
        
        # Log request completion
        logger.info(f"[COMPLETE] {request.method} {request.url.path} - {response.status_code} in {duration:.3f}s")
        
        # Monitor slow requests
        if duration > 5.0:  # 5 seconds threshold
            logger.warning(f"[SLOW] {request.method} {request.url.path} took {duration:.3f}s")
        
        # Update API monitor
        api_monitor.log_request(
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            duration=duration
        )
        
        return response
        
    except Exception as e:
        duration = time.time() - start_time
        logger.error(f"[ERROR] {request.method} {request.url.path} after {duration:.3f}s - {str(e)}")
        raise


app.include_router(adminauth_route.router)



# Scheduler Instance
scheduler = BackgroundScheduler()

# Supported languages
SUPPORTED_LANGS = ["en", "fr"]

# Middleware for detecting language
async def detect_language(request: Request, call_next):
    lang = request.headers.get("Accept-Language", "en").split(",")[0].split("-")[0]
    if lang not in SUPPORTED_LANGS:
        lang = "en"
    request.state.lang = lang
    return await call_next(request)

# Add middleware to FastAPI
app.add_middleware(BaseHTTPMiddleware, dispatch=detect_language)


@app.on_event("startup")
async def init_scheduler():
    print("[STARTUP] Starting application initialization...")

    scheduler = AsyncIOScheduler()

    # Initialize database connection
    try:
        from config.db_config import initialize_database
        db_initialized = await initialize_database()
        if not db_initialized:
            print("[ERROR] Database initialization failed - application may not function properly")
        else:
            print("[SUCCESS] Database initialized successfully")

            try:
                await seed_admin()
                print("[SUCCESS] Admin seeding completed")
            except Exception as seeder_error:
                print(f"[ERROR] Admin seeding failed: {seeder_error}")
    except Exception as e:
        print(f"[ERROR] Database initialization error: {e}")
    

    scheduler.start()
    print("✅ Scheduler initialized successfully")
    print("🟢 Registered jobs:")
    for job in scheduler.get_jobs():
        print(f"    • {job.id} - Next run at: {job.next_run_time}")
    
    print("🚀 Application startup completed successfully!")
    

@app.on_event("shutdown")
async def shutdown_event():
    print("🛑 Starting application shutdown...")
    
    # Shutdown scheduler
    try:
        logger.info("Shutting down scheduler...")
        scheduler.shutdown()
        print("✅ Scheduler shutdown completed")
    except Exception as e:
        print(f"❌ Error shutting down scheduler: {e}")
    
    # Close database connections
    try:
        from config.db_config import close_database
        await close_database()
        print("✅ Database connections closed")
    except Exception as e:
        print(f"❌ Error closing database connections: {e}")
    
    # Close Redis connections
    try:
        from core.utils.redis_helper import close_redis_connections
        await close_redis_connections()
        print("✅ Redis connections closed")
    except Exception as e:
        print(f"❌ Error closing Redis connections: {e}")
    
    print("🛑 Application shutdown completed")

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    errors = exc.errors()
    
    # Extract field names and error messages
    formatted_errors = {err["loc"][-1]: err["msg"] for err in errors}  

    return JSONResponse(
        content={
            "message": "Validation Error",
            "data": {"errors": formatted_errors},  # More readable error structure
            "success": False
        },
        status_code=422  # Use 422 for validation errors
    )


# Configure comprehensive logging
from core.utils.logging_config import setup_logging, get_logger, api_monitor

# Setup logging with file and console output
setup_logging(
    log_level=logging.INFO,
    log_to_file=True,
    log_to_console=True
)
logger = get_logger(__name__)

class DateTimeEncoder(JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)

def main():
    scheduler = init_scheduler()
    logger.info("Scheduler started")
    
    try:
        # Run initial update
        update_ev_data()
        
        # Keep the main thread alive
        while True:
            pass
    except (KeyboardInterrupt, SystemExit):
        logger.info("Shutting down scheduler...")
        scheduler.shutdown()

if __name__ == "__main__":
    import uvicorn
    from config.basic_config import settings

    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.RELOAD
    )
