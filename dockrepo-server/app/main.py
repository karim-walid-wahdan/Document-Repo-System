# app/main.py
from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI
from starlette.exceptions import HTTPException as StarletteHTTPException
from fastapi.responses import JSONResponse
from app.storage.s3 import ensure_bucket_exists
import logging, uuid


from app.db.session import AsyncSessionLocal
from app.core.cache import get_redis
from app.services.cache_sync import snapshot_all_departments, write_all_departments_to_redis
from app.routers import health, auth, documents, roles, departments, users, tags  
from app.services.cache_sync import (
    snapshot_all_departments, write_all_departments_to_redis,
    refresh_all_tags, 
)
app = FastAPI(title="DocRepo API", version="0.1.0")
app.include_router(users.router)
app.include_router(health.router)
app.include_router(auth.router)
app.include_router(documents.router)
app.include_router(departments.router)
app.include_router(roles.router)
app.include_router(tags.router)
logger = logging.getLogger("uvicorn.error")
@app.on_event("startup")
async def warm_caches():
    try:
        ensure_bucket_exists()
        async with AsyncSessionLocal() as session:
            r = await get_redis()
            # departments (existing)
            snapshot = await snapshot_all_departments(session)
            await write_all_departments_to_redis(r, snapshot)
            # tags (new)
            await refresh_all_tags(session, r)
            logger.info("Cache warm: departments=%d, tags=%d", len(snapshot), len(await r.smembers("tag:index")))
    except Exception:
        logger.exception("Failed to warm caches")
@app.exception_handler(StarletteHTTPException)
async def starlette_http_exception_handler(request, exc: StarletteHTTPException):
    msg = str(exc.detail)
    if exc.status_code == 400 and "parsing the body" in msg.lower():
        cid = uuid.uuid4().hex
        logger.exception("Multipart parse failed cid=%s path=%s", cid, request.url.path)
        return JSONResponse(
            status_code=400,
            content={"detail": "Bad multipart/form-data", "cid": cid},
        )
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173","http://localhost:3000","*"],  # tighten in prod
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)