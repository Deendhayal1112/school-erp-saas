"""
Tests for API Response Envelopes.
"""

from app.common.responses import (
    CreatedResponse,
    DeletedResponse,
    PaginatedResponse,
    PaginationMetadata,
    SuccessResponse,
)


def test_standard_response_envelopes():
    # SuccessResponse
    succ = SuccessResponse(data={"key": "val"}, message="Success!")
    assert succ.success is True
    assert succ.message == "Success!"
    assert succ.data == {"key": "val"}

    # CreatedResponse
    created = CreatedResponse(data={"id": 1})
    assert created.success is True
    assert "created" in created.message

    # DeletedResponse
    deleted = DeletedResponse()
    assert deleted.success is True
    assert "deleted" in deleted.message

    # PaginatedResponse
    meta = PaginationMetadata(
        total_records=100,
        page=2,
        page_size=10,
        total_pages=10,
        next="http://testserver/api/v1/items?page=3",
        previous="http://testserver/api/v1/items?page=1",
    )
    paginated = PaginatedResponse(
        pagination=meta,
        results=[{"id": 1}, {"id": 2}],
    )
    assert paginated.success is True
    assert len(paginated.results) == 2
    assert paginated.pagination.total_records == 100
