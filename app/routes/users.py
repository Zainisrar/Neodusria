from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, EmailStr, validator
from bson import ObjectId
from datetime import datetime, timedelta
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi.security import OAuth2PasswordBearer
from app.db import db

router = APIRouter(prefix="/users", tags=["Users & Domains"])

users_collection = db["users"]
domains_collection = db["domains"]

# ---------------------- Security ----------------------
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

SECRET_KEY = "your-secret-key"  # 🔒 store in env
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="users/login")


# ---------------------- Models ----------------------
class User(BaseModel):
    name: str
    email: EmailStr
    role: str
    password: str
    avatar: str | None = None
    domain: str
    permissions: list[str] = []

    @validator("role")
    def validate_role(cls, value):
        allowed_roles = ["admin", "individual"]
        if value not in allowed_roles:
            raise ValueError(f"Role must be one of {allowed_roles}")
        return value


class Domain(BaseModel):
    name: str
    icon: str | None = None
    locked: bool = False
    admin_contact: str | None = None


def serialize(doc):
    doc["_id"] = str(doc["_id"])
    return doc


def http_error(status: int, message: str, details: dict | None = None):
    return HTTPException(
        status_code=status,
        detail={"success": False, "message": message, "details": details or {}}
    )


# ---------------------- Token Helpers ----------------------
def create_access_token(data: dict, expires_delta: timedelta | None = None):
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def get_current_user(token: str = Depends(oauth2_scheme)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise http_error(401, "Invalid authentication token")
    except JWTError:
        raise http_error(401, "Invalid authentication token")

    user = users_collection.find_one({"_id": ObjectId(user_id)})
    if not user:
        raise http_error(401, "User not found")
    return serialize(user)


# ---------------------- Users CRUD ----------------------
@router.get("/")
def get_users(current_user: dict = Depends(get_current_user)):
    try:
        users = [serialize(u) for u in users_collection.find()]
        return {"success": True, "data": users}
    except Exception as e:
        raise http_error(500, "Failed to fetch users", {"error": str(e)})


@router.post("/")
def create_user(user: User):
    try:
        existing = users_collection.find_one({"email": user.email})
        if existing:
            raise http_error(400, "User with this email already exists", {"email": user.email})

        # hash password
        hashed_password = pwd_context.hash(user.password)
        user_data = user.dict()
        user_data["password"] = hashed_password

        result = users_collection.insert_one(user_data)
        new_user = users_collection.find_one({"_id": result.inserted_id})

        return {"success": True, "message": "User created successfully", "data": serialize(new_user)}

    except ValueError as ve:
        raise http_error(422, "Validation error", {"field": "role", "error": str(ve)})
    except Exception as e:
        raise http_error(500, "Failed to create user", {"error": str(e)})


@router.put("/{user_id}")
def update_user(user_id: str, updated_user: User, current_user: dict = Depends(get_current_user)):
    try:
        hashed_password = pwd_context.hash(updated_user.password)
        updated_data = updated_user.dict()
        updated_data["password"] = hashed_password

        result = users_collection.update_one(
            {"_id": ObjectId(user_id)},
            {"$set": updated_data}
        )

        if result.matched_count == 0:
            raise http_error(404, "User not found", {"user_id": user_id})

        updated = users_collection.find_one({"_id": ObjectId(user_id)})
        return {"success": True, "message": "User updated successfully", "data": serialize(updated)}

    except ValueError as ve:
        raise http_error(422, "Validation error", {"field": "role", "error": str(ve)})
    except Exception as e:
        raise http_error(500, "Failed to update user", {"error": str(e)})


@router.delete("/{user_id}")
def delete_user(user_id: str, current_user: dict = Depends(get_current_user)):
    try:
        result = users_collection.delete_one({"_id": ObjectId(user_id)})
        if result.deleted_count == 0:
            raise http_error(404, "User not found", {"user_id": user_id})

        return {"success": True, "message": f"User {user_id} deleted"}

    except Exception as e:
        raise http_error(500, "Failed to delete user", {"error": str(e)})


# ---------------------- Login ----------------------
@router.post("/login")
def login(email: str, password: str):
    user = users_collection.find_one({"email": email})
    if not user:
        raise http_error(401, "Invalid email or password")

    if not pwd_context.verify(password, user["password"]):
        raise http_error(401, "Invalid email or password")

    # Generate JWT
    access_token = create_access_token({"sub": str(user["_id"]), "role": user["role"]})

    return {
        "success": True,
        "message": "Login successful",
        "access_token": access_token,
        "token_type": "bearer",
        "user": serialize(user)
    }


# ---------------------- Domains CRUD ----------------------
@router.get("/domains")
def get_domains(current_user: dict = Depends(get_current_user)):
    try:
        domains = [serialize(d) for d in domains_collection.find()]
        return {"success": True, "data": domains}
    except Exception as e:
        raise http_error(500, "Failed to fetch domains", {"error": str(e)})


@router.post("/domains")
def create_domain(domain: Domain, current_user: dict = Depends(get_current_user)):
    try:
        existing = domains_collection.find_one({"name": domain.name})
        if existing:
            raise http_error(400, "Domain with this name already exists", {"name": domain.name})

        result = domains_collection.insert_one(domain.dict())
        new_domain = domains_collection.find_one({"_id": result.inserted_id})

        return {"success": True, "message": "Domain created successfully", "data": serialize(new_domain)}

    except Exception as e:
        raise http_error(500, "Failed to create domain", {"error": str(e)})


@router.put("/domains/{domain_id}")
def update_domain(domain_id: str, updated_domain: Domain, current_user: dict = Depends(get_current_user)):
    try:
        result = domains_collection.update_one(
            {"_id": ObjectId(domain_id)},
            {"$set": updated_domain.dict()}
        )

        if result.matched_count == 0:
            raise http_error(404, "Domain not found", {"domain_id": domain_id})

        updated = domains_collection.find_one({"_id": ObjectId(domain_id)})
        return {"success": True, "message": "Domain updated successfully", "data": serialize(updated)}

    except Exception as e:
        raise http_error(500, "Failed to update domain", {"error": str(e)})


@router.delete("/domains/{domain_id}")
def delete_domain(domain_id: str, current_user: dict = Depends(get_current_user)):
    try:
        result = domains_collection.delete_one({"_id": ObjectId(domain_id)})
        if result.deleted_count == 0:
            raise http_error(404, "Domain not found", {"domain_id": domain_id})

        return {"success": True, "message": f"Domain {domain_id} deleted"}

    except Exception as e:
        raise http_error(500, "Failed to delete domain", {"error": str(e)})
