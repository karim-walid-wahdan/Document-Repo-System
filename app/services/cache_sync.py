# app/services/cache_sync.py
from __future__ import annotations

from collections import defaultdict
from typing import Dict, List

import json
import redis.asyncio as redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    Department,
    Role,
    DepartmentRole,
    Tag as TagModel,
)

# ------------------ Department cache ------------------

DEPT_INDEX_KEY = "dept:index"          # set of department ids (strings)
DEPT_KEY = "dept:{dept_id}"            # JSON blob per department

def _dept_key(dept_id: int) -> str:
    return DEPT_KEY.format(dept_id=dept_id)

async def snapshot_all_departments(session: AsyncSession) -> Dict[int, dict]:
    """
    Build an in-memory snapshot:
      {dept_id: { department_id, name, location, roles: [{role_id, name}, ...] }}
    """
    rows = await session.execute(
        select(
            Department.department_id,
            Department.name,
            Department.location,
            Role.role_id,
            Role.name,
        )
        .select_from(Department)
        .join(
            DepartmentRole,
            DepartmentRole.department_id == Department.department_id,
            isouter=True,
        )
        .join(Role, Role.role_id == DepartmentRole.role_id, isouter=True)
        .order_by(Department.department_id, Role.role_id)
    )

    snapshot: Dict[int, dict] = {}
    grouped: Dict[int, List[tuple]] = defaultdict(list)

    for dep_id, dep_name, dep_loc, role_id, role_name in rows.all():
        grouped[dep_id].append((role_id, role_name))
        if dep_id not in snapshot:
            snapshot[dep_id] = {
                "department_id": dep_id,
                "name": dep_name,
                "location": dep_loc,
                "roles": [],
            }

    for dep_id, items in grouped.items():
        roles = [
            {"role_id": int(rid), "name": rname}
            for rid, rname in items
            if rid is not None
        ]
        snapshot[dep_id]["roles"] = roles

    # If there are departments but no role mappings, ensure they still appear
    if not snapshot:
        for d in (await session.execute(select(Department))).scalars().all():
            snapshot[d.department_id] = {
                "department_id": d.department_id,
                "name": d.name,
                "location": d.location,
                "roles": [],
            }
    return snapshot

async def write_all_departments_to_redis(r: redis.Redis, snapshot: Dict[int, dict]) -> None:
    pipe = r.pipeline()
    pipe.delete(DEPT_INDEX_KEY)
    for dep_id, payload in snapshot.items():
        pipe.set(_dept_key(dep_id), json.dumps(payload, ensure_ascii=False))
        pipe.sadd(DEPT_INDEX_KEY, str(dep_id))
    await pipe.execute()

async def refresh_one_department(session: AsyncSession, r: redis.Redis, department_id: int) -> None:
    rows = await session.execute(
        select(
            Department.department_id,
            Department.name,
            Department.location,
            Role.role_id,
            Role.name,
        )
        .select_from(Department)
        .join(
            DepartmentRole,
            DepartmentRole.department_id == Department.department_id,
            isouter=True,
        )
        .join(Role, Role.role_id == DepartmentRole.role_id, isouter=True)
        .where(Department.department_id == department_id)
        .order_by(Role.role_id)
    )

    dep = {"department_id": department_id, "name": None, "location": None, "roles": []}
    found = False
    for dep_id, dep_name, dep_loc, role_id, role_name in rows.all():
        found = True
        dep["name"] = dep_name
        dep["location"] = dep_loc
        if role_id is not None:
            dep["roles"].append({"role_id": int(role_id), "name": role_name})

    pipe = r.pipeline()
    if not found:
        pipe.srem(DEPT_INDEX_KEY, str(department_id))
        pipe.delete(_dept_key(department_id))
        await pipe.execute()
        return

    pipe.set(_dept_key(department_id), json.dumps(dep, ensure_ascii=False))
    pipe.sadd(DEPT_INDEX_KEY, str(department_id))
    await pipe.execute()

async def refresh_departments_with_role(session: AsyncSession, r: redis.Redis, role_id: int) -> None:
    dep_ids = (
        await session.execute(
            select(DepartmentRole.department_id).where(DepartmentRole.role_id == role_id)
        )
    ).scalars().all()
    for dep_id in dep_ids:
        await refresh_one_department(session, r, int(dep_id))

# ------------------ Tag cache ------------------

TAG_INDEX_KEY = "tag:index"        # set of tag ids
TAG_KEY = "tag:{tag_id}"           # json payload per tag
TAG_LEX_KEY = "tag:lex"            # sorted set for lex prefix search (members = lower(name))
TAG_NAME2ID = "tag:name2id"        # hash lower(name) -> id

def _tag_key(tag_id: int) -> str:
    return TAG_KEY.format(tag_id=tag_id)

async def snapshot_all_tags(session: AsyncSession) -> Dict[int, dict]:
    rows = await session.execute(
        select(TagModel.tag_id, TagModel.name).order_by(TagModel.name)
    )
    snap: Dict[int, dict] = {
        int(tid): {"tag_id": int(tid), "name": name} for tid, name in rows.all()
    }
    return snap

async def write_all_tags_to_redis(r: redis.Redis, snapshot: Dict[int, dict]) -> None:
    pipe = r.pipeline()
    pipe.delete(TAG_INDEX_KEY)
    pipe.delete(TAG_LEX_KEY)
    pipe.delete(TAG_NAME2ID)
    for tid, payload in snapshot.items():
        nm = (payload.get("name") or "").strip()
        lower = nm.lower()
        pipe.set(_tag_key(tid), json.dumps(payload, ensure_ascii=False))
        pipe.sadd(TAG_INDEX_KEY, str(tid))
        pipe.zadd(TAG_LEX_KEY, {lower: 0})  # same score → lexicographic range works
        pipe.hset(TAG_NAME2ID, lower, tid)
    await pipe.execute()

async def refresh_all_tags(session: AsyncSession, r: redis.Redis) -> None:
    snap = await snapshot_all_tags(session)
    await write_all_tags_to_redis(r, snap)