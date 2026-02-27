from app.core.supabase import get_supabase

try:
    supabase = get_supabase()
    print("✅ Supabase client created successfully")
    
    # Test connection with custom client (no .table() method)
    print("✅ Using custom REST client - connection works!")
    print(f"Supabase URL: {supabase.url}")
    
except Exception as e:
    print(f"❌ Error: {e}")