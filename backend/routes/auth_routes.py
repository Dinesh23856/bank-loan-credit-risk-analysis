import os
from fastapi import APIRouter, Depends, HTTPException, Response, Request
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import User
from ..schemas import UserRegister, UserLogin, TokenResponse, UserResponse, TokenRefreshResponse
from ..auth import (
    hash_password,
    verify_password,
    create_access_token,
    create_refresh_token,
    rotate_refresh_token,
    revoke_refresh_token
)
from ..dependencies import require_authenticated_user, normalize_role
from ..services.audit_service import log_audit_event
from ..limiter import limiter

router = APIRouter(prefix="/auth", tags=["Authentication"])

COOKIE_NAME = "refresh_token"
COOKIE_MAX_AGE = 7 * 24 * 3600  # 7 days

@router.post("/register", response_model=UserResponse, status_code=201)
@limiter.limit("10/minute")
def register(request: Request, x: UserRegister, db: Session = Depends(get_db)):
    email = str(x.email).lower()
    if db.query(User).filter(User.email == email).first():
        raise HTTPException(409, "Email is already registered.")
    u = User(name=x.name.strip(), email=email, password_hash=hash_password(x.password), role="user")
    db.add(u)
    db.commit()
    db.refresh(u)

    client_ip = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    log_audit_event(
        db=db,
        action="USER_REGISTERED",
        user=u,
        resource_type="user",
        resource_id=str(u.id),
        ip_address=client_ip,
        user_agent=user_agent,
        status="SUCCESS",
        metadata={"email": u.email, "name": u.name}
    )
    db.commit()

    return u

@router.post("/login", response_model=TokenResponse)
@limiter.limit("30/minute")
def login(request: Request, response: Response, x: UserLogin, db: Session = Depends(get_db)):
    client_ip = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    u = db.query(User).filter(User.email == str(x.email).lower()).first()
    if not u or not verify_password(x.password, u.password_hash):
        log_audit_event(
            db=db,
            action="LOGIN_FAILURE",
            user=None,
            role="ANONYMOUS",
            resource_type="auth",
            resource_id=None,
            ip_address=client_ip,
            user_agent=user_agent,
            status="FAILURE",
            reason="Invalid email or password",
            metadata={"email": str(x.email).lower()}
        )
        db.commit()
        raise HTTPException(401, "Invalid email or password.")
    
    access_token = create_access_token(u.id, u.role)
    refresh_token = create_refresh_token(u.id, u.role)

    log_audit_event(
        db=db,
        action="LOGIN_SUCCESS",
        user=u,
        role=normalize_role(u.role),
        resource_type="auth",
        resource_id=str(u.id),
        ip_address=client_ip,
        user_agent=user_agent,
        status="SUCCESS",
        metadata={"email": u.email}
    )
    db.commit()

    # Set HttpOnly refresh token cookie
    is_prod = os.getenv("ENVIRONMENT", "development").lower() == "production"
    response.set_cookie(
        key=COOKIE_NAME,
        value=refresh_token,
        httponly=True,
        max_age=COOKIE_MAX_AGE,
        samesite="lax",
        secure=is_prod
    )
    return {"access_token": access_token, "role": u.role}

@router.post("/refresh", response_model=TokenRefreshResponse)
def refresh_token_endpoint(request: Request, response: Response):
    # Retrieve refresh token from cookie or authorization header
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        # Fallback to Authorization header if provided
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ", 1)[1]
    
    if not token:
        raise HTTPException(401, "Refresh token cookie is missing.")

    new_access_token, new_refresh_token, user_id, role = rotate_refresh_token(token)

    # Set rotated cookie
    is_prod = os.getenv("ENVIRONMENT", "development").lower() == "production"
    response.set_cookie(
        key=COOKIE_NAME,
        value=new_refresh_token,
        httponly=True,
        max_age=COOKIE_MAX_AGE,
        samesite="lax",
        secure=is_prod
    )
    return {"access_token": new_access_token, "token_type": "bearer"}

@router.post("/logout")
def logout(request: Request, response: Response):
    token = request.cookies.get(COOKIE_NAME)
    if token:
        revoke_refresh_token(token)
    response.delete_cookie(key=COOKIE_NAME, samesite="lax")
    return {"message": "Logged out successfully."}

@router.get("/me", response_model=UserResponse)
def me(user = Depends(require_authenticated_user)):
    return user
