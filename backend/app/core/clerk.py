import structlog
from clerk_backend_api import AuthenticateRequestOptions, Clerk
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import settings

logger = structlog.get_logger()
security = HTTPBearer()
clerk_client = Clerk(bearer_auth=settings.clerk_secret_key) if settings.clerk_secret_key else None


async def get_clerk_user_id(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> str:
    """Verify Clerk JWT and return the user's clerk_id."""
    if not clerk_client:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": "AUTH_UNAVAILABLE", "message": "Authentication service unavailable"},
        )

    try:
        # Build a request-like object for the SDK
        request_state = clerk_client.authenticate_request(
            request,
            AuthenticateRequestOptions(
                authorized_parties=settings.cors_origin_list,
            ),
        )

        if request_state.is_signed_in:
            return request_state.payload["sub"]  # clerk user id

        logger.warning("clerk_auth_not_signed_in", reason=request_state.reason)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "INVALID_TOKEN", "message": "Invalid or expired token"},
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.warning("clerk_auth_failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "INVALID_TOKEN", "message": "Invalid or expired token"},
        ) from e


def verify_clerk_webhook(request: Request, payload: bytes) -> dict:
    """Verify Clerk webhook signature using svix."""
    from svix.webhooks import Webhook, WebhookVerificationError

    if not settings.clerk_webhook_secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": "WEBHOOK_UNAVAILABLE", "message": "Webhook verification unavailable"},
        )

    headers = {
        "svix-id": request.headers.get("svix-id", ""),
        "svix-timestamp": request.headers.get("svix-timestamp", ""),
        "svix-signature": request.headers.get("svix-signature", ""),
    }

    wh = Webhook(settings.clerk_webhook_secret)
    try:
        return wh.verify(payload, headers)
    except WebhookVerificationError as e:
        logger.warning("clerk_webhook_verification_failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "INVALID_WEBHOOK", "message": "Webhook verification failed"},
        ) from e
