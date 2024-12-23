import os

from supabase import Client, create_client

from .supabase_client import SupabaseClient
from ..fake.fake_supabase_storage_client import FakeSupabaseStorageClient
from ..implementation.supabase_storage_client import SupabaseStorageClient
from ...dependencies.api.supabase_factory_base_class import SupabaseFactoryBaseClass

class SupabaseClientFactory(SupabaseFactoryBaseClass):

    def __init__(self, environment: str):
        self.environment = environment

    def supabase_admin_client(self) -> SupabaseClient:
        try:
            key: str = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
            url: str = os.environ.get("SUPABASE_URL")
            storage_client = FakeSupabaseStorageClient() if self.environment != "prod" else SupabaseStorageClient()
            return SupabaseClient(client=create_client(url, key),
                                  storage_client=storage_client,
                                  is_admin=True)
        except Exception as e:
            raise Exception(e)

    def supabase_user_client(self,
                             access_token: str,
                             refresh_token: str) -> SupabaseClient:
        try:
            key: str = os.environ.get("SUPABASE_ANON_KEY")
            url: str = os.environ.get("SUPABASE_URL")
            client: Client = create_client(url, key)
            client.auth.set_session(access_token=access_token,
                                    refresh_token=refresh_token)
            storage_client = FakeSupabaseStorageClient() if self.environment != "prod" else SupabaseStorageClient()
            return SupabaseClient(client=client,
                                  storage_client=storage_client,
                                  is_admin=False)
        except Exception as e:
            raise Exception(e)
