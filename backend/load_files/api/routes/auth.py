import requests
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from load_files.config.settings import settings

router = APIRouter(tags=["auth"])

class LoginRequest(BaseModel):
    username: str
    password: str

class LoginResponse(BaseModel):
    access_token: str
    expires_in: int

@router.post("/login", response_model=LoginResponse)
def login(body: LoginRequest):
    token_url = f"{settings.KEYCLOAK_URL}/realms/{settings.KEYCLOAK_REALM}/protocol/openid-connect/token"
    resp = requests.post(token_url, data={
        "client_id": settings.KEYCLOAK_CLIENT_ID,
        "username": body.username,
        "password": body.password,
        "grant_type": "password",
    }, timeout=15)
    if not resp.ok:
        detail = resp.json().get("error_description", "Credenciales invalidas")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=detail)
    data = resp.json()
    return LoginResponse(access_token=data["access_token"], expires_in=data["expires_in"])
