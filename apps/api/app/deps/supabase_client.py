from typing import Optional

from app.deps.deps import SupabaseCreds, get_supabase_creds
from fastapi import Depends, Header, HTTPException, status
from reelix_user_context.user_context_repo import SupabaseUserContextRepo
from reelix_user_context.user_context_service import UserContextService


def require_bearer_token(authorization: Optional[str] = Header(None)) -> str:
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header",
        )
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Authorization header format",
        )
    return token.strip()


def get_supabase_client(
    user_token: str = Depends(require_bearer_token),
    creds: SupabaseCreds = Depends(get_supabase_creds),
):
    """Return a Supabase client authorized as the end user (DB calls go through PostgREST with user JWT)."""
    try:
        from supabase import Client, create_client  # type: ignore

        client: Client = create_client(creds.url, creds.api_key)

        # Critical: attach the user's JWT for DB calls so RLS (auth.uid()) is enforced.
        client.postgrest.auth(user_token)

        return client
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Supabase init failed: {exc}",
        )


def get_current_user_id(
    client=Depends(get_supabase_client), user_token: str = Depends(require_bearer_token)
) -> str:
    """Fetch the current user id (UUID) from GoTrue using the user's token."""
    try:
        # gotrue-python expects the token to be passed explicitly
        resp = client.auth.get_user(user_token)
        user = getattr(resp, "user", None) or getattr(resp, "data", None)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token",
            )
        user_id = getattr(user, "id", None) or user.get("id")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid user in token"
            )
        return user_id
    except HTTPException:
        raise
    except Exception as exc:
        # If GoTrue call fails, surface as auth error (most common case)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Failed to resolve user: {exc}",
        )


def get_user_context_repo(
    sb=Depends(get_supabase_client),
) -> SupabaseUserContextRepo:
    return SupabaseUserContextRepo(client=sb)


def get_user_context_service(
    repo: SupabaseUserContextRepo = Depends(get_user_context_repo),
) -> UserContextService:
    return UserContextService(repo=repo)
