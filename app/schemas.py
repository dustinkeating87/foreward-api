from datetime import date, time
from typing import Optional
from pydantic import BaseModel, EmailStr


class SignupRequest(BaseModel):
    email: EmailStr
    password: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class AlertProfileCreate(BaseModel):
    courses: list[str] = []
    date_from: date
    date_to: date
    time_from: str  # "HH:MM"
    time_to: str    # "HH:MM"
    players: int
    holes: int
    notify_email: Optional[str] = None
    notify_phone: Optional[str] = None
    active: bool = True


class AlertProfileUpdate(BaseModel):
    courses: Optional[list[str]] = None
    date_from: Optional[date] = None
    date_to: Optional[date] = None
    time_from: Optional[str] = None
    time_to: Optional[str] = None
    players: Optional[int] = None
    holes: Optional[int] = None
    notify_email: Optional[str] = None
    notify_phone: Optional[str] = None
    active: Optional[bool] = None


class CheckoutSessionRequest(BaseModel):
    # Optional: client can pass a customer email override; falls back to auth user email
    email: Optional[EmailStr] = None
