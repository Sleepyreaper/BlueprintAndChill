from __future__ import annotations

from fastapi import Depends, HTTPException, status

from blueprintandchill.auth.entra import EntraAuthService, EntraUser
from blueprintandchill.config import Settings, get_settings


def get_auth_service(settings: Settings = Depends(get_settings)) -> EntraAuthService:
    return EntraAuthService(settings)


def get_current_user(auth_service: EntraAuthService = Depends(get_auth_service)) -> EntraUser:
    # TODO: Replace demo principal resolution with session or bearer-token based authentication.
    return auth_service.get_demo_user()


def require_role(required_role: str):
    def _dependency(user: EntraUser = Depends(get_current_user)) -> EntraUser:
        if required_role not in user.roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Missing required role: {required_role}",
            )
        return user

    return _dependency
