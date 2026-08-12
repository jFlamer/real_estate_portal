from datetime import datetime

from sqlalchemy import (
    DECIMAL,
    JSON,
    Boolean,
    DateTime,
    Enum,
    Index,
    Integer,
    SmallInteger,
    String,
    Text,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Listing(Base):
    __tablename__ = 'listings'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    source: Mapped[str] = mapped_column(String(64))
    source_url: Mapped[str] = mapped_column(String(512), unique=True)

    transaction_type: Mapped[str] = mapped_column(
        Enum("sale", "rent", name="transaction_type"), default="sale"
    )

    title: Mapped[str | None] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text)

    price: Mapped[int | None] = mapped_column(Integer)
    price_status: Mapped[str] = mapped_column(
        Enum("fixed", "negotiable", "unknown", name="price_status"), default="unknown"
    )
    # opłata administracyjna podana w opisie; NULL = ogłoszenie o niej milczy
    # i wtedy mówimy o tym wprost, zamiast zgadywać
    monthly_fee: Mapped[int | None] = mapped_column(Integer)

    area: Mapped[float | None] = mapped_column(DECIMAL(6, 1))
    rooms: Mapped[int | None] = mapped_column(SmallInteger)
    floor: Mapped[int | None] = mapped_column(SmallInteger)

    bedrooms: Mapped[int | None] = mapped_column(SmallInteger)
    open_kitchen: Mapped[bool | None] = mapped_column(Boolean)
    layout_confidence: Mapped[str] = mapped_column(
        Enum("high", "low", name="layout_confidence"), default="low"
    )
    layout_source: Mapped[str] = mapped_column(
        Enum("llm", "heuristic", name="layout_source"), default="heuristic"
    )

    city: Mapped[str | None] = mapped_column(String(128))
    district: Mapped[str | None] = mapped_column(String(128))
    market: Mapped[str] = mapped_column(
        Enum("primary", "secondary", "unknown", name="market"), default="unknown"
    )

    # zdjęcia i współrzędne pochodzą wprost z ld+json portalu — trzymamy URL-e,
    # nie kopie plików: to nie nasze treści i nie chcemy ich hostować
    image_urls: Mapped[list | None] = mapped_column(JSON)
    latitude: Mapped[float | None] = mapped_column(DECIMAL(9, 6))
    longitude: Mapped[float | None] = mapped_column(DECIMAL(9, 6))

    dedup_hash: Mapped[str] = mapped_column(String(64))
    raw_json: Mapped[dict] = mapped_column(JSON)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        Index("ix_listings_city_price", "transaction_type", "city", "price"),
        Index("ix_listings_area", "area"),
        Index("ix_listings_bedrooms", "bedrooms"),
        Index("ix_listings_dedup_hash", "dedup_hash"),
    )

    def __repr__(self) -> str:
        return f"<Listing {self.id} {self.transaction_type} {self.city} {self.area}m2 {self.price}pln>"