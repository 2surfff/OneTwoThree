import base64
import json
import logging
import os
import time
import urllib.request
from datetime import date
from typing import Any

import jwt
from jwt import PyJWK

from app.ai.agenda import parse_agenda
from app.config import settings

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

_JWKS_CACHE: dict[str, Any] | None = None


def get_cors_headers(origin: str = "*") -> dict[str, str]:
    return {
        "Access-Control-Allow-Origin": origin if origin else "*",
        "Access-Control-Allow-Methods": "POST, OPTIONS",
        "Access-Control-Allow-Headers": "Authorization, Content-Type, Accept, X-Requested-With",
        "Access-Control-Max-Age": "86400",
    }


def get_jwks(region: str, pool_id: str) -> dict[str, Any]:
    global _JWKS_CACHE
    if _JWKS_CACHE is not None:
        return _JWKS_CACHE

    # Check settings first if provided inline
    if settings.cognito_jwks:
        _JWKS_CACHE = json.loads(settings.cognito_jwks)
        return _JWKS_CACHE

    url = f"https://cognito-idp.{region}.amazonaws.com/{pool_id}/.well-known/jwks.json"
    req = urllib.request.Request(url, headers={"User-Agent": "OneTwoThree-Agenda-Lambda/1.0"})
    with urllib.request.urlopen(req, timeout=5) as resp:
        _JWKS_CACHE = json.load(resp)
    return _JWKS_CACHE


def verify_cognito_token(token: str) -> dict[str, Any]:
    """Verify Cognito JWT ID/Access token using public JWKS."""
    pool_id = os.getenv("COGNITO_USER_POOL_ID", settings.cognito_user_pool_id or "eu-north-1_2JHnz3607")
    region = os.getenv("COGNITO_REGION", settings.cognito_region or "eu-north-1")
    client_id = os.getenv("COGNITO_CLIENT_ID", settings.cognito_client_id or "520q7rcdd0c5hf0ahk2adb8bm3")

    if not pool_id:
        # Dev fallback if running without cognito pool
        return {"sub": "local-dev", "email": "dev@localhost"}

    jwks = get_jwks(region, pool_id)
    unverified_header = jwt.get_unverified_header(token)
    kid = unverified_header.get("kid")
    key_dict = next((k for k in jwks.get("keys", []) if k.get("kid") == kid), None)
    if not key_dict:
        raise ValueError(f"Signing key with kid '{kid}' not found in JWKS.")

    public_key = PyJWK(key_dict).key
    issuer = f"https://cognito-idp.{region}.amazonaws.com/{pool_id}"

    decode_options = {
        "verify_signature": True,
        "verify_exp": True,
        "require": ["exp", "sub", "iss"],
    }

    # Audience verification: ID token has aud=client_id, access token has client_id in client_id claim
    claims = jwt.decode(
        token,
        public_key,
        algorithms=["RS256"],
        issuer=issuer,
        options=decode_options,
    )

    if client_id:
        token_aud = claims.get("aud") or claims.get("client_id")
        if token_aud and token_aud != client_id:
            raise ValueError(f"Invalid audience: expected {client_id}, got {token_aud}")

    return claims


def calculate_cost_usd(model_id: str, input_tokens: int, output_tokens: int) -> float:
    """Calculate estimated cost in USD for Bedrock Claude invocation."""
    model_lower = model_id.lower()
    if "haiku-4" in model_lower:
        # Claude Haiku 4.5: $1.00 / 1M input, $5.00 / 1M output
        rate_in = 1.00 / 1_000_000
        rate_out = 5.00 / 1_000_000
    elif "sonnet" in model_lower:
        # Claude 3.5 / 4.5 Sonnet: $3.00 / 1M input, $15.00 / 1M output
        rate_in = 3.00 / 1_000_000
        rate_out = 15.00 / 1_000_000
    elif "haiku-3" in model_lower or "claude-3-haiku" in model_lower:
        # Claude 3 Haiku: $0.25 / 1M input, $1.25 / 1M output
        rate_in = 0.25 / 1_000_000
        rate_out = 1.25 / 1_000_000
    else:
        # Default fallback
        rate_in = 1.00 / 1_000_000
        rate_out = 5.00 / 1_000_000

    return round(input_tokens * rate_in + output_tokens * rate_out, 6)


def handler(event: dict[str, Any], context: Any = None) -> dict[str, Any]:
    """Lambda Function URL handler for Agenda Parsing."""
    headers = event.get("headers") or {}
    # Lowercase header lookup
    normalized_headers = {k.lower(): v for k, v in headers.items()}
    origin = normalized_headers.get("origin", "*")
    cors = get_cors_headers(origin)

    # Handle CORS preflight
    http_method = (
        event.get("requestContext", {}).get("http", {}).get("method") or event.get("httpMethod") or "POST"
    )
    if http_method.upper() == "OPTIONS":
        return {
            "statusCode": 200,
            "headers": cors,
            "body": "",
        }

    # 1. Validate JWT from Authorization: Bearer <token> or accept internal proxy
    auth_header = normalized_headers.get("authorization", "")
    user_sub = normalized_headers.get("x-user-id", "")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ", 1)[1].strip()
        try:
            claims = verify_cognito_token(token)
            user_sub = claims.get("sub", "unknown")
        except Exception as exc:
            logger.warning("Token verification failed: %s", exc)
            return {
                "statusCode": 401,
                "headers": {**cors, "Content-Type": "application/json"},
                "body": json.dumps({"error": f"Unauthorized: {exc}"}),
            }
    elif not user_sub:
        return {
            "statusCode": 401,
            "headers": {**cors, "Content-Type": "application/json"},
            "body": json.dumps({"error": "Missing or malformed Authorization Bearer header"}),
        }

    # 2. Extract and validate request body
    body_raw = event.get("body") or "{}"
    if event.get("isBase64Encoded"):
        body_raw = base64.b64decode(body_raw).decode("utf-8")

    try:
        body = json.loads(body_raw) if isinstance(body_raw, str) else body_raw
    except Exception as exc:
        return {
            "statusCode": 400,
            "headers": {**cors, "Content-Type": "application/json"},
            "body": json.dumps({"error": f"Invalid JSON body: {exc}"}),
        }

    text = body.get("text", "")
    if not isinstance(text, str) or not text.strip():
        return {
            "statusCode": 400,
            "headers": {**cors, "Content-Type": "application/json"},
            "body": json.dumps({"error": "Field 'text' is required and must be a non-empty string"}),
        }

    # Text length check: <= 10000 characters
    if len(text) > 10000:
        return {
            "statusCode": 413,
            "headers": {**cors, "Content-Type": "application/json"},
            "body": json.dumps(
                {"error": "Payload too large. Maximum allowed text length is 10,000 characters."}
            ),
        }

    tz = body.get("tz") or "Europe/Kyiv"
    today_str = body.get("today")
    today = date.fromisoformat(today_str) if today_str else date.today()

    # 3. Parse agenda and measure metrics
    t0 = time.perf_counter()
    try:
        parsed_agenda, usage = parse_agenda(text=text, today=today, tz=tz)
    except Exception as exc:
        logger.error("Error parsing agenda with Bedrock: %s", exc, exc_info=True)
        return {
            "statusCode": 500,
            "headers": {**cors, "Content-Type": "application/json"},
            "body": json.dumps({"error": f"AI Parsing failed: {exc}"}),
        }

    latency_ms = round((time.perf_counter() - t0) * 1000, 2)
    in_tokens = usage.get("input_tokens", 0)
    out_tokens = usage.get("output_tokens", 0)
    cost_usd = calculate_cost_usd(settings.PARSER_MODEL, in_tokens, out_tokens)

    # 4. Structured CloudWatch log line
    log_record = {
        "event": "agenda_parsed",
        "user": user_sub,
        "model": settings.PARSER_MODEL,
        "prompt_version": settings.prompt_version,
        "input_tokens": in_tokens,
        "output_tokens": out_tokens,
        "latency_ms": latency_ms,
        "cost_usd": cost_usd,
    }
    print(json.dumps(log_record))

    # 5. Return 200 response
    return {
        "statusCode": 200,
        "headers": {**cors, "Content-Type": "application/json"},
        "body": json.dumps(
            {
                "agenda": parsed_agenda.model_dump(mode="json"),
                "model": settings.PARSER_MODEL,
                "prompt_version": settings.prompt_version,
            },
            ensure_ascii=False,
        ),
    }
