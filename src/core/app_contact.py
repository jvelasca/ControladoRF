"""Contacto de soporte / desarrollador (recursos empaquetados)."""
from __future__ import annotations

import json
import re
from functools import lru_cache
from typing import List

from app_paths import bundle_root

_DEFAULT_SUPPORT_EMAIL = "josealberto.vel@gmail.com"
_DEFAULT_SUPPORT_EMAILS = (_DEFAULT_SUPPORT_EMAIL,)
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _valid_email(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    email = value.strip()
    if not email or not _EMAIL_RE.match(email):
        return None
    return email


def _load_contact_data() -> dict:
    path = bundle_root() / "resources" / "app_contact.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


@lru_cache(maxsize=1)
def get_app_support_emails(
    fallback: tuple[str, ...] = _DEFAULT_SUPPORT_EMAILS,
) -> tuple[str, ...]:
    """Correos de soporte / desarrollador (sin duplicados, orden conservado)."""
    data = _load_contact_data()
    raw_list = data.get("support_emails")
    candidates: List[str] = []
    if isinstance(raw_list, list):
        for item in raw_list:
            email = _valid_email(item)
            if email is not None:
                candidates.append(email)
    primary = _valid_email(data.get("support_email"))
    if primary is not None and primary not in candidates:
        candidates.insert(0, primary)
    if not candidates:
        return fallback
    seen: set[str] = set()
    ordered: List[str] = []
    for email in candidates:
        key = email.casefold()
        if key in seen:
            continue
        seen.add(key)
        ordered.append(email)
    return tuple(ordered)


@lru_cache(maxsize=1)
def get_app_support_email(fallback: str = _DEFAULT_SUPPORT_EMAIL) -> str:
    """Correo principal de la aplicación para reportes y soporte."""
    emails = get_app_support_emails()
    return emails[0] if emails else fallback


def format_app_support_emails() -> str:
    """Texto para mostrar todos los correos de contacto."""
    return ", ".join(get_app_support_emails())


def build_feedback_mailto_url(*, body: str, subject: str) -> str:
    """URL mailto lista para QDesktopServices."""
    from urllib.parse import quote

    recipients = ",".join(get_app_support_emails())
    return (
        f"mailto:{quote(recipients, safe=',@')}"
        f"?subject={quote(subject)}"
        f"&body={quote(body)}"
    )
