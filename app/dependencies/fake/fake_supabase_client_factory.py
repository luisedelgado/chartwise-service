from .fake_supabase_manager import FakeSupabaseClient
from ...dependencies.api.supabase_factory_base_class import SupabaseFactoryBaseClass

class FakeSupabaseClientFactory(SupabaseFactoryBaseClass):

    def __init__(self,
                 fake_supabase_admin_manager: FakeSupabaseClient,
                 fake_supabase_user_manager: FakeSupabaseClient):
        self.fake_supabase_admin_manager = fake_supabase_admin_manager
        self.fake_supabase_user_manager = fake_supabase_user_manager

    def supabase_admin_manager(self) -> FakeSupabaseClient:
        return self.fake_supabase_admin_manager

    def supabase_user_manager(self, access_token: str, refresh_token: str) -> FakeSupabaseClient:
        return self.fake_supabase_user_manager
