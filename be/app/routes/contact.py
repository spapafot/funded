from datetime import datetime, timezone
from uuid import uuid4

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr

from app.config import settings
from app.db import get_table
from app.keys import contact_pk, CONTACT_SK

router = APIRouter(prefix="/contact", tags=["contact"])

TURNSTILE_VERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"


class ContactInput(BaseModel):
    name: str
    email: EmailStr
    subject: str
    message: str
    turnstile_token: str


async def _verify_turnstile(token: str) -> bool:
    async with httpx.AsyncClient() as client:
        r = await client.post(
            TURNSTILE_VERIFY_URL,
            data={"secret": settings.turnstile_secret_key, "response": token},
        )
    return r.json().get("success", False)


@router.post("")
async def submit_contact(body: ContactInput):
    if not await _verify_turnstile(body.turnstile_token):
        raise HTTPException(
            status_code=400,
            detail={"code": "BAD_REQUEST", "message": "Bot verification failed. Please try again."},
        )

    contact_id = str(uuid4())
    now = datetime.now(timezone.utc).isoformat()

    get_table().put_item(Item={
        "PK": contact_pk(contact_id),
        "SK": CONTACT_SK,
        "contactId": contact_id,
        "name": body.name,
        "email": body.email,
        "subject": body.subject,
        "message": body.message,
        "createdAt": now,
        "status": "new",
    })

    return {"ok": True}
