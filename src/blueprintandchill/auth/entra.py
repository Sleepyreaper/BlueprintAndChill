from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from blueprintandchill.config import Settings


@dataclass(slots=True)
class EntraUser:
    subject: str
    display_name: str
    email: str | None
    roles: list[str]
    claims: dict[str, Any]


class EntraAuthService:
    """Framework service for future Microsoft Entra ID integration.

    TODO:
    - integrate MSAL/Authlib/OpenID Connect flow
    - validate ID/access tokens against tenant metadata
    - map app roles / group membership to local authorization roles
    - replace placeholder user with signed-in principal context
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    @property
    def configured(self) -> bool:
        return self._settings.is_entra_configured

    def get_login_url(self) -> str | None:
        if not self.configured:
            return None

        # TODO: Build a real OIDC authorization URL using tenant metadata, nonce, state,
        # and the configured redirect URI.
        authority = self._settings.entra_authority.rstrip("/")
        return f"{authority}/{self._settings.entra_tenant_id}/oauth2/v2.0/authorize"

    def get_demo_user(self) -> EntraUser:
        return EntraUser(
            subject="demo-user",
            display_name="Demo Requester",
            email="demo.requester@example.invalid",
            roles=["requester"],
            claims={"auth_mode": "demo", "configured": self.configured},
        )
