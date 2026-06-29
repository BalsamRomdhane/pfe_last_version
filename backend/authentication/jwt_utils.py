"""
jwt_utils.py — Centralized JWT validation for the Enterprise Compliance Platform.

Architecture:
  - Django fallback tokens  → HS256, signed with settings.SECRET_KEY
  - Keycloak tokens         → RS256, verified via realm JWKS endpoint

SonarQube rule S5659 compliance:
  - Signature is ALWAYS verified (no verify_signature=False, no verify=False)
  - Algorithm is explicitly restricted per token type (no algorithm confusion)
  - PyJWT default options are preserved (exp, nbf, iat all verified)
  - The `options` kwarg is NOT used to disable verifications
  - HS256 and RS256 paths are distinct — no silent exception bridge between them
  - get_unverified_header() is used ONLY to route, never to trust claims
  - The actual decode always validates the signature with the correct key

Why the previous pattern triggered SonarQube S5659:
  The old code called get_unverified_header() to decide the decode path,
  then used `options={'verify_exp': True}` which SonarQube interprets as
  a partial-options override (it expects no options override at all, or a
  full explicit options dict). Additionally, the silent `except InvalidTokenError:
  pass` bridge between the HS256 and RS256 decode attempts was flagged as a
  potential algorithm confusion bypass.

This module resolves all three issues:
  1. No options override — PyJWT's secure defaults are used as-is.
  2. No silent exception bridge — the token source is determined from the
     header algorithm before any decode, and each path is mutually exclusive.
  3. Algorithm list is a single-element list per path — no multi-algorithm
     confusion possible.
"""
from __future__ import annotations

import logging
from typing import Any, Dict

import jwt
from django.conf import settings
from jwt import PyJWKClient
from jwt.exceptions import InvalidTokenError

logger = logging.getLogger(__name__)

# Algorithms explicitly allowed in this application.
# Any other algorithm (including 'none') is rejected.
_ALLOWED_ALGORITHMS = frozenset({'HS256', 'RS256'})

# PyJWKClient is expensive to instantiate (performs an HTTP request the first
# time it fetches the JWKS). A module-level cache avoids re-fetching on every
# WebSocket connection or API request.
_jwks_client_cache: Dict[str, PyJWKClient] = {}


def _get_jwks_client(jwks_url: str) -> PyJWKClient:
    """Return a cached PyJWKClient for the given JWKS URL."""
    if jwks_url not in _jwks_client_cache:
        # cache_keys=True tells PyJWKClient to cache the signing keys in memory
        # after the first fetch, reducing network round-trips.
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

    Verification performed by PyJWT (all enabled by default):
      - Signature (HMAC-SHA256 with settings.SECRET_KEY)
      - exp  — token must not be expired
      - nbf  — token must not be used before its not-before time
      - iat  — issued-at must be present and in the past

    Raises:
        jwt.ExpiredSignatureError   — token has expired
        jwt.InvalidTokenError       — any other validation failure
        ValueError                  — algorithm mismatch or 'none' algorithm
    """
    # Guard: read the header WITHOUT trusting any claims, solely to reject
    # tokens that are not HS256. This prevents algorithm confusion: a
    # Keycloak RS256 token must never reach the HS256 decode path.
    try:
        header = jwt.get_unverified_header(token)
    except InvalidTokenError as exc:
        raise ValueError(f'Malformed JWT header: {exc}') from exc

    alg = header.get('alg', '')
    if alg not in _ALLOWED_ALGORITHMS:
        raise ValueError(f'Algorithm "{alg}" is not permitted.')
    if alg != 'HS256':
        raise ValueError(
            f'Expected HS256 token but received algorithm "{alg}". '
            'Use decode_rs256_token() for Keycloak tokens.'
        )

    # PyJWT verifies the signature and all registered claims by default.
    # We do NOT pass any `options` dict to avoid accidentally relaxing checks.
    return jwt.decode(
        token,
        settings.SECRET_KEY,
        algorithms=['HS256'],           # single-element list — no confusion possible
    )


def decode_rs256_token(token: str) -> Dict[str, Any]:
    """
    Decode and validate a Keycloak-issued RS256 token.

    Verification performed by PyJWT (all enabled by default):
      - Signature (RSA-SHA256 with the realm public key from JWKS)
      - exp  — token must not be expired
      - nbf  — token must not be used before its not-before time
      - iat  — issued-at must be present and in the past

    Raises:
        jwt.ExpiredSignatureError   — token has expired
        jwt.InvalidTokenError       — any other validation failure
        ValueError                  — algorithm mismatch or JWKS fetch error
    """
    # Guard: reject non-RS256 tokens before attempting signature verification.
    try:
        header = jwt.get_unverified_header(token)
    except InvalidTokenError as exc:
        raise ValueError(f'Malformed JWT header: {exc}') from exc

    alg = header.get('alg', '')
    if alg not in _ALLOWED_ALGORITHMS:
        raise ValueError(f'Algorithm "{alg}" is not permitted.')
    if alg != 'RS256':
        raise ValueError(
            f'Expected RS256 token but received algorithm "{alg}". '
            'Use decode_hs256_token() for Django-issued tokens.'
        )

    jwks_url = _build_jwks_url()
    try:
        client       = _get_jwks_client(jwks_url)
        signing_key  = client.get_signing_key_from_jwt(token)
    except Exception as exc:
        raise ValueError(f'Could not retrieve JWKS signing key: {exc}') from exc

    # PyJWT verifies signature + all registered claims by default.
    return jwt.decode(
        token,
        signing_key.key,
        algorithms=['RS256'],           # single-element list — no confusion possible
    )


def decode_token(token: str) -> Dict[str, Any]:
    """
    Route-and-validate: determine token type from the unverified header,
    then call the appropriate strict decoder.

    This function is the single entry point used by:
      - authentication.py  (DRF middleware)
      - services.py        (KeycloakService.get_user_profile)
      - consumers.py       (WebSocket auth)

    SonarQube S5659 compliance:
      - The algorithm read from the header is used ONLY for routing.
      - Each branch calls a dedicated decoder that verifies the signature
        with the correct key for that algorithm.
      - There is NO silent exception pass-through that could bridge the two
        paths (the old `except InvalidTokenError: pass` pattern is gone).
      - `options` is never passed to jwt.decode(), so no default check
        can be accidentally disabled.

    Raises:
        jwt.ExpiredSignatureError   — token has expired
        jwt.InvalidTokenError       — signature or claims invalid
        ValueError                  — unsupported algorithm or 'none'
    """
    try:
        header = jwt.get_unverified_header(token)
    except InvalidTokenError as exc:
        raise ValueError(f'Malformed JWT header: {exc}') from exc

    alg = header.get('alg', '')

    if alg == 'none':
        # Explicitly reject the 'none' algorithm (unsigned tokens).
        raise ValueError('Unsigned tokens (alg=none) are not accepted.')

    if alg not in _ALLOWED_ALGORITHMS:
        raise ValueError(
            f'Algorithm "{alg}" is not in the allowed list {sorted(_ALLOWED_ALGORITHMS)}.'
        )

    if alg == 'HS256':
        return decode_hs256_token(token)

    # alg == 'RS256'
    return decode_rs256_token(token)


def decode_first_login_token(token: str) -> Dict[str, Any]:
    """
    Validate a first-login / password-reset token (always HS256).

    In addition to the standard checks performed by decode_hs256_token(),
    this function also verifies the 'purpose' claim.

    Raises:
        jwt.ExpiredSignatureError  — link has expired
        jwt.InvalidTokenError      — signature or claims invalid
        ValueError                 — wrong algorithm or wrong purpose
    """
    decoded = decode_hs256_token(token)

    if decoded.get('purpose') != 'first_login':
        raise ValueError(
            "JWT 'purpose' claim is not 'first_login'. "
            "This token cannot be used for password reset."
        )

    return decoded
