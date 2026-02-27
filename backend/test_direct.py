from app.core.supabase import get_supabase

try:
    supabase = get_supabase()
    print(f"✅ Supabase client created")
    print(f"URL: {supabase.url}")
    print(f"API Key: {supabase.key[:20]}...")
    
    # Test signup
    print("\nTesting signup...")
    result = supabase.auth_signup(
        email="pythontest@example.com",
        password="Test123456!",
        metadata={"full_name": "Python Test"}
    )
    
    print("✅ Signup successful!")
    print(f"User ID: {result.get('id')}")
    print(f"Email: {result.get('email')}")
    
except Exception as e:
    print(f"❌ Error: {e}")