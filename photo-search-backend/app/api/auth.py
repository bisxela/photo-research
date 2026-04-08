from uuid import uuid4

from fastapi import APIRouter, HTTPException, status, Depends

from app.core.auth import create_access_token, get_current_user, hash_password, verify_password
from app.core.database import database
from app.models.schemas import AuthRequest, AuthResponse, UserResponse

router = APIRouter()


@router.post("/register", response_model=AuthResponse)
async def register(request: AuthRequest):
    existing = await database.fetch_one(
        "SELECT id FROM users WHERE username = :username",
        {"username": request.username},
    )
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Username already exists")

    user_id = str(uuid4())
    password_hash = hash_password(request.password)

    user = await database.fetch_one(
        """
        INSERT INTO users (id, username, password_hash)
        VALUES (:id, :username, :password_hash)
        RETURNING id, username, created_at
        """,
        {"id": user_id, "username": request.username, "password_hash": password_hash},
    )

    token = create_access_token(str(user["id"]), user["username"])
    return AuthResponse(
        access_token=token,
        user=UserResponse(
            id=user["id"],
            username=user["username"],
            created_at=user["created_at"],
        ),
    )


@router.post("/login", response_model=AuthResponse)
async def login(request: AuthRequest):
    user = await database.fetch_one(
        "SELECT id, username, password_hash, created_at FROM users WHERE username = :username",
        {"username": request.username},
    )
    if not user or not verify_password(request.password, user["password_hash"]):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid username or password")

    token = create_access_token(str(user["id"]), user["username"])
    return AuthResponse(
        access_token=token,
        user=UserResponse(
            id=user["id"],
            username=user["username"],
            created_at=user["created_at"],
        ),
    )


@router.get("/me", response_model=UserResponse)
async def me(current_user=Depends(get_current_user)):
    return UserResponse(
        id=current_user["id"],
        username=current_user["username"],
        created_at=current_user["created_at"],
    )
