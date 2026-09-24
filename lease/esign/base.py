"""
Common interface every e-signature provider must implement. Adding a new
provider later (DocuSign, Adobe Sign, ...) means writing one class here
that implements SignatureProvider and registering it in factory.py's
_PROVIDERS -- nothing in lease/views.py needs to change, since it only
ever talks to SignatureProvider, never to a concrete provider class.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class SignProcess:
    """Returned by create_sign_process(). process_id/document_ref are
    opaque, provider-specific strings -- callers persist them (on the
    Lease) and pass them back unchanged into get_result_status() /
    fetch_signed_document() once the signer completes the redirect_url
    flow."""
    process_id: str
    document_ref: str
    redirect_url: str


class SignatureProvider(ABC):
    """One instance per signing request. Selected via
    lease.esign.factory.get_signature_provider() -- never instantiated
    directly by calling code."""

    name: str  # short slug (e.g. "uaepass"), stored on the Lease so the
    # correct provider can be re-selected on the callback round-trip.

    @abstractmethod
    def create_sign_process(
        self, *, pdf_bytes: bytes, filename: str, callback_url: str, ui_locale: str = "en",
    ) -> SignProcess:
        """Upload the document and start a signing process. Returns
        identifiers to persist plus the URL to redirect the signer's
        browser to so they can authenticate and approve the signature."""
        raise NotImplementedError

    @abstractmethod
    def get_result_status(self, process_id: str) -> str:
        """Normalized status: 'pending' | 'finished' | 'failed' | 'canceled'."""
        raise NotImplementedError

    @abstractmethod
    def fetch_signed_document(self, document_ref: str) -> bytes:
        """Raw signed PDF bytes, once get_result_status() reports 'finished'."""
        raise NotImplementedError

    def cleanup(self, process_id: str) -> None:
        """Best-effort post-completion cleanup on the provider's side.
        Optional -- default no-op; override only if the provider needs it."""
        pass
