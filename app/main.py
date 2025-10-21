# app/main.py
from fastapi import FastAPI
from starlette.exceptions import HTTPException as StarletteHTTPException
from fastapi.responses import JSONResponse
import logging, uuid

from app.routers import health, auth, documents
from app.routers import departments, roles
from app.db.session import AsyncSessionLocal
from app.core.cache import get_redis
from app.services.cache_sync import snapshot_all_departments, write_all_departments_to_redis
from app.routers import users
app = FastAPI(title="DocRepo API", version="0.1.0")
app.include_router(users.router)
app.include_router(health.router)
app.include_router(auth.router)
app.include_router(documents.router)
app.include_router(departments.router)
app.include_router(roles.router)
logger = logging.getLogger("uvicorn.error")
@app.on_event("startup")
async def warm_department_cache():
    try:
        async with AsyncSessionLocal() as session:
            r = await get_redis()
            snapshot = await snapshot_all_departments(session)
            await write_all_departments_to_redis(r, snapshot)
            logger.info("Departments cache warmed: %d items", len(snapshot))
    except Exception:
        logger.exception("Failed to warm departments cache")

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
