from jose import jwt
from jose.exceptions import JWTError
import requests
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from load_files.config.settings import settings
from load_files.utils.logger import logger

security = HTTPBearer()
_jwks_cache: dict | None = None

def _get_jwks() -> dict:
    global _jwks_cache
    if _jwks_cache is None:
        logger.debug("Fetching JWKS from %s", settings.KEYCLOAK_JWKS_URL)
        try:
            response = requests.get(settings.KEYCLOAK_JWKS_URL, timeout=10)
            response.raise_for_status()
            _jwks_cache = response.json()
        except requests.RequestException as e:
            logger.error("Keycloak unavailable: %s", e)
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Keycloak unavailable")
    return _jwks_cache

def verify_token(token: str) -> dict | None:
    try:
        header = jwt.get_unverified_header(token)
        jwks = _get_jwks()
        rsa_key = None
        for key in jwks["keys"]:
            if key["kid"] == header["kid"]:
                rsa_key = {k: key[k] for k in ("kty", "kid", "use", "n", "e")}
                break
        if not rsa_key:
            logger.warning("No matching RSA key found for kid: %s", header.get("kid"))
            return None
        decode_kwargs = {
            "token": token, "key": rsa_key, "algorithms": ["RS256"],
            "issuer": settings.KEYCLOAK_ISSUER,
            "options": {"verify_exp": True, "verify_iss": False, "verify_aud": settings.KEYCLOAK_VERIFY_AUDIENCE},
        }
        if settings.KEYCLOAK_VERIFY_AUDIENCE:
            decode_kwargs["audience"] = settings.KEYCLOAK_CLIENT_ID
        payload = jwt.decode(**decode_kwargs)
        return payload
    except JWTError as e:
        logger.warning("Token verification failed: %s", e)
        return None

def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    payload = verify_token(credentials.credentials)
    if not payload:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token invalido o expirado")
    return payload

def require_client_role(client_id: str, required_role: str):
    def role_checker(payload: dict = Depends(get_current_user)) -> dict:
        resource_access = payload.get("resource_access", {})
        client_roles = resource_access.get(client_id, {}).get("roles", [])
        if required_role not in client_roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Se requiere el rol '{required_role}' para el cliente '{client_id}'")
        return payload
    return role_checker
