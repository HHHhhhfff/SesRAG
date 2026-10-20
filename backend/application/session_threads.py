"""v2 会话读取、游标与元数据事务。"""

import base64
import binascii
import json
from dataclasses import asdict
from datetime import datetime, timezone

from sqlalchemy import and_, or_, select

from backend.application.branches import ACTIVE_RUN_STATES, default_branch, resolve_scope
from backend.application.errors import ApplicationError
from backend.application.threads import get_thread, now_utc, upgrade_for_v2_write
from backend.db.models import MessageModel, RunModel, ThreadModel
from backend.infrastructure.session.branches import SQLBranchRepository


async def thread_summary(session, thread):
    branch = await default_branch(session, thread.thread_id)
    return utc_projection(
        {
            **{
                name: getattr(thread, name)
                for name in (
                    "thread_id",
                    "owner_id",
                    "title",
                    "conversation_version",
                    "archived_at",
                    "created_at",
                    "updated_at",
                )
            },
            "default_branch_id": branch.branch_id,
        }
    )


def utc_projection(value):
    if isinstance(value, datetime):
        return (
            value.replace(tzinfo=timezone.utc)
            if value.tzinfo is None
            else value.astimezone(timezone.utc)
        )
    if isinstance(value, dict):
        return {key: utc_projection(item) for key, item in value.items()}
    if isinstance(value, list):
        return [utc_projection(item) for item in value]
    return value


def encode_cursor(thread):
    stamp = thread.updated_at.replace(tzinfo=timezone.utc).isoformat()
    return (
        base64.urlsafe_b64encode(
            json.dumps([stamp, thread.thread_id], separators=(",", ":")).encode()
        )
        .decode()
        .rstrip("=")
    )


def decode_cursor(cursor):
    try:
        if len(cursor) > 1024 or any(
            c not in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"
            for c in cursor
        ):
            raise ValueError
        pair = json.loads(base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4)))
        if (
            not isinstance(pair, list)
            or len(pair) != 2
            or not all(isinstance(x, str) and x for x in pair)
        ):
            raise ValueError
        stamp = datetime.fromisoformat(pair[0])
        if stamp.tzinfo is None:
            raise ValueError
        return stamp, pair[1]
    except (ValueError, TypeError, binascii.Error, UnicodeError):
        raise ApplicationError("INVALID_CURSOR", "分页游标无效", 422) from None


async def list_session_threads(session, settings, query):
    statement = select(ThreadModel).where(ThreadModel.owner_id == settings.owner_id)
    if not query.include_archived:
        statement = statement.where(ThreadModel.archived_at.is_(None))
    if query.cursor:
        stamp, identity = decode_cursor(query.cursor)
        statement = statement.where(
            or_(
                ThreadModel.updated_at < stamp,
                and_(ThreadModel.updated_at == stamp, ThreadModel.thread_id < identity),
            )
        )
    rows = list(
        (
            await session.scalars(
                statement.order_by(
                    ThreadModel.updated_at.desc(), ThreadModel.thread_id.desc()
                ).limit(query.limit + 1)
            )
        ).all()
    )
    more = len(rows) > query.limit
    rows = rows[: query.limit]
    return {
        "threads": [await thread_summary(session, row) for row in rows],
        "has_more": more,
        "next_cursor": encode_cursor(rows[-1]) if more else None,
    }


async def patch_session_thread(session, settings, thread_id, payload):
    thread = await get_thread(session, settings, thread_id)
    await session.refresh(thread, with_for_update=True)
    await upgrade_for_v2_write(session, thread)
    if "title" in payload.model_fields_set:
        thread.title = payload.title
    if "archived" in payload.model_fields_set:
        thread.archived_at = now_utc() if payload.archived else None
    thread.updated_at = now_utc()
    await session.commit()
    return await thread_summary(session, thread)


async def list_session_branches(session, settings, thread_id):
    await get_thread(session, settings, thread_id)
    return utc_projection(
        {
            "branches": [
                asdict(row) for row in await SQLBranchRepository(session).list_branches(thread_id)
            ]
        }
    )


async def session_thread_detail(session, settings, thread_id, query):
    thread = await get_thread(session, settings, thread_id)
    selected = query.branch_id or (await default_branch(session, thread_id)).branch_id
    repository = SQLBranchRepository(session)
    scope = await resolve_scope(repository, thread_id, selected)
    chain = scope.branches
    eligible = await repository.list_path_messages(
        thread_id, scope.segments, before_seq=query.before_seq, limit=query.limit + 1
    )
    more = len(eligible) > query.limit
    page = eligible[-query.limit :]
    rows = (
        await session.scalars(
            select(MessageModel)
            .where(MessageModel.message_id.in_([message.message_id for message in page]))
            .order_by(MessageModel.seq)
        )
    ).all()
    branch_ids = {branch.branch_id for branch in chain}
    path_ids = select(MessageModel.message_id).where(
        repository.path_condition(thread_id, scope.segments)
    )
    visible_ids = {message.message_id for message in page}
    selected_runs = (
        select(RunModel)
        .where(RunModel.thread_id == thread_id, RunModel.branch_id == selected)
        .order_by(RunModel.created_at.desc(), RunModel.run_id.desc())
    )
    active = await session.scalar(
        selected_runs.with_only_columns(RunModel.run_id)
        .where(RunModel.status.in_(ACTIVE_RUN_STATES))
        .limit(1)
    )
    recent = await session.scalar(selected_runs.with_only_columns(RunModel.run_id).limit(1))
    runs = (
        await session.scalars(
            select(RunModel)
            .where(
                RunModel.thread_id == thread_id,
                or_(
                    RunModel.branch_id == selected,
                    and_(
                        RunModel.branch_id.in_(branch_ids),
                        RunModel.user_message_id.in_(path_ids),
                        or_(
                            RunModel.assistant_message_id.is_(None),
                            RunModel.assistant_message_id.in_(path_ids),
                        ),
                    ),
                ),
                or_(
                    RunModel.user_message_id.in_(visible_ids),
                    RunModel.assistant_message_id.in_(visible_ids),
                    RunModel.run_id.in_([identity for identity in (active, recent) if identity]),
                ),
            )
            .order_by(RunModel.created_at.desc(), RunModel.run_id.desc())
        )
    ).all()
    summaries = [
        {
            name: getattr(run, name)
            for name in (
                "run_id",
                "branch_id",
                "user_message_id",
                "assistant_message_id",
                "parent_run_id",
                "operation_kind",
                "execution_schema_version",
                "status",
                "created_at",
            )
        }
        for run in runs
    ]
    messages = [
        {
            **{
                name: getattr(message, name)
                for name in (
                    "message_id",
                    "thread_id",
                    "branch_id",
                    "seq",
                    "role",
                    "source",
                    "content",
                    "status",
                    "run_id",
                    "created_at",
                )
            },
            "citations": message.citations_json or [],
        }
        for message in rows
    ]
    return utc_projection(
        {
            "thread": await thread_summary(session, thread),
            "branch": asdict(chain[-1]),
            "branch_path": [asdict(branch) for branch in chain],
            "messages": messages,
            "runs": summaries,
            "active_run_id": active,
            "recent_run_id": recent,
            "next_before_seq": page[0].seq if more else None,
            "has_more": more,
        }
    )
