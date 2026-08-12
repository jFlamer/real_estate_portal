from datetime import datetime
from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


class ListingSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    transaction_type: str
    title: str | None
    price: int | None
    price_status: str
    # building/admin fee as stated in the listing; null means the listing is silent
    monthly_fee: int | None
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
    # URLs point at the portal's own CDN — we link photos, we do not rehost them
    image_urls: list[str] = []
    source_url: str


class ListingDetail(ListingSummary):
    description: str
    source: str
    latitude: float | None
    longitude: float | None
    created_at: datetime


class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int = Field(description="number of compliant ofers")
    page: int
    page_size: int
    pages: int = Field(description="number of pages for a given page_size")