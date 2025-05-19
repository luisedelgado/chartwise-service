import re, uuid

from fastapi import (
    HTTPException,
    status,
    Request
)
from pytz import timezone

from ...internal.schemas import THERAPISTS_TABLE_NAME
from ...dependencies.dependency_container import AwsDbBaseClass

def is_valid_timezone_identifier(
    tz_identifier: str
) -> bool:
    """
    Returns a flag representing whether or not the incoming timezone identifier is valid.
    For context: https://en.wikipedia.org/wiki/List_of_tz_database_time_zones
    """
    try:
        timezone(tz_identifier)
        return True
    except:
        return False

def gender_has_default_pronouns(
    gender: str = None
) -> bool:
    """
    Returns a flag representing whether or not the incoming gender has default pronouns.
    """
    if gender is None:
        return False
    return (gender in ['male', 'female'])

def extract_status_code(
    exception,
    fallback: status
):
    """
    Attempts to extract a status code for an Exception object whose underlying type we don't know.
    """
    if isinstance(exception, HTTPException):
        return exception.status_code

    common_status_attributes = ['status_code', 'code', 'status', 'response_code']
    for attr in common_status_attributes:
        if hasattr(exception, attr):
            value = getattr(exception, attr)
            if isinstance(value, int):
                return value
    return fallback

async def get_user_language_code(
    user_id: str,
    aws_db_client: AwsDbBaseClass,
    request: Request
):
    """
    Retrieves the current user's language preference.
    """
    try:
        therapist_query = await aws_db_client.select(
            request=request,
            user_id=user_id,
            fields=["language_preference"],
            filters={
                'id': user_id
            },
            table_name=THERAPISTS_TABLE_NAME
        )
        assert 1 == len(therapist_query), "Expected exactly one therapist to be returned"
        return therapist_query[0]["language_preference"]
    except Exception as e:
        raise RuntimeError(f"Encountered an issue while pulling user's language preference: {e}") from e

def map_language_code_to_language(
    language_code: str
):
    """
    Maps a language code to a language abbreviation.
    """
    if language_code.startswith("en"):
        return "en"
    elif language_code.startswith("es"):
        return "es"
    else:
        raise Exception ("Untracked language code")

def is_valid_extension(
    ext: str
) -> bool:
    if ext is None:
        return False
    return bool(re.fullmatch(r"\.[a-zA-Z0-9]+", ext))

def is_valid_uuid(
    uuid_string: str
) -> bool:
    if len(uuid_string or '') == 0:
        return False

    try:
        val = uuid.UUID(uuid_string, version=None)
        return str(val) == uuid_string.lower()
    except (ValueError, AttributeError, TypeError):
        return False

def retrieve_ip_address(request: Request) -> str:
    """
    Extracts the IP address from the request.
    This function checks the "X-Forwarded-For" header first, which is commonly used in
    load-balanced environments. If that header is not present, it falls back to the
    "client.host" attribute of the request.
    """
    # Check if the request is behind a proxy or load balancer
    x_forwarded_for = request.headers.get("X-Forwarded-For")
    if x_forwarded_for:
        ip_address = x_forwarded_for.split(",")[0].strip()
    else:
        ip_address = request.client.host
    return ip_address
