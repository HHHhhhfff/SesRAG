import pytest
from sqlalchemy import event, select

from backend.api.schemas.v2.threads import BranchCreate, ThreadDetailQuery
from backend.application.branches import create_branch, default_branch, resolve_path
from backend.application.errors import ApplicationError
from backend.application.session_operations import request_hash
from backend.application.session_threads import session_thread_detail
from backend.application.threads import create_message_run, create_thread
from backend.config import Settings
from backend.db.base import Base
from backend.db.models import BranchModel, MessageModel, ThreadModel
from backend.db.session import create_engine, create_session_factory
from backend.infrastructure.session.branches import SQLBranchRepository


@pytest.fixture
async def session_db(tmp_path):
    settings = Settings(
        database_url=f"sqlite+aiosqlite:///{tmp_path / 'paths.db'}", redis_enabled=False
    )
    engine = create_engine(settings)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    async with create_session_factory(engine)() as session:
        yield settings, session
    await engine.dispose()


async def test_nested_fork_truncates_ancestry_without_copy_and_rejects_invisible_fork(session_db):
    settings, session = session_db
    thread = await create_thread(session, settings, "paths")
    tid = thread.thread_id
    first, run, _, _ = await create_message_run(session, settings, tid, "first", None)
    run.status = "cancelled"
    await session.commit()
    root = await default_branch(session, tid)
    second, run, _, _ = await create_message_run(session, settings, tid, "second", None)
    run.status = "cancelled"
    await session.commit()
    child, _ = await create_branch(
        session,
        settings,
        tid,
        BranchCreate(parent_branch_id=root.branch_id, fork_message_id=first.message_id),
        "child",
    )
    # 子分支事实的 seq 延续 Thread；不复制祖先，也不包含父分支后续。
    session.add(
        MessageModel(
            message_id="child-message",
            thread_id=tid,
            branch_id=child.branch_id,
            seq=3,
            role="user",
            source="user_input",
            content="child",
        )
    )
    thread.next_message_seq = 3
    child.head_message_id = "child-message"
    child.version = 1
    await session.commit()
    grandchild, _ = await create_branch(
        session,
        settings,
        tid,
        BranchCreate(parent_branch_id=child.branch_id, fork_message_id="child-message"),
        "grandchild",
    )
    chain, path = await resolve_path(SQLBranchRepository(session), tid, grandchild.branch_id)
    assert [m.message_id for m in path] == [first.message_id, "child-message"]
    assert len(chain) == 3
    assert len((await session.scalars(select(MessageModel))).all()) == 3
    with pytest.raises(ApplicationError) as error:
        await create_branch(
            session,
            settings,
            tid,
            BranchCreate(parent_branch_id=child.branch_id, fork_message_id=second.message_id),
            "invisible",
        )
    assert error.value.code == "INVALID_BRANCH_PATH" and error.value.status_code == 422
    await session.rollback()


async def test_branch_limits_and_cycles_are_bounded(session_db):
    settings, session = session_db
    thread = await create_thread(session, settings, "limits")
    tid = thread.thread_id
    message, run, _, _ = await create_message_run(session, settings, tid, "fork", None)
    run.status = "cancelled"
    await session.commit()
    root = await default_branch(session, tid)
    message_id = message.message_id
    parent = root.branch_id
    for index in range(31):
        branch, _ = await create_branch(
            session,
            settings,
            tid,
            BranchCreate(parent_branch_id=parent, fork_message_id=message.message_id),
            str(index),
        )
        parent = branch.branch_id
    with pytest.raises(ApplicationError) as error:
        await create_branch(
            session,
            settings,
            tid,
            BranchCreate(parent_branch_id=parent, fork_message_id=message.message_id),
            "depth",
        )
    assert error.value.code == "BRANCH_LIMIT_EXCEEDED"
    await session.rollback()
    # 损坏数据的环也必须有界失败，不能无限递归。
    root = await default_branch(session, tid)
    root.parent_branch_id = parent
    root.fork_message_id = message_id
    await session.commit()
    with pytest.raises(ApplicationError) as error:
        await resolve_path(SQLBranchRepository(session), tid, parent)
    assert error.value.code == "INVALID_BRANCH_PATH"


async def test_hundred_branch_limit_rolls_back_and_other_thread_is_404(session_db):
    settings, session = session_db
    thread = await create_thread(session, settings, "limits")
    tid = thread.thread_id
    message, run, _, _ = await create_message_run(session, settings, tid, "fork", None)
    run.status = "cancelled"
    await session.commit()
    root = await default_branch(session, tid)
    root_id, message_id = root.branch_id, message.message_id
    for index in range(99):
        session.add(
            BranchModel(
                branch_id=f"branch-{index}",
                thread_id=tid,
                parent_branch_id=root_id,
                fork_message_id=message_id,
                head_message_id=message_id,
                name="sibling",
                is_default=False,
                version=0,
            )
        )
    await session.commit()
    with pytest.raises(ApplicationError) as error:
        await create_branch(
            session,
            settings,
            tid,
            BranchCreate(parent_branch_id=root_id, fork_message_id=message_id),
            "overflow",
        )
    assert error.value.code == "BRANCH_LIMIT_EXCEEDED"
    await session.rollback()
    assert (await session.get(ThreadModel, tid)).conversation_version == 1
    other = await create_thread(session, settings, "other")
    with pytest.raises(ApplicationError) as error:
        await create_branch(
            session,
            settings,
            other.thread_id,
            BranchCreate(parent_branch_id=root_id, fork_message_id=message_id),
            "foreign",
        )
    assert error.value.status_code == 404


def test_request_hash_preserves_omission_identity_and_operation_kind():
    omitted = request_hash(
        "message",
        {"branch_id": "b", "content": "hello"},
        ("model_profile_id", "model_profile_version"),
    )
    assert omitted == request_hash(
        "message",
        {"content": "hello", "branch_id": "b"},
        ("model_profile_version", "model_profile_id"),
    )
    assert omitted != request_hash(
        "message",
        {
            "branch_id": "b",
            "content": "hello",
            "model_profile_id": "mock-default",
            "model_profile_version": 1,
        },
        ("model_profile_id", "model_profile_version"),
    )

    assert omitted != request_hash(
        "regenerate",
        {"branch_id": "b", "content": "hello"},
        ("model_profile_id", "model_profile_version"),
    )


async def test_detail_reads_bounded_page_instead_of_materializing_history(session_db):
    settings, session = session_db
    thread = await create_thread(session, settings, "bounded")
    tid = thread.thread_id
    branch = await default_branch(session, tid)
    for seq in range(1, 31):
        session.add(
            MessageModel(
                message_id=str(seq),
                thread_id=tid,
                branch_id=branch.branch_id,
                seq=seq,
                role="user",
                source="user_input",
                content=f"fact {seq}",
            )
        )
    thread.next_message_seq = 30
    branch.head_message_id = "30"
    branch.version = 30
    await session.commit()
    session.expunge_all()
    loaded = []

    def track(_session, instance):
        if isinstance(instance, MessageModel):
            loaded.append(instance.message_id)

    event.listen(session.sync_session, "loaded_as_persistent", track)
    detail = await session_thread_detail(session, settings, tid, ThreadDetailQuery(limit=2))
    assert [message["message_id"] for message in detail["messages"]] == ["29", "30"]
    assert len(loaded) <= 3
