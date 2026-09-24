"""
Registry of e-signature providers. Which one is active is controlled by
utilities.config.SIGNATURE_PROVIDER (env var), or passed explicitly (e.g.
to re-select the provider a specific lease's signature was started with,
stored as Lease.esign_provider) -- lease/views.py never imports a
concrete provider class directly.

To add a new provider: implement lease.esign.base.SignatureProvider in a
new module here, then add one line to _PROVIDERS below.
"""
from utilities import config
from .base import SignatureProvider
from .uaepass import UaePassSignatureProvider

_PROVIDERS: dict[str, type[SignatureProvider]] = {
    "uaepass": UaePassSignatureProvider,
}


def get_signature_provider(name: str | None = None) -> SignatureProvider:
    key = (name or config.SIGNATURE_PROVIDER or "uaepass").lower()
    provider_cls = _PROVIDERS.get(key)
    if not provider_cls:
        raise ValueError(f"Unknown signature provider: {key!r}. Registered: {list(_PROVIDERS)}")
    return provider_cls()


def register_provider(key: str, provider_cls: type[SignatureProvider]) -> None:
    """Alternative to editing _PROVIDERS directly -- a new provider module
    can call this from its own import if preferred."""
    _PROVIDERS[key.lower()] = provider_cls
