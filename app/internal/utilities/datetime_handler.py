from datetime import datetime

DATE_TIME_FORMAT = "%m-%d-%Y %H:%M:%S"
DATE_FORMAT = "%m-%d-%Y"

"""
Returns a flag representing whether or not the incoming date is valid.
The valid format is considered to be %m-%d-%Y
"""
def is_valid_date(date_input: str) -> bool:
    try:
        datetime.strptime(date_input, DATE_FORMAT)
        return True
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
