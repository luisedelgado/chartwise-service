from ..api.supabase_base_class import SupabaseBaseClass

class SupabaseFactoryBaseClass:

    def supabase_admin_client(self) -> SupabaseBaseClass:
        pass

    def supabase_user_client(self, access_token: str, refresh_token: str) -> SupabaseBaseClass:
        pass
