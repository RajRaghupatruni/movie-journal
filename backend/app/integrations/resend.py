"""Small Resend adapter. Credentials stay in backend settings."""

from __future__ import annotations

import httpx

from app.core.config import Settings


class EmailDeliveryError(RuntimeError):
    def __init__(self, message: str, *, transient: bool):
        super().__init__(message)
        self.transient = transient


class ResendEmailAdapter:
    def __init__(self, settings: Settings):
        self.api_key = (
            settings.resend_api_key.get_secret_value() if settings.resend_api_key else None
        )
        self.from_address = settings.resend_from_address
        self.timeout = settings.provider_timeout_seconds

    def send(self, *, recipient: str, subject: str, html: str, text: str) -> str:
        if not self.api_key or not self.from_address:
            raise EmailDeliveryError("Resend is not configured", transient=False)
        try:
            response = httpx.post(
                "https://api.resend.com/emails",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={
                    "from": self.from_address,
                    "to": [recipient],
                    "subject": subject,
                    "html": html,
                    "text": text,
                },
                timeout=self.timeout,
            )
        except (httpx.TimeoutException, httpx.NetworkError) as exc:
            raise EmailDeliveryError("Resend network failure", transient=True) from exc
        if response.is_success:
            return str(response.json().get("id", "unknown"))
        raise EmailDeliveryError(
            f"Resend returned HTTP {response.status_code}",
            transient=response.status_code >= 500 or response.status_code == 429,
        )
