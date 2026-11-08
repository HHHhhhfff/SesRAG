# SesRAG 合成验收资料

## Database
SesRAG stores execution facts in PostgreSQL and vectors in pgvector.

## Notification
Redis only provides notifications and short lived cache.

## Local text
TXT and Markdown are parsed locally without MinerU.

## Office
Office originals are sent to MinerU only after consent for each operation.

## Publishing
A candidate index becomes active only after all stages succeed.

## Failure
A failed rebuild preserves the previous active batch.

## Snapshot
Each new Run freezes its retrieval view and model configuration.

## Retry
An automatic retry keeps the same Run and user Message.

## Worker
Every task write requires task id, worker id and generation.

## Citation
Citations refer only to evidence selected into the actual context.

## Rerank
Dense similarity and reranker relevance scores are recorded separately.

## Neighbor
Neighbor expansion stays inside the same document and index batch.

## Unknown
An unknown remote submission is not automatically submitted again.

## Cancel
Local cancellation cannot guarantee remote cancellation or refund.

## Limits
A source file must not exceed ten mebibytes.

## Scope
One retrieval selects exactly one owned knowledge base.

## Token
API credentials must never appear in public events or messages.

## Events
Events use increasing sequence numbers within each Run.

## Empty
An empty scope is a successful empty search, not a service failure.

## Fallback
Office parser failures never fall back to a local parser.

| Item | Value |
| --- | --- |
| Vector dimension | 1024 |
