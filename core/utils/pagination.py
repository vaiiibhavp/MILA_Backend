from fastapi import Query
from pydantic import BaseModel

# class for StandardResultsSetPagination
class StandardResultsSetPagination(BaseModel):
    page: int = 1
    page_size: int = 10

    @property
    def skip(self) -> int:
        return (self.page - 1) * self.page_size

    @property
    def limit(self) -> int:
        return self.page_size

# To use the pagination class in the endpoint
def pagination_params(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100)) -> StandardResultsSetPagination:
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

    return [{
        "records": records,
        "pagination": {
            "page": page,
            "page_size": page_size,
            "total_records": total_records,
            "total_pages": total_pages,
            "has_next": page < total_pages,
            "has_previous": page > 1
        }
    }]

