import os

from supabase import Client, create_client

from ...api.supabase_factory_base_class import SupabaseFactoryBaseClass
from .supabase_manager import SupabaseManager

class SupabaseManagerFactory(SupabaseFactoryBaseClass):

    def supabase_admin_manager(self) -> SupabaseManager:
        try:
            key: str = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
            url: str = os.environ.get("SUPABASE_URL")
            return SupabaseManager(client=create_client(url, key))
        except Exception as e:
            raise Exception(e)

    def supabase_user_manager(self,
                              access_token: str,
                              refresh_token: str) -> SupabaseManager:
        try:
            key: str = os.environ.get("SUPABASE_ANON_KEY")
            url: str = os.environ.get("SUPABASE_URL")
            client: Client = create_client(url, key)
            client.auth.set_session(access_token=access_token,
                                    refresh_token=refresh_token)
            return SupabaseManager(client=client)
        except Exception as e:
            raise Exception(e)
