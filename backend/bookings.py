"""Booking a provider for a specific slot, with a frozen verification snapshot."""
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from auth import CurrentUser
from database import get_db
from matching import profile_competencies
from models import AvailabilitySlot, Booking, BookingStatus, Competency, Provider, ProviderType
from schemas import BookingIn, BookingOut, SnapshotProvider
from snapshots import build_snapshot

router = APIRouter(tags=["bookings"])

ALREADY_BOOKED = "Sorry, that slot is already booked. Please choose another time."


@router.post("/bookings", response_model=BookingOut, status_code=201)
def create_booking(body: BookingIn, user: CurrentUser, db: Session = Depends(get_db)):
    """Book the provider's slot that covers `requested_time`.

    Double-booking is prevented twice over: the slot's row is locked
    (SELECT ... FOR UPDATE) while we check for an existing booking and create
    ours, so a simultaneous request for the same slot waits and then sees it's
    taken; and bookings.slot_id is unique, so the database refuses a second
    booking even if the check were somehow bypassed.
    """
    provider = db.get(Provider, body.provider_id)
    if provider is None:
        raise HTTPException(status_code=404, detail="Provider not found")
    if provider.provider_type is ProviderType.driver and not (body.dropoff or "").strip():
        raise HTTPException(status_code=422, detail="Please give a drop-off address for a trip with a driver.")

    slot = db.scalar(
        select(AvailabilitySlot)
        .where(
            AvailabilitySlot.provider_id == provider.id,
            AvailabilitySlot.starts_at <= body.requested_time,
            AvailabilitySlot.ends_at > body.requested_time,
        )
        .with_for_update()
    )
    if slot is None:
        raise HTTPException(
            status_code=409,
            detail=f"{provider.name} isn't available at that time. Please choose one of their available slots.",
        )
    if slot.starts_at <= datetime.now(UTC):
        raise HTTPException(status_code=409, detail="That slot has already started. Please choose a later one.")
    if db.scalar(select(Booking.id).where(Booking.slot_id == slot.id)):
        raise HTTPException(status_code=409, detail=ALREADY_BOOKED)

    relevant = (
        set(profile_competencies(user.profile, provider.provider_type)) if user.profile else set()
    )
    snapshot = build_snapshot(
        provider=SnapshotProvider(
            id=provider.id,
            name=provider.name,
            provider_type=provider.provider_type,
            location=provider.location,
        ),
        competencies=[(c.code, c.label) for c in provider.competencies],
        latest=provider.verifications[-1] if provider.verifications else None,
        relevant=relevant,
        labels={c.code: c.label for c in db.scalars(select(Competency))},
        captured_at=datetime.now(UTC),
    )
    booking = Booking(
        user_id=user.id,
        provider_id=provider.id,
        slot_id=slot.id,
        starts_at=slot.starts_at,
        ends_at=slot.ends_at,
        pickup=body.pickup.strip(),
        dropoff=(body.dropoff or "").strip() or None,
        notes=(body.notes or "").strip() or None,
        verification_snapshot=snapshot.model_dump(mode="json"),
    )
    db.add(booking)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail=ALREADY_BOOKED) from None
    db.refresh(booking)
    return booking


@router.get("/bookings", response_model=list[BookingOut])
def my_bookings(user: CurrentUser, db: Session = Depends(get_db)):
    """The logged-in user's bookings, soonest first."""
    return db.scalars(
        select(Booking).where(Booking.user_id == user.id).order_by(Booking.starts_at)
    ).all()


@router.get("/bookings/{booking_id}", response_model=BookingOut)
def get_booking(booking_id: int, user: CurrentUser, db: Session = Depends(get_db)):
    """One of the logged-in user's bookings. Other people's bookings are a 404."""
    booking = db.get(Booking, booking_id)
    if booking is None or booking.user_id != user.id:
        raise HTTPException(status_code=404, detail="Booking not found")
    return booking


@router.post("/bookings/{booking_id}/cancel", response_model=BookingOut)
def cancel_booking(booking_id: int, user: CurrentUser, db: Session = Depends(get_db)):
    """Cancel one of the logged-in user's bookings before it starts.

    The booking and its verification snapshot are kept, marked cancelled; the
    slot is released (slot_id cleared) so someone else can book that time.
    """
    booking = db.scalar(select(Booking).where(Booking.id == booking_id).with_for_update())
    if booking is None or booking.user_id != user.id:
        raise HTTPException(status_code=404, detail="Booking not found")
    if booking.status is BookingStatus.cancelled:
        raise HTTPException(status_code=409, detail="This booking is already cancelled.")
    if booking.starts_at <= datetime.now(UTC):
        raise HTTPException(
            status_code=409, detail="This booking has already started, so it can't be cancelled here."
        )
    booking.status = BookingStatus.cancelled
    booking.cancelled_at = datetime.now(UTC)
    booking.slot_id = None
    db.commit()
    db.refresh(booking)
    return booking
