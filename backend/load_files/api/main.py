import redis
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from load_files.api.routes.auth import router as auth_router
from load_files.api.routes.upload import router as upload_router
from load_files.api.routes.websocket import router as ws_router
from load_files.config.settings import settings
from load_files.utils.logger import logger

app = FastAPI(title=settings.APP_NAME, version=settings.APP_VERSION)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(upload_router)
app.include_router(ws_router)


@app.get("/health")
def health():
    checks = {"status": "healthy", "version": settings.APP_VERSION}
    try:
        r = redis.Redis.from_url(settings.REDIS_URL)
        r.ping()
        r.close()
        checks["redis"] = "ok"
    except Exception as e:
        checks["redis"] = "error"
        checks["status"] = "degraded"
        logger.warning("Health check: Redis unavailable: %s", e)
    return checks


logger.info(
    "Starting %s v%s (env=%s, log=%s)",
    settings.APP_NAME, settings.APP_VERSION,
    settings.ENVIRONMENT, settings.LOG_LEVEL,
)
