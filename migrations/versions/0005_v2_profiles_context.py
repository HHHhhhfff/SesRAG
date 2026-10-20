"""版本化模型元数据与只读上下文事实表。"""

import sqlalchemy as sa
from alembic import op

from migrations.v2_session_checks import guard_downgrade

revision = "0005_v2_profiles_context"
down_revision = "0004_v2_session_branches"
branch_labels = None
depends_on = None


def upgrade():
    profiles = op.create_table(
        "model_profiles",
        sa.Column("profile_id", sa.String(36), primary_key=True),
        sa.Column("version", sa.Integer(), primary_key=True),
        sa.Column("display_name", sa.String(200), nullable=False),
        sa.Column("provider_kind", sa.String(40), nullable=False),
        sa.Column("model_name", sa.String(200), nullable=False),
        sa.Column("generation_params", sa.JSON(), nullable=False),
        sa.Column("base_url", sa.String(500)),
        sa.Column("context_window_tokens", sa.Integer(), nullable=False),
        sa.Column("max_output_tokens", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("is_default", sa.Boolean(), nullable=False),
        sa.Column("tokenizer_kind", sa.String(40), nullable=False),
        sa.Column("tokenizer_version", sa.String(40), nullable=False),
        sa.Column("tokenizer_config", sa.JSON(), nullable=False),
        sa.Column("config_ref", sa.String(120)),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.current_timestamp(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.current_timestamp(),
        ),
        sa.CheckConstraint(
            "version>0 AND context_window_tokens>0 AND max_output_tokens>0",
            name="ck_model_profiles_budgets",
        ),
        sa.CheckConstraint("status IN ('enabled','disabled')", name="ck_model_profiles_status"),
        sa.CheckConstraint(
            "NOT is_default OR status='enabled'", name="ck_model_profiles_default_enabled"
        ),
    )
    op.create_index(
        "uq_model_profiles_default",
        "model_profiles",
        ["is_default"],
        unique=True,
        postgresql_where=sa.text("is_default"),
        sqlite_where=sa.text("is_default"),
    )
    op.bulk_insert(
        profiles,
        [
            dict(
                profile_id=pid,
                version=1,
                display_name=name,
                provider_kind="mock",
                model_name="mock",
                generation_params={},
                base_url=None,
                context_window_tokens=window,
                max_output_tokens=output,
                status="enabled",
                is_default=default,
                tokenizer_kind="mock",
                tokenizer_version="1",
                tokenizer_config={"safety_margin_tokens": 128, "summary_max_tokens": 512},
                config_ref=None,
            )
            for pid, name, window, output, default in (
                ("mock-default", "Mock 普通上下文", 8192, 1024, True),
                ("mock-small", "Mock 小上下文", 2048, 256, False),
            )
        ],
    )
    op.create_table(
        "context_plans",
        sa.Column("context_plan_id", sa.String(36), primary_key=True),
        sa.Column("run_id", sa.String(36), sa.ForeignKey("runs.run_id"), nullable=False),
        sa.Column("task_id", sa.String(36), sa.ForeignKey("tasks.task_id"), nullable=False),
        sa.Column("generation", sa.Integer(), nullable=False),
        sa.Column("attempt", sa.Integer(), nullable=False),
        sa.Column("thread_id", sa.String(36), sa.ForeignKey("threads.thread_id"), nullable=False),
        sa.Column("branch_id", sa.String(36), sa.ForeignKey("branches.branch_id"), nullable=False),
        sa.Column(
            "anchor_message_id", sa.String(36), sa.ForeignKey("messages.message_id"), nullable=False
        ),
        *[
            sa.Column(name, sa.JSON(), nullable=False)
            for name in (
                "selected_message_ids",
                "omitted_messages",
                "omitted_ranges",
                "summary_ids",
                "selected_evidence",
            )
        ],
        sa.Column("trim_policy_version", sa.String(40), nullable=False),
        sa.Column("counter_version", sa.String(40), nullable=False),
        *[
            sa.Column(name, sa.Integer(), nullable=False)
            for name in (
                "estimated_input_tokens",
                "reserved_output_tokens",
                "safety_margin_tokens",
                "context_window_tokens",
            )
        ],
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("task_id", "generation", name="uq_context_plans_task_generation"),
    )
    op.create_index("ix_context_plans_run_id", "context_plans", ["run_id"])
    op.create_table(
        "conversation_summaries",
        sa.Column("summary_id", sa.String(36), primary_key=True),
        sa.Column("thread_id", sa.String(36), sa.ForeignKey("threads.thread_id"), nullable=False),
        sa.Column("branch_id", sa.String(36), sa.ForeignKey("branches.branch_id"), nullable=False),
        sa.Column("covered_message_ids", sa.JSON(), nullable=False),
        sa.Column("from_seq", sa.Integer(), nullable=False),
        sa.Column("to_seq", sa.Integer(), nullable=False),
        sa.Column("source_hash", sa.String(64), nullable=False),
        sa.Column("source_segments", sa.JSON(), nullable=False),
        sa.Column("summary_text", sa.Text(), nullable=False),
        sa.Column("summary_policy_version", sa.String(40), nullable=False),
        sa.Column("source_run_id", sa.String(36), sa.ForeignKey("runs.run_id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_conversation_summaries_thread_id", "conversation_summaries", ["thread_id"])
    op.create_index("ix_conversation_summaries_branch_id", "conversation_summaries", ["branch_id"])
    with op.batch_alter_table("runs") as batch:
        batch.add_column(sa.Column("context_plan_id", sa.String(36)))
        batch.add_column(sa.Column("model_profile_id", sa.String(36)))
        batch.add_column(sa.Column("model_profile_version", sa.Integer()))
        batch.create_foreign_key(
            "fk_runs_context_plan", "context_plans", ["context_plan_id"], ["context_plan_id"]
        )
        batch.create_foreign_key(
            "fk_runs_model_profile",
            "model_profiles",
            ["model_profile_id", "model_profile_version"],
            ["profile_id", "version"],
        )


def downgrade():
    guard_downgrade(op.get_bind())
    with op.batch_alter_table("runs") as batch:
        batch.drop_constraint("fk_runs_context_plan", type_="foreignkey")
        batch.drop_constraint("fk_runs_model_profile", type_="foreignkey")
        for column in ("context_plan_id", "model_profile_id", "model_profile_version"):
            batch.drop_column(column)
    op.drop_table("conversation_summaries")
    op.drop_table("context_plans")
    op.drop_table("model_profiles")
