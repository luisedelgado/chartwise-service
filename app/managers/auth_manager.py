import os, requests, uuid

from fastapi import status
from portkey_ai import PORTKEY_GATEWAY_URL, createHeaders
from supabase import create_client, Client

from ..api.auth_base_class import AuthManagerBaseClass

class AuthManager(AuthManagerBaseClass):

    def datastore_user_instance(self, access_token, refresh_token) -> Client:
        key: str = os.environ.get("SUPABASE_ANON_KEY")
        url: str = os.environ.get("SUPABASE_URL")
        supabase: Client = create_client(url, key)
        supabase.auth.set_session(access_token=access_token,
                                refresh_token=refresh_token)
        return supabase

    def datastore_admin_instance(self) -> Client:
        key: str = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
        url: str = os.environ.get("SUPABASE_URL")
        return create_client(url, key)

    def get_monitoring_proxy_url(self) -> str:
        return PORTKEY_GATEWAY_URL

    def is_monitoring_proxy_reachable(self) -> bool:
        try:
            return requests.get(self.get_monitoring_proxy_url()).status_code < status.HTTP_500_INTERNAL_SERVER_ERROR
        except:
            return False

    def create_monitoring_proxy_config(self, cache_max_age, llm_model):
        return {
            "provider": "openai",
            "virtual_key": os.environ.get("PORTKEY_OPENAI_VIRTUAL_KEY"),
            "cache": {
                "mode": "semantic",
                "max_age": cache_max_age,
            },
            "retry": {
                "attempts": 2,
            },
            "override_params": {
                "model": llm_model,
                "temperature": 0,
            }
        }

    def create_monitoring_proxy_headers(self, **kwargs):
        caching_shard_key = None if "caching_shard_key" not in kwargs else kwargs["caching_shard_key"]
        cache_max_age = None if "cache_max_age" not in kwargs else kwargs["cache_max_age"]
        llm_model = None if "llm_model" not in kwargs else kwargs["llm_model"]
        metadata = None if "metadata" not in kwargs else kwargs["metadata"]
        return createHeaders(trace_id=uuid.uuid4(),
                            api_key=os.environ.get("PORTKEY_API_KEY"),
                            config=self.create_monitoring_proxy_config(cache_max_age, llm_model),
                            cache_namespace=caching_shard_key,
                            metadata=metadata)
