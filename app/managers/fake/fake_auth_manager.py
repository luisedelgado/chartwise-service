from supabase import Client

from ...api.auth_base_class import AuthManagerBaseClass

class FakeAuthManager(AuthManagerBaseClass):
    def datastore_user_instance(self, access_token, refresh_token) -> Client:
        return None

    def datastore_admin_instance(self) -> Client:
        return None

    def get_monitoring_proxy_url(self) -> str:
        return ""

    def is_monitoring_proxy_reachable(self) -> bool:
        return False

    def create_monitoring_proxy_config(self, cache_max_age, llm_model):
        return {}

    def create_monitoring_proxy_headers(self, **kwargs):
        return {}
