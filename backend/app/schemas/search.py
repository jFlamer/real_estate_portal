from typing import Literal

from pydantic import BaseModel, Field, model_validator

SortOption = Literal["newest", "price_asc", "price_desc", "area_asc", "area_desc"]


class SearchFilters(BaseModel):
    q: str | None = Field(default=None, max_length=200, description="phrase in title or description")

    city: str | None = Field(default=None, max_length=128)
    district: str | None = Field(default=None, max_length=128)

    price_min: int | None = Field(default=None, ge=0)
    price_max: int | None = Field(default=None, ge=0)
    area_min: float | None = Field(default=None, ge=0)
    area_max: float | None = Field(default=None, ge=0)

    rooms_min: int | None = Field(default=None, ge=0, le=20)
    bedrooms_min: int | None = Field(default=None, ge=0, le=10)
    open_kitchen: bool | None = None

    market: Literal["primary", "secondary", "unknown"] | None = None

    sort: SortOption = "newest"
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)

    @model_validator(mode="after")
    def check_ranges(self) -> "SearchFilters":
        if self.price_min is not None and self.price_max is not None and self.price_min > self.price_max:
            raise ValueError("price_min cannot be greater than price_max")
        if self.area_min is not None and self.area_max is not None and self.area_min > self.area_max:
            raise ValueError("area_min annot be greater than area_max")
        return self