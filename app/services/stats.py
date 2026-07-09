"""Live per-room booking statistics derived directly from the database."""
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..models import Booking


def get(room_id: int, db: Session | None = None) -> dict:
    if db is None:
        return {"count": 0, "revenue": 0}
    row = (
        db.query(func.count(Booking.id), func.coalesce(func.sum(Booking.price_cents), 0))
        .filter(Booking.room_id == room_id, Booking.status == "confirmed")
        .one()
    )
    return {"count": row[0], "revenue": row[1]}


# Keep these as no-ops so call sites don't need to change.
def record_create(room_id: int, price_cents: int) -> None:
    pass


def record_cancel(room_id: int, price_cents: int) -> None:
    pass
