import os, uuid

from fastapi import HTTPException, status
from portkey_ai import createHeaders
from pytz import timezone

from ...dependencies.api.supabase_base_class import SupabaseBaseClass

"""
Returns a flag representing whether or not the incoming timezone identifier is valid.
For context: https://en.wikipedia.org/wiki/List_of_tz_database_time_zones
"""
def is_valid_timezone_identifier(tz_identifier: str) -> bool:
    try:
        timezone(tz_identifier)
        return True
    except:
        return False

"""
Returns a flag representing whether or not the incoming gender has default pronouns.
"""
def gender_has_default_pronouns(gender: str = None) -> bool:
    if gender is None:
        return False
    return (gender in ['male', 'female'])

"""
Attempts to extract a status code for an Exception object whose underlying type we don't know.
"""
def extract_status_code(exception, fallback: status):
    if isinstance(exception, HTTPException):
        return exception.status_code

    common_status_attributes = ['status_code', 'code', 'status', 'response_code']
    for attr in common_status_attributes:
        if hasattr(exception, attr):
            value = getattr(exception, attr)
            if isinstance(value, int):
                return value
    return fallback

"""
Retrieves the current user's language preference.
"""
def get_user_language_code(user_id: str,
                           supabase_client: SupabaseBaseClass):
    try:
        therapist_query = supabase_client.select(fields="*",
                                                 filters={
                                                   'id': user_id
                                                 },
                                                 table_name="therapists")
        assert (0 != len((therapist_query).data))
        return therapist_query.dict()['data'][0]["language_preference"]
    except Exception as e:
        raise Exception("Encountered an issue while pulling user's language preference.")

"""
Maps a language code to a language abbreviation.
"""
def map_language_code_to_language(language_code: str):
    if language_code.startswith("en"):
        return "en"
    elif language_code.startswith("es"):
        return "es"
    else:
        raise Exception ("Untracked language code")

"""
Creates a proxy config for the monitoring layer.
"""
def create_monitoring_proxy_config(llm_model, cache_max_age = None):
        config = {
            "provider": "openai",
            "virtual_key": os.environ.get("PORTKEY_OPENAI_VIRTUAL_KEY"),
            "retry": {
                "attempts": 2,
            },
            "override_params": {
                "model": llm_model,
                "temperature": 0,
            }
        }
        if cache_max_age is not None:
            config["cache"] = {
                "mode": "semantic",
                "max_age": cache_max_age,
            }
        return config

"""
Creates proxy headers for the monitoring layer.
"""
def create_monitoring_proxy_headers(**kwargs):
    caching_shard_key = None if "caching_shard_key" not in kwargs else kwargs["caching_shard_key"]
    cache_max_age = None if "cache_max_age" not in kwargs else kwargs["cache_max_age"]
    llm_model = None if "llm_model" not in kwargs else kwargs["llm_model"]
    metadata = None if "metadata" not in kwargs else kwargs["metadata"]

    if cache_max_age is not None and caching_shard_key is not None:
        monitoring_proxy_config = create_monitoring_proxy_config(cache_max_age=cache_max_age,
                                                                 llm_model=llm_model)
        return createHeaders(trace_id=uuid.uuid4(),
                             api_key=os.environ.get("PORTKEY_API_KEY"),
                             config=monitoring_proxy_config,
                             cache_namespace=caching_shard_key,
                             metadata=metadata)

    monitoring_proxy_config = create_monitoring_proxy_config(llm_model=llm_model)
    return createHeaders(trace_id=uuid.uuid4(),
                         api_key=os.environ.get("PORTKEY_API_KEY"),
                         config=monitoring_proxy_config,
                         metadata=metadata)

def map_stripe_product_name_to_chartwise_tier(stripe_plan: str) -> str:
    if stripe_plan == "premium_plan_yearly" or stripe_plan == "premium_plan_monthly":
        return "premium"
    elif stripe_plan == "basic_plan_yearly" or stripe_plan == "basic_plan_monthly":
        return "basic"
    else:
        raise Exception("Untracked Stripe product name")
