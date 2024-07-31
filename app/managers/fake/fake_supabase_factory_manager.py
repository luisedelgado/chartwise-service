from ...api.supabase_factory_base_class import SupabaseFactoryBaseClass
from .fake_supabase_manager import FakeSupabaseManager

class FakeSupabaseManagerFactory(SupabaseFactoryBaseClass):

    def supabase_admin_manager(self) -> FakeSupabaseManager:
        return FakeSupabaseManager()

    def supabase_user_manager(self, access_token: str, refresh_token: str) -> FakeSupabaseManager:
        return FakeSupabaseManager()
