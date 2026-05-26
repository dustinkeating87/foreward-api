import re
from datetime import date, datetime, time
from typing import Optional
from pydantic import BaseModel, EmailStr, model_validator

_TIME_RE = re.compile(r"^\d{2}:\d{2}$")


class SignupRequest(BaseModel):
    email: EmailStr
    password: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class AlertProfileCreate(BaseModel):
    course: Optional[str] = None   # singular accepted from frontend
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

    @model_validator(mode="after")
    def coerce_course_to_courses(self):
        if self.course and not self.courses:
            self.courses = [self.course]
        return self

    @model_validator(mode="after")
    def validate_dates_and_times(self):
        today = date.today()

        for field_name, val in [("time_from", self.time_from), ("time_to", self.time_to)]:
            if not _TIME_RE.match(val):
                raise ValueError(f"{field_name} must be in HH:MM format (e.g. 08:00)")
            try:
                datetime.strptime(val, "%H:%M")
            except ValueError:
                raise ValueError(f"{field_name} must be in HH:MM format (e.g. 08:00)")

        if self.date_to < self.date_from:
            raise ValueError("End date must be on or after start date")

        if self.date_to < today:
            raise ValueError("End date is in the past; this alert could never fire")

        if self.time_from >= self.time_to:
            raise ValueError("Start time must be before end time")

        return self


class AlertProfileUpdate(BaseModel):
    course: Optional[str] = None   # singular accepted from frontend
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

    @model_validator(mode="after")
    def coerce_course_to_courses(self):
        if self.course and self.courses is None:
            self.courses = [self.course]
        return self


class SignupFreeTierRequest(BaseModel):
    email: EmailStr
    password: str
    phone_e164: str
    verification_token: str


class CheckoutSessionRequest(BaseModel):
    # Optional: client can pass a customer email override; falls back to auth user email
    email: Optional[EmailStr] = None
