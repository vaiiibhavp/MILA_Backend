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
