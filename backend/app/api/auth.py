from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, EmailStr
from app.core.supabase import get_supabase, SupabaseClient

router = APIRouter(prefix="/auth", tags=["Authentication"])

# Request/Response Models
class SignUpRequest(BaseModel):
    email: EmailStr
    password: str
    full_name: str

class SignInRequest(BaseModel):
    email: EmailStr
    password: str

class AuthResponse(BaseModel):
    user: dict
    session: dict
    message: str

# Sign Up
@router.post("/signup")
async def sign_up(data: SignUpRequest, supabase: SupabaseClient = Depends(get_supabase)):
    try:
        # Create user in Supabase Auth
        auth_result = supabase.auth_signup(
            email=data.email,
            password=data.password,
            metadata={"full_name": data.full_name}
        )
        
        print(f"Auth result: {auth_result}")  # Debug
        
        # Extract user info from response
        user_data = auth_result.get("user") or auth_result
        user_id = user_data.get("id")
        
        if not user_id:
            raise HTTPException(status_code=400, detail=f"No user ID in response: {auth_result}")
        
        # Create user profile
        try:
            supabase.table_insert("user_profiles", {
                "id": user_id,
                "full_name": data.full_name
            })
        except Exception as profile_error:
            print(f"Profile creation error (non-critical): {profile_error}")
        
        return {
            "user": user_data,
            "session": auth_result.get("session", {}),
            "message": "User created successfully"
        }
            
    except HTTPException:
        raise
    except Exception as e:
        print(f"Signup error: {str(e)}")
        raise HTTPException(status_code=400, detail=f"Signup failed: {str(e)}")

# Sign In
@router.post("/signin")
async def sign_in(data: SignInRequest, supabase: SupabaseClient = Depends(get_supabase)):
    try:
        result = supabase.auth_signin(
            email=data.email,
            password=data.password
        )
        
        user_data = result.get("user") or {}
        
        return {
            "user": user_data,
            "session": result,
            "message": "Signed in successfully"
        }
            
    except Exception as e:
        print(f"Signin error: {str(e)}")
        raise HTTPException(status_code=401, detail=f"Sign in failed: {str(e)}")

# Sign Out
@router.post("/signout")
async def sign_out():
    return {"message": "Signed out successfully"}

# Get Current User (simplified)
@router.get("/me")
async def get_current_user():
    return {"message": "Not implemented yet - requires auth middleware"}