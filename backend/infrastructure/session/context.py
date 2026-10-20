"""按 Branch 路径批量加载有界 Message 正文。"""

from sqlalchemy import select

from backend.db.models import ConversationSummaryModel, MessageModel, RunModel
from backend.domain.ports.session import ContextMessage, ConversationSummaryRecord


class SQLContextRepository:
    def __init__(self, session):
        self.session = session

    async def get_candidate_messages(
        self, thread_id: str, message_ids: list[str]
    ) -> list[ContextMessage]:
        if not message_ids:
            return []
        rows = (
            await self.session.execute(
                select(MessageModel, RunModel.user_message_id, RunModel.status)
                .outerjoin(RunModel, MessageModel.run_id == RunModel.run_id)
                .where(
                    MessageModel.thread_id == thread_id, MessageModel.message_id.in_(message_ids)
                )
            )
        ).all()
        by_id = {
            message.message_id: ContextMessage(
                message.message_id,
                message.seq,
                message.role,
                message.content,
                message.status,
                message.run_id,
                input_id,
                run_status,
            )
            for message, input_id, run_status in rows
        }
        return [by_id[identity] for identity in message_ids if identity in by_id]

    async def find_reusable_summary(
        self, thread_id: str, branch_id: str, source_hash: str, policy_version: str
    ) -> ConversationSummaryRecord | None:
        row = await self.session.scalar(
            select(ConversationSummaryModel)
            .where(
                ConversationSummaryModel.thread_id == thread_id,
                ConversationSummaryModel.branch_id == branch_id,
                ConversationSummaryModel.source_hash == source_hash,
                ConversationSummaryModel.summary_policy_version == policy_version,
            )
            .order_by(
                ConversationSummaryModel.created_at.desc(), ConversationSummaryModel.summary_id
            )
            .limit(1)
        )
        if row is None:
            return None
        return ConversationSummaryRecord(
            row.summary_id,
            row.thread_id,
            row.branch_id,
            tuple(row.covered_message_ids),
            row.from_seq,
            row.to_seq,
            row.source_hash,
            tuple(row.source_segments),
            row.summary_text,
            row.summary_policy_version,
            row.source_run_id,
        )
