"""
Signed state token carrying (lease_id, provider, role) through a signer's
browser redirect round-trip -- there's no server-side session to rely on
since the provider calls the finish-callback directly, unauthenticated.
Shared by every provider's callback wiring in lease/views.py, so it lives
here rather than inside a specific provider module.
"""
from django.core import signing

_STATE_SALT = "lease.esign.signature"


def sign_state(lease_id, provider: str, role: str) -> str:
    return signing.TimestampSigner(salt=_STATE_SALT).sign(f"{lease_id}:{provider}:{role}")


def verify_state(state: str, max_age_seconds=1800):
    """Returns (lease_id, provider, role), or (None, None, None) if state
    is missing, tampered with, or older than max_age_seconds (default 30
    minutes -- generous, since signing in the provider's UI can take a
    while)."""
    if not state:
        return None, None, None
    try:
        value = signing.TimestampSigner(salt=_STATE_SALT).unsign(state, max_age=max_age_seconds)
        lease_id, provider, role = value.split(":", 2)
        return lease_id, provider, role
    except (signing.BadSignature, ValueError):
        return None, None, None
