from supabase import create_client, Client
from app.config import settings

# Anon client — respects RLS, used for auth operations
supabase: Client = create_client(settings.supabase_url, settings.supabase_key)

# Service role client — bypasses RLS, used for admin operations (webhooks, export)
supabase_admin: Client = create_client(settings.supabase_url, settings.supabase_service_key)
