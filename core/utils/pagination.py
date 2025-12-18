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
