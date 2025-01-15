import requests

from fastapi import status
from portkey_ai import PORTKEY_GATEWAY_URL

def get_monitoring_proxy_url() -> str:
    return PORTKEY_GATEWAY_URL

def use_monitoring_proxy() -> bool:
    try:
        return requests.get(get_monitoring_proxy_url()).status_code < status.HTTP_500_INTERNAL_SERVER_ERROR
    except:
        return False
