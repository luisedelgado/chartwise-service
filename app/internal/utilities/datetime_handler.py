from datetime import datetime, timedelta

from pytz import timezone

DATE_TIME_FORMAT = "%m-%d-%Y %H:%M:%S"
DATE_FORMAT = "%m-%d-%Y"
MONTH_YEAR_FORMAT = "%B %Y"

"""
Returns a flag representing whether or not the incoming date is valid.
The valid format is considered to be %m-%d-%Y

Arguments:
date_input – the date to be validated.
tz_identifier – the (optional) client timezone identifier to be used for validation.
"""
def is_valid_date(date_input: str, tz_identifier: str = None) -> bool:
    try:
        if len(tz_identifier or '') == 0:
            return datetime.strptime(date_input, DATE_FORMAT).date() <= datetime.now().date()

        tz = timezone(tz_identifier)
        return datetime.strptime(date_input, DATE_FORMAT).date() <= datetime.now(tz).date()
    except:
        return False

"""
Returns a formatted version of the incoming date, for internal use.
The valid format is considered to be %m-%d-%Y
"""
def convert_to_internal_date_format(session_date: str) -> str:
    try:
        session_date_as_date = datetime.strptime(session_date, '%Y-%m-%d')
        return datetime.strftime(session_date_as_date, DATE_FORMAT)
    except:
        raise Exception("Something went wrong while formatting the incoming date.")
