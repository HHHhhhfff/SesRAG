"""COMP_008/012：旧文档保留、ContextPlan/Summary独立回退阻止；正式PG工厂由插件注入。"""

import pytest
from sqlalchemy import inspect, text

from tests.unit.test_foundation_migrations import migrate, migration_engine
from tests.unit.test_v2_session_migrations import seed_run


def test_COMP_008_documents_chunks_roundtrip():
    with migration_engine().begin() as connection:
        migrate(connection, "upgrade", "0003_chunk_locations")
        connection.execute(
            text(
                "INSERT INTO documents (document_id,owner_id,filename,extension,size_bytes,"
                "content_hash,storage_key,status,active_index_batch_id,source,"
                "created_at,updated_at) "
                "VALUES ('doc','owner','synthetic.txt','txt',4,'safe-hash','synthetic-key',"
                "'indexed','batch','local_upload',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"
            )
        )
        connection.execute(
            text(
                "INSERT INTO chunks (chunk_id,document_id,index_batch_id,seq,text,start_offset,"
                "end_offset,locations_json,created_at) VALUES "
                "('chunk','doc','batch',1,'fact',0,4,'[]',CURRENT_TIMESTAMP)"
            )
        )

        def read():
            return {
                table: connection.execute(text(f"SELECT * FROM {table}")).all()
                for table in ["documents", "chunks"]
            }

        before = read()
        for direction, revision in [
            ("upgrade", "head"),
            ("upgrade", "head"),
            ("downgrade", "0003_chunk_locations"),
            ("upgrade", "head"),
        ]:
            migrate(connection, direction, revision)
            assert read() == before


@pytest.mark.parametrize("fact", ["context_plan", "summary", "v2_thread"])
def test_COMP_012_independent_context_facts_guard(fact):
    with migration_engine().begin() as connection:
        migrate(connection, "upgrade", "0003_chunk_locations")
        seed_run(connection, "old", "failed")
        migrate(connection, "upgrade", "head")
        if fact == "v2_thread":
            connection.execute(text("UPDATE threads SET conversation_version=2"))
        elif fact == "summary":
            connection.execute(
                text(
                    "INSERT INTO conversation_summaries "
                    "(summary_id,thread_id,branch_id,covered_message_ids,"
                    "from_seq,to_seq,source_hash,source_segments,summary_text,summary_policy_version,"
                    "source_run_id,created_at) SELECT 'summary',thread_id,branch_id,'[\"m-old\"]',"
                    "1,1,'safe-hash','[]','synthetic','trim_then_extract_v1','old',"
                    "CURRENT_TIMESTAMP FROM branches"
                )
            )
        else:
            connection.execute(
                text(
                    "INSERT INTO context_plans "
                    "(context_plan_id,run_id,task_id,generation,attempt,thread_id,"
                    "branch_id,anchor_message_id,selected_message_ids,omitted_messages,omitted_ranges,"
                    "summary_ids,selected_evidence,trim_policy_version,counter_version,estimated_input_tokens,"
                    "reserved_output_tokens,safety_margin_tokens,context_window_tokens,"
                    "status,created_at) SELECT 'plan','old','t-old',1,1,thread_id,branch_id,"
                    "'m-old','[]','[]','[]','[]','[]','trim_then_extract_v1','mock@1',"
                    "10,1024,128,8192,'ready',CURRENT_TIMESTAMP FROM branches"
                )
            )
        tables = inspect(connection).get_table_names()
        before = {
            table: connection.execute(text(f"SELECT * FROM {table}")).all() for table in tables
        }
        with pytest.raises(RuntimeError, match="V2_BUSINESS_FACTS"):
            migrate(connection, "downgrade", "0003_chunk_locations")
        assert inspect(connection).get_table_names() == tables
        assert {
            table: connection.execute(text(f"SELECT * FROM {table}")).all() for table in tables
        } == before
