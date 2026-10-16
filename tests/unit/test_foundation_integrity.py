from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.db.base import Base
from backend.db.models import MessageModel, TaskModel, ThreadModel


def test_message_idempotency_is_unique_only_within_one_thread():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        session.add_all([ThreadModel(thread_id=t, owner_id="owner") for t in ["a", "b"]])
        session.flush()
        session.add_all(
            [
                MessageModel(
                    message_id=t,
                    thread_id=t,
                    seq=1,
                    role="user",
                    content="question",
                    idempotency_key="same-key",
                )
                for t in ["a", "b"]
            ]
        )
        session.commit()
        session.add(
            MessageModel(
                message_id="duplicate",
                thread_id="a",
                seq=2,
                role="user",
                content="question",
                idempotency_key="same-key",
            )
        )
        with pytest.raises(IntegrityError):
            session.commit()


def test_assistant_is_unique_per_run_but_user_can_share_run_id():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(ThreadModel(thread_id="thread", owner_id="owner"))
        session.flush()
        for seq, role in [(1, "user"), (2, "assistant")]:
            session.add(
                MessageModel(
                    message_id=str(seq),
                    thread_id="thread",
                    seq=seq,
                    role=role,
                    content="text",
                    run_id="run",
                )
            )
        session.commit()
        session.add(
            MessageModel(
                message_id="duplicate",
                thread_id="thread",
                seq=3,
                role="assistant",
                content="text",
                run_id="run",
            )
        )
        with pytest.raises(IntegrityError):
            session.commit()


@pytest.mark.parametrize(
    "kind,run_id,document_id",
    [
        ("run", None, None),
        ("run", "run", "doc"),
        ("index_document", None, None),
        ("index_document", "run", "doc"),
        ("other", None, "doc"),
    ],
)
def test_task_target_check_rejects_invalid_fact(kind, run_id, document_id):
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(
            TaskModel(
                task_id="task",
                kind=kind,
                run_id=run_id,
                document_id=document_id,
                state="queued",
                deadline_at=datetime.now(timezone.utc),
            )
        )
        with pytest.raises(IntegrityError):
            session.commit()
