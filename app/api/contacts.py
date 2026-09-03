from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.user import User
from app.models.trusted_contact import TrustedContact, ContactStatus
from app.schemas.contact import ContactCreate, ContactUpdate, ContactOut
from app.api.deps import get_current_user
from app.services.email_service import send_email

router = APIRouter(prefix="/api/contacts", tags=["contacts"])


@router.get("", response_model=list[ContactOut])
def list_contacts(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return db.query(TrustedContact).filter(TrustedContact.owner_id == current_user.id).all()


@router.post("", response_model=ContactOut, status_code=201)
def create_contact(payload: ContactCreate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    contact = TrustedContact(owner_id=current_user.id, **payload.model_dump())
    # Auto-link if this email already belongs to a registered SafeHer user.
    if contact.email:
        existing = db.query(User).filter(User.email == contact.email).first()
        if existing:
            contact.linked_user_id = existing.id
            contact.status = ContactStatus.verified
    db.add(contact)
    db.commit()
    db.refresh(contact)
    return contact


@router.put("/{contact_id}", response_model=ContactOut)
def update_contact(contact_id: str, payload: ContactUpdate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    contact = _get_owned(db, contact_id, current_user.id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(contact, field, value)
    db.commit()
    db.refresh(contact)
    return contact


@router.delete("/{contact_id}", status_code=204)
def delete_contact(contact_id: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    contact = _get_owned(db, contact_id, current_user.id)
    db.delete(contact)
    db.commit()


@router.post("/{contact_id}/invite")
async def invite_contact(contact_id: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    contact = _get_owned(db, contact_id, current_user.id)
    if not contact.email:
        raise HTTPException(400, "This contact has no email address to invite.")
    html = (
        f"<p><strong>{current_user.full_name}</strong> added you as a trusted contact on SafeHer AI, "
        "a personal safety app. Register to receive their emergency and journey alerts.</p>"
    )
    await send_email(contact.email, f"{current_user.full_name} invited you to SafeHer AI", html)
    contact.status = ContactStatus.pending
    db.commit()
    return {"message": "Invitation sent."}


def _get_owned(db: Session, contact_id: str, owner_id: str) -> TrustedContact:
    contact = db.get(TrustedContact, contact_id)
    if not contact or contact.owner_id != owner_id:
        raise HTTPException(404, "Contact not found.")
    return contact
