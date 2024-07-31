from ..api.supabase_base_class import SupabaseBaseClass

class SupabaseFactoryBaseClass:

    def supabase_admin_manager(self) -> SupabaseBaseClass:
        pass

    def supabase_user_manager(self, access_token: str, refresh_token: str) -> SupabaseBaseClass:
        pass
