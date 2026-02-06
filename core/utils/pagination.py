from fastapi import Query
from pydantic import BaseModel
from typing import Optional

# class for StandardResultsSetPagination
class StandardResultsSetPagination(BaseModel):
    page: Optional[int] = None
    page_size: Optional[int] = None

    @property
    def skip(self) -> int:
        if self.page is None or self.page_size is None:
            return 0
        return (self.page - 1) * self.page_size

    @property
    def limit(self) -> Optional[int]:
        return self.page_size

# To use the pagination class in the endpoint
def pagination_params(
    page: Optional[int] = Query(None, ge=1),
    page_size: Optional[int] = Query(None, ge=1, le=100),
) -> StandardResultsSetPagination:
    return StandardResultsSetPagination(
        page=page,
        page_size=page_size
    )

def build_paginated_response(
    records: list,
    page: int,
    page_size: int,
    total_records: int
) -> list:
    """
    Build a standardized paginated response.
    """

    total_pages = (
        (total_records + page_size - 1) // page_size
        if page_size > 0 else 0
    )

    return {
        "records": records,
        "pagination": {
            "page": page,
            "page_size": page_size,
            "total_records": total_records,
            "total_pages": total_pages,
            "has_next": page < total_pages,
            "has_previous": page > 1
        }
    }

