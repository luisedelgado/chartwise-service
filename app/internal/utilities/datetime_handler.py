from datetime import datetime

from pytz import timezone

DATE_TIME_FORMAT = "%m-%d-%Y %H:%M:%S"
DATE_FORMAT = "%m-%d-%Y"
DATE_FORMAT_SPELL_OUT_MONTH = "%b %d, %Y"
DATE_FORMAT_YYYY_MM_DD = '%Y-%m-%d'
MONTH_YEAR_FORMAT = "%B %Y"

"""
Returns a flag representing whether or not the incoming date is valid.
The valid format is considered to be %m-%d-%Y

Arguments:
date_input – the date to be validated.
incoming_date_format – the date format.
tz_identifier – the (optional) client timezone identifier to be used for validation.
"""
def is_valid_date(date_input: str,
                  incoming_date_format: str,
                  tz_identifier: str = None) -> bool:
    try:
        if len(tz_identifier or '') == 0:
            return datetime.strptime(date_input, incoming_date_format).date() <= datetime.now().date()

        tz = timezone(tz_identifier)
        return datetime.strptime(date_input, incoming_date_format).date() <= datetime.now(tz).date()
    except:
        return False

"""
Returns a string containing the date that is most recent.

Arguments:
first_date – the first date to be used for comparison.
first_date_format – the first date original format.
second_date – the second date to be used for comparison.
second_date_format – the second date original format.
"""
def retrieve_most_recent_date(first_date: str,
                              first_date_format: str,
                              second_date: str,
                              second_date_format: str) -> str:
    try:
        first_datetime = datetime.strptime(first_date, first_date_format)
        second_datetime = datetime.strptime(second_date, second_date_format)
        second_is_most_recent_date = first_datetime.date() < second_datetime.date()
        return second_date if second_is_most_recent_date else first_date
    except Exception as e:
        raise Exception("Invalid date formats")

"""
Returns a formatted version of the incoming date, for internal use.
The valid format is considered to be %m-%d-%Y
"""
def convert_to_date_format_mm_dd_yyyy(incoming_date: str, incoming_date_format: str) -> str:
    try:
        session_date_as_date = datetime.strptime(incoming_date, incoming_date_format)
        return datetime.strftime(session_date_as_date, DATE_FORMAT)
    except:
        raise Exception("Something went wrong while formatting the incoming date.")

"""
Returns a formatted version of the incoming date as "Oct 10th, 2024".
"""
def convert_to_date_format_spell_out_month(session_date: str, incoming_date_format: str) -> str:
    try:
        session_date_as_date = datetime.strptime(session_date, incoming_date_format)
        return datetime.strftime(session_date_as_date, DATE_FORMAT_SPELL_OUT_MONTH)
    except:
        raise Exception("Something went wrong while formatting the incoming date.")
