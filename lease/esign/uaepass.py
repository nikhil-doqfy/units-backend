"""
UAE PASS eSignSP digital-signature provider -- applies a real PAdES digital
signature to the document (not just an authentication event standing in
for one).

Docs: https://docs.uaepass.ae/feature-guides/signature-integration-guide/digital-signature-single-document
Flow: get a service-level access token (client_credentials, a signature-
service client_id/secret separate from a plain OAuth login app) -> upload
the PDF to create a signer process -> redirect the signer's browser to the
returned URL to authenticate and approve -> poll for the result -> fetch
the signed PDF.

The "process" JSON body matches UAE PASS's "PDF Document Signing Guide"
v2.0 and its sample Postman collection. Not yet exercised against a live
UAE PASS environment -- needs issued client credentials.
"""
import json
import logging

import requests
from django.core.cache import cache

from utilities import config
from .base import SignatureProvider, SignProcess

logger = logging.getLogger(__name__)

_TOKEN_CACHE_KEY = "uaepass_sign_access_token"


class UaePassSignatureProvider(SignatureProvider):
    name = "uaepass"

    def _get_access_token(self) -> str:
        cached = cache.get(_TOKEN_CACHE_KEY)
        if cached:
            return cached

        response = requests.post(
            config.UAE_PASS_SIGN_TOKEN_URL,
            auth=(config.UAE_PASS_SIGN_CLIENT_ID, config.UAE_PASS_SIGN_CLIENT_SECRET),
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            data={"grant_type": "client_credentials", "scope": config.UAE_PASS_SIGN_SCOPE},
            timeout=15,
        )
        response.raise_for_status()
        payload = response.json()
        token = payload["access_token"]
        # Valid ~5 minutes (expires_in: 300 per the guide); cache a little under that so
        # concurrent signature requests reuse it instead of re-fetching.
        cache.set(_TOKEN_CACHE_KEY, token, timeout=max(payload.get("expires_in", 300) - 30, 30))
        return token

    def create_sign_process(self, *, pdf_bytes, filename, callback_url, ui_locale="en") -> SignProcess:
        token = self._get_access_token()
        # Shape follows the UAE PASS "PDF Document Signing Guide" v2.0 and
        # its Postman collection: signature_field lives under
        # signer.parameters, with page/rectangle wrapped in "location".
        process = {
            "process_type": "urn:safelayer:eidas:processes:document:sign:esigp",
            "labels": [["digitalid", "server", config.UAE_PASS_SIGN_LEVEL]],
            "signer": {
                "signature_policy_id": config.UAE_PASS_SIGN_POLICY_ID,
                "parameters": {
                    "type": config.UAE_PASS_SIGN_TYPE,
                    "signature_field": {
                        "name": "Sign1",
                        "location": {
                            "page": {"number": "last"},
                            "rectangle": {"x": 100, "y": 110, "height": 150, "width": 400},
                        },
                        "appearance": {
                            "signature_details": {
                                "details": [
                                    {"type": "subject", "title": "Signer Name: "},
                                    {"type": "date", "title": "Signature Date: "},
                                ]
                            }
                        },
                    },
                },
            },
            "ui_locales": ["en_US" if ui_locale == "en" else "ar_AE"],
            "finish_callback_url": callback_url,
            "views": {
                "document_agreement": {"skip_server_id": config.UAE_PASS_SIGN_SKIP_SERVER_ID},
            },
        }
        if config.UAE_PASS_SIGN_TIMESTAMP:
            process["timestamp"] = {"provider_id": "urn:uae:tws:generation:policy:digitalid"}
        files = {
            "process": (None, json.dumps(process), "application/json"),
            "document": (filename, pdf_bytes, "application/pdf"),
        }
        response = requests.post(
            f"{config.UAE_PASS_SIGN_RESOURCE_URL}/signer_processes",
            headers={"Authorization": f"Bearer {token}"},
            files=files,
            timeout=30,
        )
        response.raise_for_status()
        body = response.json()
        redirect_url = body["tasks"]["pending"][0]["url"]
        document_url = body["documents"][0]["url"]
        document_ref = document_url.rstrip("/").split("/")[-1]
        return SignProcess(process_id=body["id"], document_ref=document_ref, redirect_url=redirect_url)

    def get_result_status(self, process_id: str) -> str:
        token = self._get_access_token()
        response = requests.get(
            f"{config.UAE_PASS_SIGN_RESOURCE_URL}/signer_processes/{process_id}/result",
            headers={"Authorization": f"Bearer {token}"},
            timeout=15,
        )
        # UAE PASS answers 404 SignerProcessResultNotAvailableException
        # until the signer has finished (or canceled) in its UI.
        if response.status_code == 404 and "ResultNotAvailable" in response.text:
            return "pending"
        response.raise_for_status()
        return response.json().get("status", "pending")

    def fetch_signed_document(self, document_ref: str) -> bytes:
        token = self._get_access_token()
        response = requests.get(
            f"{config.UAE_PASS_SIGN_RESOURCE_URL}/documents/{document_ref}/content",
            headers={"Authorization": f"Bearer {token}"},
            timeout=30,
        )
        response.raise_for_status()
        return response.content

    def cleanup(self, process_id: str) -> None:
        try:
            token = self._get_access_token()
            requests.delete(
                f"{config.UAE_PASS_SIGN_RESOURCE_URL}/signer_processes/{process_id}/",
                headers={"Authorization": f"Bearer {token}"},
                timeout=15,
            )
        except Exception:
            logger.exception("UAE_PASS_SIGN_CLEANUP_FAILED | process_id=%s", process_id)
