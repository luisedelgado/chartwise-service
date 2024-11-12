from abc import ABC, abstractmethod

from ..api.supabase_base_class import SupabaseBaseClass

class SupabaseFactoryBaseClass(ABC):

    """
    Returns a Supabase client with full priviledges.
    """
    @abstractmethod
    def supabase_admin_client() -> SupabaseBaseClass:
        pass

    """
    Retrieves a Supabase client with permissions associated with the incoming tokens.

    Arguments:
    access_token – the access_token.
    refresh_token – the refresh_token.
    """
    @abstractmethod
    def supabase_user_client(access_token: str, refresh_token: str) -> SupabaseBaseClass:
        pass
