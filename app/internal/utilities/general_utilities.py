from fastapi import status
from pytz import timezone

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
def gender_has_default_pronouns(gender: str) -> bool:
    return (gender in ['male', 'female'])

"""
Attempts to extract a status code for an Exception object whose underlying type we don't know.
"""
def extract_status_code(exception, fallback: status):
    common_status_attributes = ['status_code', 'code', 'status', 'response_code']
    for attr in common_status_attributes:
        if hasattr(exception, attr):
            value = getattr(exception, attr)
            if isinstance(value, int):
                return value
    return fallback
