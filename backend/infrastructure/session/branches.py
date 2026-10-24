from sqlalchemy import and_, or_, select

from backend.db.models import BranchModel, MessageModel
from backend.domain.ports.session import BranchRecord, PathMessage


class SQLBranchRepository:
    def __init__(self, session):
        self.session = session

    async def list_branches(self, thread_id):
        rows = (
            await self.session.scalars(
                select(BranchModel)
                .where(BranchModel.thread_id == thread_id)
                .order_by(BranchModel.created_at, BranchModel.branch_id)
            )
        ).all()
        return [
            BranchRecord(**{name: getattr(row, name) for name in BranchRecord.__dataclass_fields__})
            for row in rows
        ]

    async def get_messages(self, thread_id, message_ids):
        rows = (
            await self.session.execute(
                select(
                    MessageModel.message_id,
                    MessageModel.thread_id,
                    MessageModel.branch_id,
                    MessageModel.seq,
                    MessageModel.role,
                ).where(
                    MessageModel.thread_id == thread_id, MessageModel.message_id.in_(message_ids)
                )
            )
        ).all()
        return [PathMessage(*row) for row in rows]

    @staticmethod
    def path_condition(thread_id, segments):
        return and_(
            MessageModel.thread_id == thread_id,
            or_(
                *[
                    and_(
                        MessageModel.branch_id == part.branch_id,
                        MessageModel.seq <= part.through_seq,
                    )
                    if part.through_seq is not None
                    else MessageModel.branch_id == part.branch_id
                    for part in segments
                ]
            ),
        )

    async def list_path_messages(
        self, thread_id, segments, *, before_seq=None, limit=None, message_id=None
    ):
        statement = select(
            MessageModel.message_id,
            MessageModel.thread_id,
            MessageModel.branch_id,
            MessageModel.seq,
            MessageModel.role,
        ).where(self.path_condition(thread_id, segments))
        if before_seq is not None:
            statement = statement.where(MessageModel.seq < before_seq)
        if message_id is not None:
            statement = statement.where(MessageModel.message_id == message_id)
        statement = statement.order_by(MessageModel.seq.desc())
        if limit is not None:
            statement = statement.limit(limit)
        rows = list(reversed((await self.session.execute(statement)).all()))
        return [PathMessage(*row) for row in rows]

    async def lock_branches(self, thread_id, branch_ids):
        return (
            await self.session.scalars(
                select(BranchModel)
                .where(BranchModel.thread_id == thread_id, BranchModel.branch_id.in_(branch_ids))
                .order_by(BranchModel.branch_id)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
        ).all()
