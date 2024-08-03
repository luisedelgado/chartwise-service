from ..api.supabase_base_class import SupabaseBaseClass

class SupabaseFactoryBaseClass:

    """
    Returns a Supabase client with full priviledges.
    """
    def supabase_admin_client(self) -> SupabaseBaseClass:
        pass

    """
    Retrieves a Supabase client with permissions associated with the incoming tokens.

    Arguments:
    access_token – the access_token.
    refresh_token – the refresh_token.
    """
    def supabase_user_client(self, access_token: str, refresh_token: str) -> SupabaseBaseClass:
        pass
