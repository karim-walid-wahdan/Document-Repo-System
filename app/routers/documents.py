# app/routers/documents.py
from datetime import datetime, timezone
from typing import Annotated, List, Optional
from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException, Query, status, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc, and_, exists
from app.db.session import get_session
from app.db.models import Document, DocumentVersion, Tag, DocumentTag, DocAccess, AppUser, Department, DocVisibility
from app.core.deps import get_current_user
from app.storage.s3 import get_s3_client
from app.core.settings import settings

router = APIRouter(prefix="/documents", tags=["documents"])

# ---------- Schemas
class DocumentOut(BaseModel):
    doc_id: int
    title: str
    description: str
    visibility: DocVisibility
    updated_at: datetime

class VersionOut(BaseModel):
    version_no: int
    storage_key: str
    file_size: int
    uploaded_at: datetime
    uploaded_by: int
    is_latest: bool

class SearchOut(BaseModel):
    doc: DocumentOut
    tags: List[str] = []
    latest_version: Optional[VersionOut] = None

# ---------- Helpers
async def _next_version_no(session: AsyncSession, doc_id: int) -> int:
    q = await session.execute(select(func.coalesce(func.max(DocumentVersion.version_no), 0)).where(DocumentVersion.doc_id == doc_id))
    return int(q.scalar_one()) + 1
async def _log_action(session: AsyncSession, *, user_id: int, doc_id: int, version_no: int, action_type: str, ip: str):
    await session.execute(
        func.pg_sleep(0)  # no-op to keep async path happy; replace with real INSERT using text() if you prefer
    )  # keep it minimal; or create ActionLog ORM row
# ---------- Endpoints
@router.post("", response_model=VersionOut, status_code=201)
async def create_document(
    request: Request,
    title: Annotated[str, Form()],
    description: Annotated[str, Form()],
    visibility: Annotated[DocVisibility, Form()] = DocVisibility.internal,
    tags: Annotated[Optional[str], Form()] = None,        # comma-separated
    file: UploadFile = File(...),
    user: AppUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    # create doc
    now = datetime.now(timezone.utc)
    doc = Document(title=title, description=description, visibility=visibility, created_at=now, updated_at=now)
    session.add(doc)
    await session.flush()  # get doc_id

    # tags
    tag_names = [t.strip() for t in (tags or "").split(",") if t.strip()]
    if tag_names:
        existing = dict((name, tid) for name, tid in (await session.execute(select(Tag.name, Tag.tag_id).where(Tag.name.in_(tag_names)))).all())
        for name in tag_names:
            tid = existing.get(name)
            if not tid:
                t = Tag(name=name)
                session.add(t)
                await session.flush()
                tid = t.tag_id
            session.add(DocumentTag(doc_id=doc.doc_id, tag_id=tid))

    # version 1
    vno = 1
    key = f"docs/{doc.doc_id}/v{vno}/{file.filename}"
    data = await file.read()
    s3 = get_s3_client()
    s3.put_object(Bucket=settings.S3_BUCKET, Key=key, Body=data, ContentType=file.content_type or "application/octet-stream")

    # mark as latest
    ver = DocumentVersion(
        doc_id=doc.doc_id,
        version_no=vno,
        storage_key=key,
        file_size=len(data),
        is_latest=True,
        uploaded_at=now,
        uploaded_by=user.user_id,
    )
    session.add(ver)
    await session.commit()
    await _log_action(session, user_id=user.user_id, doc_id=doc.doc_id, version_no=vno, action_type="upload", ip=str(request.client.host))
    return VersionOut(
        version_no=vno, storage_key=key, file_size=ver.file_size, uploaded_at=ver.uploaded_at, uploaded_by=user.user_id, is_latest=True
    )
@router.post("/{doc_id}/versions", response_model=VersionOut, status_code=201)
async def add_version(
    request: Request,
    doc_id: int,
    file: UploadFile = File(...),
    user: AppUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    
    doc = await session.get(Document, doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    vno = await _next_version_no(session, doc_id)
    key = f"docs/{doc_id}/v{vno}/{file.filename}"
    data = await file.read()
    s3 = get_s3_client()
    s3.put_object(Bucket=settings.S3_BUCKET, Key=key, Body=data, ContentType=file.content_type or "application/octet-stream")

    # unset previous latest
    await session.execute(
        DocumentVersion.__table__.update()
        .where(DocumentVersion.doc_id == doc_id, DocumentVersion.is_latest == True)
        .values(is_latest=False)
    )

    ver = DocumentVersion(
        doc_id=doc_id, version_no=vno, storage_key=key, file_size=len(data), is_latest=True,
        uploaded_at=datetime.now(timezone.utc), uploaded_by=user.user_id
    )
    session.add(ver)
    doc.updated_at = datetime.now(timezone.utc)
    await session.commit()
    await _log_action(session, user_id=user.user_id, doc_id=doc_id, version_no=vno, action_type="upload", ip=str(request.client.host))
    return VersionOut(version_no=vno, storage_key=key, file_size=ver.file_size, uploaded_at=ver.uploaded_at, uploaded_by=user.user_id, is_latest=True)
@router.get("", response_model=list[SearchOut])
async def search_documents(
    q: Optional[str] = Query(None, description="Search in title"),
    tags: Optional[list[str]] = Query(None),
    uploader: Optional[int] = Query(None, description="Filter by uploader user_id"),
    limit: int = 25,
    offset: int = 0,
    user: AppUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    # base: docs visible to user's department OR public
    subq_latest = select(
        DocumentVersion.doc_id, DocumentVersion.version_no, DocumentVersion.storage_key,
        DocumentVersion.file_size, DocumentVersion.uploaded_at, DocumentVersion.uploaded_by
    ).where(DocumentVersion.is_latest == True).subquery()
    tags_agg = func.array_agg(Tag.name).filter(Tag.name.isnot(None)).label("tags")
    stmt = (
        select(
        Document,
        subq_latest.c.version_no,
        subq_latest.c.storage_key,
        subq_latest.c.file_size,
        subq_latest.c.uploaded_at,
        subq_latest.c.uploaded_by,
        tags_agg,  # <-- use this
    )
        .join_from(Document, subq_latest, Document.doc_id == subq_latest.c.doc_id, isouter=True)
        .join(DocumentTag, DocumentTag.doc_id == Document.doc_id, isouter=True)
        .join(Tag, Tag.tag_id == DocumentTag.tag_id, isouter=True)
        .where(
            (Document.visibility != DocVisibility.restricted)
            | exists().where(and_(DocAccess.doc_id == Document.doc_id, DocAccess.department_id == user.department_id))
        )
        .group_by(Document.doc_id, subq_latest.c.version_no, subq_latest.c.storage_key, subq_latest.c.file_size, subq_latest.c.uploaded_at, subq_latest.c.uploaded_by)
        .order_by(desc(Document.updated_at))
        .limit(limit).offset(offset)
    )

    if q:
        stmt = stmt.where(Document.title.ilike(f"%{q}%"))
    if tags:
        stmt = stmt.having(func.bool_or(Tag.name.in_(tags)))
    if uploader:
        stmt = stmt.where(subq_latest.c.uploaded_by == uploader)

    rows = (await session.execute(stmt)).all()
    results = []
    for doc, vno, key, sz, up_at, up_by, tag_arr in rows:
        results.append(
            SearchOut(
                doc=DocumentOut(
                    doc_id=doc.doc_id, title=doc.title, description=doc.description,
                    visibility=doc.visibility, updated_at=doc.updated_at
                ),
                tags=tag_arr or [],
                latest_version=(VersionOut(version_no=vno, storage_key=key, file_size=sz, uploaded_at=up_at, uploaded_by=up_by, is_latest=True) if vno else None),
            )
        )
    return results
@router.get("/{doc_id}/versions", response_model=list[VersionOut])
async def version_history(doc_id: int, user: AppUser = Depends(get_current_user), session: AsyncSession = Depends(get_session)):
    stmt = select(DocumentVersion).where(DocumentVersion.doc_id == doc_id).order_by(desc(DocumentVersion.version_no))
    rows = (await session.execute(stmt)).scalars().all()
    if not rows:
        raise HTTPException(status_code=404, detail="Document not found or no versions")
    return [
        VersionOut(
            version_no=v.version_no, storage_key=v.storage_key, file_size=v.file_size,
            uploaded_at=v.uploaded_at, uploaded_by=v.uploaded_by, is_latest=v.is_latest
        )
        for v in rows
    ]
@router.get("/{doc_id}/download")
async def download(doc_id: int, version: Optional[int] = None, session: AsyncSession = Depends(get_session), user: AppUser = Depends(get_current_user)):
    # pick version
    if version is None:
        v = await session.scalar(select(DocumentVersion).where(DocumentVersion.doc_id == doc_id, DocumentVersion.is_latest == True))
    else:
        v = await session.scalar(select(DocumentVersion).where(DocumentVersion.doc_id == doc_id, DocumentVersion.version_no == version))
    if not v:
        raise HTTPException(status_code=404, detail="Version not found")
    s3 = get_s3_client()
    url = s3.generate_presigned_url(
        "get_object",
        Params={"Bucket": settings.S3_BUCKET, "Key": v.storage_key},
        ExpiresIn=300,
    )
    return {"url": url}