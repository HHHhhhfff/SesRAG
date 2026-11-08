"""导出严格v3 Schema；前端继续只从contracts生成类型。"""

import json
from datetime import datetime
from pathlib import Path
from typing import Literal, Union

from pydantic import Field, RootModel, create_model

from backend.api.schemas.v2.runs import RunOperationCreate
from backend.api.schemas.v2.threads import MessageRunResponse
from backend.api.schemas.v3 import StrictModel
from backend.api.schemas.v3.context import ContextPlan, ContextResponse
from backend.api.schemas.v3.documents import (
    BuildCreate,
    ChunkList,
    Document,
    DocumentList,
    DocumentPatch,
    IndexBuild,
)
from backend.api.schemas.v3.events import EVENT_DATA_V2, EVENT_DATA_V3, LEGACY_EVENT_DATA
from backend.api.schemas.v3.knowledge_bases import (
    KnowledgeBase,
    KnowledgeBaseCreate,
    KnowledgeBaseList,
    KnowledgeBasePatch,
)
from backend.api.schemas.v3.profiles import RagProfile, RagProfileList
from backend.api.schemas.v3.retrieval import DiagnosticCreate, EvidenceBundle, RetrievalExecution
from backend.api.schemas.v3.sessions import (
    CitationV2,
    Message,
    MessageCreate,
    RunDetail,
    ThreadDetail,
)
from backend.domain.rag_snapshot import FrozenRetrievalConfig, SearchToolInput, SearchToolResult


def wire_catalog():
    # 生成明确的版本+事件类型联合；不能把运行时dict校验器导出成任意object。
    variants = []
    for version, mapping in ((1, LEGACY_EVENT_DATA), (2, EVENT_DATA_V2), (3, EVENT_DATA_V3)):
        for kind, payload in mapping.items():
            variants.append(
                create_model(
                    f"EventV{version}{kind.replace('.', '_').title().replace('_', '')}",
                    __base__=StrictModel,
                    schema_version=(Literal[version], ...),
                    event_id=(str, ...),
                    run_id=(str, ...),
                    seq=(int, Field(ge=1)),
                    type=(Literal[kind], ...),
                    occurred_at=(datetime, ...),
                    data=(payload, ...),
                )
            )
    event = Union[tuple(variants)]
    event_list = create_model(
        "EventList",
        __base__=StrictModel,
        events=(list[event], Field(max_length=1000)),
        next_after_seq=(int, Field(ge=0)),
        has_more=(bool, ...),
    )
    models = [
        KnowledgeBase,
        KnowledgeBaseCreate,
        KnowledgeBasePatch,
        KnowledgeBaseList,
        Document,
        BuildCreate,
        DocumentPatch,
        DocumentList,
        IndexBuild,
        ChunkList,
        RagProfileList,
        DiagnosticCreate,
        RetrievalExecution,
        EvidenceBundle,
        MessageCreate,
        RunDetail,
        ThreadDetail,
        ContextResponse,
        RunOperationCreate,
        MessageRunResponse,
    ]
    return create_model(
        "RagApiCatalog",
        __base__=StrictModel,
        **{model.__name__: (model, ...) for model in models},
        event=(event, ...),
        event_list=(event_list, ...),
    )


class RagToolDefinition(StrictModel):
    name: Literal["rag.search"] = "rag.search"
    version: Literal[1] = 1
    readonly: Literal[True] = True
    max_calls_per_generation: Literal[1] = 1
    input_contract: Literal["tool_rag_search_input_v1.json"] = "tool_rag_search_input_v1.json"
    result_contract: Literal["tool_rag_search_result_v2.json"] = "tool_rag_search_result_v2.json"


SCHEMAS = {
    "knowledge_base_v3.json": KnowledgeBase,
    "document_v3.json": Document,
    "index_build_v3.json": IndexBuild,
    "rag_profile_v3.json": RagProfile,
    "retrieval_v3.json": RetrievalExecution,
    "evidence_v2.json": EvidenceBundle,
    "api_responses_v3.json": wire_catalog(),
    "message_v3.json": Message,
    "run_v3.json": RunDetail,
    "citation_v2.json": CitationV2,
    "context_plan_v3.json": ContextPlan,
    "run_event_v3.json": create_model(
        "RunEventSchema",
        __base__=RootModel,
        root=(wire_catalog().model_fields["event"].annotation, ...),
    ),
    "tool_v1.json": RagToolDefinition,
    "rag_binding_v3.json": FrozenRetrievalConfig,
    "tool_rag_search_input_v1.json": SearchToolInput,
    "tool_rag_search_result_v2.json": SearchToolResult,
}


def export(*, check=False):
    root = Path(__file__).resolve().parents[2] / "contracts"
    for filename, model in SCHEMAS.items():
        schema = model.model_json_schema()
        schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
        schema["$id"] = f"https://sesrag.local/contracts/{filename}"
        value = json.dumps(schema, ensure_ascii=False, indent=2) + "\n"
        path = root / filename
        if check:
            if path.read_text(encoding="utf-8") != value:
                raise RuntimeError(f"契约漂移：{filename}")
        else:
            path.write_text(value, encoding="utf-8")


if __name__ == "__main__":
    import sys

    export(check="--check" in sys.argv)
