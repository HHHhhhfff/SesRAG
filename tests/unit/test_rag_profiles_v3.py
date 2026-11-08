"""PRD-003：固定路由、不可变空间及向量边界。"""

import math

import pytest

from backend.application.errors import ApplicationError
from backend.application.vector_validation import validate_vector
from backend.domain.rag import EmbeddingSpace, ParseRequest, RetrievalPolicy, parser_for


@pytest.mark.parametrize("extension", [".txt", ".md"])
def test_plain_text_never_selects_cloud(extension):
    assert parser_for(extension) == "local"
    assert ParseRequest().resolve(extension) == "local"
    with pytest.raises(ApplicationError, match="本地"):
        ParseRequest(cloud_consent=True, consent_version="mineru-office-outbound-v1").resolve(
            extension
        )


@pytest.mark.parametrize("extension", [".doc", ".docx", ".pdf", ".xls", ".xlsx", ".ppt", ".pptx"])
def test_office_requires_per_operation_consent_and_has_no_route_override(extension):
    assert parser_for(extension) == "mineru"
    with pytest.raises(ApplicationError) as error:
        ParseRequest().resolve(extension)
    assert error.value.code == "CLOUD_CONSENT_REQUIRED"
    assert (
        ParseRequest(cloud_consent=True, consent_version="mineru-office-outbound-v1").resolve(
            extension
        )
        == "mineru"
    )
    with pytest.raises(ValueError):
        ParseRequest.model_validate({"mode": "local"})


def test_unknown_formats_are_not_provider_capabilities():
    for extension in (".html", ".png", ".docm", ".exe"):
        with pytest.raises(ApplicationError):
            parser_for(extension)


def test_equal_dimensions_do_not_merge_different_model_spaces():
    left = EmbeddingSpace(model="a", revision="r1", dimension=1024)
    assert left.space_id == EmbeddingSpace(model="a", revision="r1", dimension=1024).space_id
    assert left.space_id != EmbeddingSpace(model="b", revision="r1", dimension=1024).space_id
    assert left.space_id != EmbeddingSpace(model="a", revision="r2", dimension=1024).space_id


def test_profile_limits_and_vectors_reject_invalid_values():
    with pytest.raises(ValueError):
        RetrievalPolicy(top_k=21)
    with pytest.raises(ValueError):
        RetrievalPolicy(candidate_k=4, top_k=5)
    assert validate_vector([0.2, 0.3], dimension=2) == [0.2, 0.3]
    for value in ([0, 0], [1, math.nan], [1], [1, math.inf]):
        with pytest.raises(ApplicationError):
            validate_vector(value, dimension=2)


def test_temporary_budget_cannot_admit_zero_worker_capacity():
    import pytest
    from pydantic import ValidationError

    from backend.config import Settings

    with pytest.raises(ValidationError):
        Settings(rag_tmp_budget_bytes=256 * 1024**2, _env_file=None)
