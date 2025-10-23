# app/db/models.py
from typing import Optional
from datetime import datetime
from sqlalchemy.orm import Mapped, mapped_column, DeclarativeBase, relationship
from sqlalchemy import String, Integer, Text, Boolean, ForeignKey, DateTime, SmallInteger, Enum, BigInteger, UniqueConstraint
from sqlalchemy import Index , text
from sqlalchemy import ForeignKey, ForeignKeyConstraint, BigInteger
from enum import Enum as PyEnum
from sqlalchemy.dialects.postgresql import INET
class Base(DeclarativeBase):
    pass

# app/db/models.py
from enum import Enum as PyEnum
from sqlalchemy import Enum as PgEnum
# ... other imports

class DocVisibility(str, PyEnum):
    public = "public"
    internal = "internal"
    restricted = "restricted"

class Role(Base):
    __tablename__ = "role"
    role_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(15), unique=True, nullable=False)

class Department(Base):
    __tablename__ = "department"
    department_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    location: Mapped[str] = mapped_column(String(50), nullable=False)

class AppUser(Base):
    __tablename__ = "app_user"
    user_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    pass_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    role_id: Mapped[int] = mapped_column(ForeignKey("role.role_id"), nullable=False, default=2)
    department_id: Mapped[int] = mapped_column(ForeignKey("department.department_id"), nullable=False, default=1)

class Document(Base):
    __tablename__ = "document"
    doc_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(200), unique=True, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)

    
    visibility: Mapped[DocVisibility] = mapped_column(
        PgEnum(DocVisibility, name="doc_visibility", create_type=False),  # <<<
        nullable=False,
        default=DocVisibility.internal,
    )

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

class DocAccess(Base):
    __tablename__ = "doc_access"
    department_id: Mapped[int] = mapped_column(ForeignKey("department.department_id", ondelete="CASCADE"), primary_key=True)
    doc_id: Mapped[int] = mapped_column(ForeignKey("document.doc_id", ondelete="CASCADE"), primary_key=True)
    access_level: Mapped[int] = mapped_column(SmallInteger, nullable=False)

class Tag(Base):
    __tablename__ = "tag"
    tag_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)

    # keep the Python name you like (deleted or tag_deleted), but map to the DB column
    deleted: Mapped[bool] = mapped_column(
        "tag_deleted",        # <-- actual column name in the DB
        Boolean,
        nullable=False,
        server_default=text("false"),
    )
class DocumentTag(Base):
    __tablename__ = "document_tag"
    doc_id: Mapped[int] = mapped_column(ForeignKey("document.doc_id", ondelete="CASCADE"), primary_key=True)
    tag_id: Mapped[int] = mapped_column(ForeignKey("tag.tag_id", ondelete="CASCADE"), primary_key=True)

class DocumentVersion(Base):
    __tablename__ = "document_version"
    doc_id: Mapped[int] = mapped_column(ForeignKey("document.doc_id", ondelete="CASCADE"), primary_key=True)
    version_no: Mapped[int] = mapped_column(Integer, primary_key=True)
    storage_key: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)
    is_latest: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    uploaded_by: Mapped[int] = mapped_column(ForeignKey("app_user.user_id"), nullable=False)

Index("idx_document_version_latest", DocumentVersion.doc_id, postgresql_where=(DocumentVersion.is_latest == True))

class ActionLog(Base):
    __tablename__ = "action_log"

    log_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    action_type: Mapped[str] = mapped_column(String(30), nullable=False)
    ip: Mapped[str] = mapped_column(INET, nullable = False)
    time_stamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)

    user_id: Mapped[int] = mapped_column(ForeignKey("app_user.user_id"), nullable=False)

    # composite foreign key to document_version (doc_id, version_no)
    doc_id: Mapped[int] = mapped_column(Integer, nullable=False)
    version_no: Mapped[int] = mapped_column(Integer, nullable=False)

    __table_args__ = (
        ForeignKeyConstraint(
            ["doc_id", "version_no"],
            ["document_version.doc_id", "document_version.version_no"],
            name="fk_actionlog_docver",
        ),
    )
class DepartmentRole(Base):
    __tablename__ = "department_role"
    department_id: Mapped[int] = mapped_column(ForeignKey("department.department_id", ondelete="CASCADE"), primary_key=True)
    role_id: Mapped[int] = mapped_column(ForeignKey("role.role_id", ondelete="CASCADE"), primary_key=True)
