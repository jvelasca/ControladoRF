"""Tests contacto / feedback mailto."""
from core.app_contact import (
    build_feedback_mailto_url,
    format_app_support_emails,
    get_app_support_email,
    get_app_support_emails,
)


def test_support_email_from_resource():
    email = get_app_support_email()
    assert "@" in email
    assert "." in email.split("@")[-1]


def test_support_emails_primary_contact():
    emails = get_app_support_emails()
    assert len(emails) >= 1
    assert emails[0] == "josealberto.vel@gmail.com"


def test_format_app_support_emails():
    text = format_app_support_emails()
    assert "@" in text
    assert "josealberto.vel@gmail.com" in text


def test_build_feedback_mailto_url():
    url = build_feedback_mailto_url(body="Hola", subject="Test")
    assert url.startswith("mailto:")
    assert "Hola" in url or "Hola" in url.replace("%20", " ")
    assert "josealberto.vel@gmail.com" in url or "josealberto.vel%40gmail.com" in url
