import os

from supabase import create_client, Client

"""
Returns an active supabase instance based on a user's auth tokens.

Arguments:
access_token  – the access_token associated with a live supabase session
refresh_token  – the refresh_token associated with a live supabase session
"""
def supabase_user_instance(access_token, refresh_token) -> Client:
    key: str = os.environ.get("SUPABASE_ANON_KEY")
    url: str = os.environ.get("SUPABASE_URL")
    supabase: Client = create_client(url, key)
    supabase.auth.set_session(access_token=access_token,
                            refresh_token=refresh_token)
    return supabase

"""
Returns an active supabase instance with admin priviledges.
"""
def supabase_admin_instance() -> Client:
    key: str = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    url: str = os.environ.get("SUPABASE_URL")
    return create_client(url, key)
