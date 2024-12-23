import os

from supabase import Client, create_client

from .supabase_client import SupabaseClient
from ...dependencies.api.supabase_factory_base_class import SupabaseFactoryBaseClass

class SupabaseClientFactory(SupabaseFactoryBaseClass):

    def supabase_admin_client(self) -> SupabaseClient:
        try:
            key: str = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
            url: str = os.environ.get("SUPABASE_URL")
            return SupabaseClient(client=create_client(url, key), is_admin=True)
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
            return SupabaseClient(client=client, is_admin=False)
        except Exception as e:
            raise Exception(e)
