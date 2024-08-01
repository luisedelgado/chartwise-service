from ...api.supabase_factory_base_class import SupabaseFactoryBaseClass
from .fake_supabase_manager import FakeSupabaseManager

class FakeSupabaseManagerFactory(SupabaseFactoryBaseClass):

    def __init__(self,
                 fake_supabase_admin_manager: FakeSupabaseManager,
                 fake_supabase_user_manager: FakeSupabaseManager):
        self.fake_supabase_admin_manager = fake_supabase_admin_manager
        self.fake_supabase_user_manager = fake_supabase_user_manager

    def supabase_admin_manager(self) -> FakeSupabaseManager:
        return self.fake_supabase_admin_manager

    def supabase_user_manager(self, access_token: str, refresh_token: str) -> FakeSupabaseManager:
        return self.fake_supabase_user_manager
