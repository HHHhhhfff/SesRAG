from enum import StrEnum


class RunState(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    RETRY_WAITING = "retry_waiting"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskState(StrEnum):
    QUEUED = "queued"
    LEASED = "leased"
    RUNNING = "running"
    RETRY_WAITING = "retry_waiting"
    WAITING_EXTERNAL = "waiting_external"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskKind(StrEnum):
    RUN = "run"
    INDEX_DOCUMENT = "index_document"
    INDEX_BUILD = "index_build"
    RETRIEVAL_DIAGNOSTIC = "retrieval_diagnostic"


class DocumentState(StrEnum):
    UPLOADED = "uploaded"
    INDEXING = "indexing"
    INDEXED = "indexed"
    FAILED = "failed"


class MessageRole(StrEnum):
    USER = "user"
    ASSISTANT = "assistant"


class MessageStatus(StrEnum):
    COMPLETED = "completed"
    GENERATING = "generating"
