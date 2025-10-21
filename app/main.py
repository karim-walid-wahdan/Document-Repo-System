# app/main.py
from fastapi import FastAPI
from app.routers import health, auth
from app.routers import documents

app = FastAPI(title="DocRepo API", version="0.2.0")

app.include_router(health.router)
app.include_router(auth.router)
app.include_router(documents.router)
