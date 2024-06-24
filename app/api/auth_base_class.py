from abc import ABC

from supabase import Client

class AuthManagerBaseClass(ABC):

    """
    Returns an active supabase instance based on a user's auth tokens.

    Arguments:
    access_token – the access_token associated with a live supabase session.
    refresh_token – the refresh_token associated with a live supabase session.
    """
    def datastore_user_instance(access_token, refresh_token) -> Client:
        pass

    """
    Returns an active supabase instance with admin priviledges.
    """
    def datastore_admin_instance() -> Client:
        pass

    """
    Returns whether or not the monitoring proxy is reachable.
    """
    def is_monitoring_proxy_reachable() -> bool:
        pass

    """
    Returns the monitoring proxy url.
    """
    def get_monitoring_proxy_url() -> str:
        pass

    """
    Returns a config to be used for the monitoring proxy.

    Arguments:
    cache_max_age – the ttl of the cache.
    llm_model – the llm_model used.
    """
    def create_monitoring_proxy_config(cache_max_age, llm_model):
        pass

    """
    Returns a set of headers to be used for the monitoring proxy service.

    Arguments:
    kwargs  – the set of optional arguments.
    """
    def create_monitoring_proxy_headers(**kwargs):
        pass
