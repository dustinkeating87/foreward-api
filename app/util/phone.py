import hashlib
import re

_E164_RE = re.compile(r"^\+[1-9]\d{7,14}$")


def hash_phone(e164: str) -> str:
    return hashlib.sha256(e164.encode()).hexdigest()


def is_valid_e164(phone: str) -> bool:
    return bool(_E164_RE.match(phone))
