from backend.infrastructure.rag.pgvector_store import cosine_similarity


def test_cosine_similarity_orders_matching_vectors():
    assert cosine_similarity([1.0, 0.0], [1.0, 0.0]) > cosine_similarity([1.0, 0.0], [0.0, 1.0])
