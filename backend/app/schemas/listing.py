from datetime import datetime
from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


class ListingSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str | None
    price: int | None
    price_status: str
    area: float | None
    rooms: int | None
    floor: int | None

    bedrooms: int | None
    open_kitchen: bool | None
    layout_confidence: str
    layout_source: str

    city: str | None
    district: str | None
    market: str
    source_url: str


class ListingDetail(ListingSummary):
    description: str
    source: str
    created_at: datetime


class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int = Field(description="number of compliant ofers")
    page: int
    page_size: int
    pages: int = Field(description="number of pages for a given page_size")