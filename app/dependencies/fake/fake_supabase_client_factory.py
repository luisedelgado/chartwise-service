from .fake_supabase_client import FakeSupabaseClient
from ..api.supabase_factory_base_class import SupabaseFactoryBaseClass

class FakeSupabaseClientFactory(SupabaseFactoryBaseClass):

    def __init__(self,
                 fake_supabase_admin_client: FakeSupabaseClient,
                 fake_supabase_user_client: FakeSupabaseClient):
        self.fake_supabase_admin_client = fake_supabase_admin_client
        self.fake_supabase_user_client = fake_supabase_user_client

    def supabase_admin_client(self) -> FakeSupabaseClient:
        return self.fake_supabase_admin_client

    def supabase_user_client(self, access_token: str, refresh_token: str) -> FakeSupabaseClient:
        return self.fake_supabase_user_client
