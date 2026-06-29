"""
jwt_utils.py — Centralized JWT validation for the Enterprise Compliance Platform.

Architecture:
  - Keycloak tokens         → RS256, verified via realm JWKS endpoint
  - Django fallback tokens  → HS256, signed with settings.SECRET_KEY

SonarQube S5659 compliance (three-rule surface area):
  1. jwt.decode() is ALWAYS called with an explicit key and algorithm list.
  2. get_unverified_header() is NOT used anywhere in this module — the
     algorithm is determined by the decode attempt itself, not by reading
     unverified header data first (which is what triggers S5659).
  3. The 'none' algorithm is implicitly rejected because neither 'HS256'
     nor 'RS256' algorithm lists include 'none', and PyJWT raises an
     InvalidAlgorithmError for any algorithm not in the supplied list.

Token routing strategy (no get_unverified_header):
  decode_token() tries RS256 first (Keycloak path). If the JWKS key lookup
  fails or the signature is invalid, it falls back to HS256 (Django path).
  Both attempts verify the full signature — there is no partial-verify step.

Why this avoids S5659:
  SonarQube's taint-tracking for S5659 follows the token value from its
  source to a jwt.decode() call. If get_unverified_header() is called on the
  same token before the decode, the taint path is considered "unverified use."
  By removing all get_unverified_header() calls and going straight to
  jwt.decode() with a concrete key, the taint path terminates at the first
  verified decode — satisfying the rule.
"""
from __future__ import annotations

import logging
from typing import Any, Dict

import jwt
from django.conf import settings
from jwt import PyJWKClient
from jwt.exceptions import InvalidTokenError

logger = logging.getLogger(__name__)

# PyJWKClient is expensive to instantiate (performs an HTTP request the first
# time it fetches the JWKS). A module-level cache avoids re-fetching on every
# WebSocket connection or API request.
_jwks_client_cache: Dict[str, PyJWKClient] = {}


def _get_jwks_client(jwks_url: str) -> PyJWKClient:
    """Return a cached PyJWKClient for the given JWKS URL."""
    if jwks_url not in _jwks_client_cache:
        _jwks_client_cache[jwks_url] = PyJWKClient(jwks_url, cache_keys=True)
    return _jwks_client_cache[jwks_url]


def _build_jwks_url() -> str:
    return (
        f"{settings.KEYCLOAK_SERVER_URL.rstrip('/')}/realms/"
        f"{settings.KEYCLOAK_REALM}/protocol/openid-connect/certs"
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def decode_hs256_token(token: str) -> Dict[str, Any]:
    """
    Decode and validate a Django-issued HS256 token.

    PyJWT verifies by default: signature, exp, nbf, iat.
    No `options` override is used — all PyJWT default verifications apply.

    Raises:
        jwt.ExpiredSignatureError  — token has expired
        jwt.InvalidTokenError      — signature or claims invalid
    """
    # jwt.decode() with algorithms=['HS256'] rejects any token whose header
    # algorithm is not HS256 (including 'none'), without needing a prior
    # get_unverified_header() call. Signature is always verified.
    return jwt.decode(
        token,
        settings.SECRET_KEY,
        algorithms=['HS256'],
    )


def decode_rs256_token(token: str) -> Dict[str, Any]:
    """
    Decode and validate a Keycloak-issued RS256 token.

    The signing key is fetched from the realm JWKS endpoint. PyJWT verifies
    signature, exp, nbf and iat. No `options` override is used.

    Raises:
        jwt.ExpiredSignatureError  — token has expired
        jwt.InvalidTokenError      — signature or claims invalid
        ValueError                 — JWKS key retrieval failed
    """
    jwks_url = _build_jwks_url()
    try:
        client      = _get_jwks_client(jwks_url)
        signing_key = client.get_signing_key_from_jwt(token)
    except Exception as exc:
        raise ValueError(f'Could not retrieve JWKS signing key: {exc}') from exc

    # jwt.decode() with algorithms=['RS256'] rejects non-RS256 tokens
    # (including 'none') without any prior header inspection.
    return jwt.decode(
        token,
        signing_key.key,
        algorithms=['RS256'],
    )


def decode_token(token: str) -> Dict[str, Any]:
    """
    Decode and validate a token of either supported type.

    Strategy: attempt RS256 (Keycloak) first; on failure attempt HS256
    (Django fallback). Both paths perform full signature verification via
    jwt.decode() — no get_unverified_header() is called, satisfying S5659.

    This function is the single entry point used by:
      - authentication.py  (DRF authentication middleware)
      - services.py        (KeycloakService.get_user_profile)
      - consumers.py       (WebSocket authentication)

    Raises:
        jwt.ExpiredSignatureError  — token has expired (either path)
        jwt.InvalidTokenError      — both decode attempts failed
    """
    # ── Try RS256 (Keycloak) first ────────────────────────────────────────
    try:
        return decode_rs256_token(token)
    except jwt.ExpiredSignatureError:
        # Token is structurally valid RS256 but expired — surface the error.
        raise
    except Exception:
        # Not a valid RS256 token (wrong algorithm, bad signature, JWKS
        # unreachable) — fall through to the HS256 path.
        pass

    # ── Fall back to HS256 (Django-issued token) ──────────────────────────
    return decode_hs256_token(token)


def decode_first_login_token(token: str) -> Dict[str, Any]:
    """
    Validate a first-login / password-reset token (always HS256).

    Delegates signature validation to decode_hs256_token(), then checks
    the 'purpose' claim to prevent token reuse across contexts.

    Raises:
        jwt.ExpiredSignatureError  — link has expired
        jwt.InvalidTokenError      — signature or claims invalid
        ValueError                 — wrong purpose claim
    """
    decoded = decode_hs256_token(token)

    if decoded.get('purpose') != 'first_login':
        raise ValueError(
            "JWT 'purpose' claim is not 'first_login'. "
            "This token cannot be used for password reset."
        )

    return decoded
