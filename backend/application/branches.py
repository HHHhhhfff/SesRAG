"""分支路径和分叉规则；不复制祖先消息。"""

from uuid import uuid4

from sqlalchemy import func, select

from backend.application.errors import ApplicationError
from backend.application.session_operations import record_operation, replay_operation, request_hash
from backend.db.models import BranchModel, MessageModel, RunModel
from backend.domain.ports.session import BranchPath, BranchRecord, BranchRepository, PathSegment
from backend.infrastructure.session.branches import SQLBranchRepository

ACTIVE_RUN_STATES = ("queued", "running", "retry_waiting", "cancelling")
MAX_BRANCHES = 100
MAX_BRANCH_DEPTH = 32


async def resolve_scope(repository: BranchRepository, thread_id: str, branch_id: str):
    branches = {branch.branch_id: branch for branch in await repository.list_branches(thread_id)}
    if branch_id not in branches:
        raise ApplicationError("BRANCH_NOT_FOUND", "Branch 不存在", 404)
    reverse: list[BranchRecord] = []
    seen = set()
    current = branches[branch_id]
    while True:
        if current.branch_id in seen or len(reverse) >= MAX_BRANCH_DEPTH:
            raise ApplicationError("INVALID_BRANCH_PATH", "Branch 路径无效", 422)
        seen.add(current.branch_id)
        reverse.append(current)
        if current.parent_branch_id is None:
            if current.fork_message_id is not None:
                raise ApplicationError("INVALID_BRANCH_PATH", "Branch 路径无效", 422)
            break
        if current.parent_branch_id not in branches or current.fork_message_id is None:
            raise ApplicationError("INVALID_BRANCH_PATH", "Branch 路径无效", 422)
        current = branches[current.parent_branch_id]
    chain = list(reversed(reverse))
    forks = {
        message.message_id: message
        for message in await repository.get_messages(
            thread_id, [branch.fork_message_id for branch in chain if branch.fork_message_id]
        )
    }
    cutoffs: dict[str, int | None] = {}
    for branch in chain:
        if branch.parent_branch_id is not None:
            fork = forks.get(branch.fork_message_id) if branch.fork_message_id else None
            cutoff = cutoffs.get(fork.branch_id) if fork else None
            if (
                fork is None
                or fork.branch_id not in cutoffs
                or (cutoff is not None and fork.seq > cutoff)
            ):
                raise ApplicationError("INVALID_BRANCH_PATH", "分叉消息不在父路径", 422)
            # 后代可再次选祖先锚点；所有较早分支均取有效 fork 上界的交集。
            cutoffs = {
                identity: min(bound, fork.seq) if bound is not None else fork.seq
                for identity, bound in cutoffs.items()
            }
        cutoffs[branch.branch_id] = None
    return BranchPath(
        tuple(chain), tuple(PathSegment(identity, bound) for identity, bound in cutoffs.items())
    )


async def resolve_path(
    repository: BranchRepository, thread_id: str, branch_id: str, *, before_seq=None, limit=None
):
    scope = await resolve_scope(repository, thread_id, branch_id)
    return list(scope.branches), await repository.list_path_messages(
        thread_id, scope.segments, before_seq=before_seq, limit=limit
    )


async def default_branch(session, thread_id):
    return (
        await session.scalars(
            select(BranchModel).where(
                BranchModel.thread_id == thread_id, BranchModel.is_default.is_(True)
            )
        )
    ).one()


async def create_branch(session, settings, thread_id, payload, idempotency_key):
    from backend.application.threads import get_thread, now_utc, upgrade_for_v2_write

    thread = await get_thread(session, settings, thread_id)
    await session.refresh(thread, with_for_update=True)
    digest = request_hash("branch", payload.model_dump(exclude_unset=True), ("name",))
    replay = await replay_operation(session, thread_id, idempotency_key, digest)
    if replay:
        return await session.get(BranchModel, replay.result_branch_id), True
    repository = SQLBranchRepository(session)
    scope = await resolve_scope(repository, thread_id, payload.parent_branch_id)
    chain = scope.branches
    await repository.lock_branches(thread_id, [branch.branch_id for branch in chain])
    if thread.archived_at is not None:
        raise ApplicationError("THREAD_ARCHIVED", "Thread 已归档", 409)
    persisted_fork = await session.get(MessageModel, payload.fork_message_id)
    if persisted_fork is None or persisted_fork.thread_id != thread_id:
        raise ApplicationError("MESSAGE_NOT_FOUND", "分叉消息不存在", 404)
    candidates = await repository.list_path_messages(
        thread_id, scope.segments, message_id=payload.fork_message_id, limit=1
    )
    fork = candidates[0] if candidates else None
    if fork is None:
        raise ApplicationError("INVALID_BRANCH_PATH", "分叉消息不在父路径", 422)
    busy = await session.scalar(
        select(RunModel.run_id).where(
            RunModel.thread_id == thread_id,
            RunModel.user_message_id == fork.message_id,
            RunModel.status.in_(ACTIVE_RUN_STATES),
        )
    )
    if busy:
        raise ApplicationError("INVALID_BRANCH_PATH", "活动 Run 输入不可分叉", 422)
    count = await session.scalar(
        select(func.count()).select_from(BranchModel).where(BranchModel.thread_id == thread_id)
    )
    if count >= MAX_BRANCHES or len(chain) >= MAX_BRANCH_DEPTH:
        raise ApplicationError("BRANCH_LIMIT_EXCEEDED", "Branch 数量或深度已达上限", 422)
    await upgrade_for_v2_write(session, thread)
    branch = BranchModel(
        branch_id=str(uuid4()),
        thread_id=thread_id,
        parent_branch_id=payload.parent_branch_id,
        fork_message_id=fork.message_id,
        name=payload.name or f"分支 {count + 1}",
        is_default=False,
        head_message_id=fork.message_id,
        version=0,
    )
    session.add(branch)
    await session.flush()
    record_operation(
        session, thread_id, idempotency_key, "branch", digest, branch_id=branch.branch_id
    )
    thread.updated_at = now_utc()
    await session.commit()
    return branch, False
