import os

from datetime import datetime

"""
Cleans up the incoming set of files from the local directory.

Arguments:
files  – the set of files to be cleaned up
"""
async def clean_up_files(files):
    for file in files:
        os.remove(file)

"""
Returns a flag representing whether or not the incoming date is valid.
The valid format is considered to be mm/dd/yyyy
"""
def is_valid_date(date_input: str) -> bool:
    try:
        datetime.strptime(date_input, '%m/%d/%Y')
        return True
    except:
        return False
