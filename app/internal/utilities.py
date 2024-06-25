import os, shutil

from datetime import datetime

from fastapi import (File, UploadFile)
from PIL import Image
from pytz import timezone

DATE_TIME_FORMAT = "%m-%d-%Y %H:%M:%S"
DATE_FORMAT = "%m-%d-%Y"
FILES_DIR = 'app/files'

"""
A result representation of an image-copy operation.
"""
class FileCopyResult():
    def __init__(self, file_copy_name: str, file_copy_full_path: str, file_copies: list):
        self.file_copy_name = file_copy_name
        self.file_copy_full_path = file_copy_full_path
        self.file_copies = file_copies

"""
Returns a wrapper with the full path of the incoming file's PDF copy.

Arguments:
image  – the image file to be processed
"""
async def make_image_pdf_copy(image: UploadFile = File(...)) -> FileCopyResult:
    try:
        copy_file_result: FileCopyResult = await make_file_copy(image)
        copy_bare_name, copy_extension = os.path.splitext(copy_file_result.file_copy_name)

        pdf_extension = '.pdf'
        if copy_extension.lower() == pdf_extension:
            # It's already a PDF, we can return as is.
            return copy_file_result

        # We need to make a PDF copy.
        image_copy_pdf_path = FILES_DIR + '/' + copy_bare_name + pdf_extension
        file_copies = copy_file_result.file_copies

        Image.open(copy_file_result.file_copy_full_path).convert('RGB').save(image_copy_pdf_path)
        file_copies.append(image_copy_pdf_path)

        return FileCopyResult(file_copy_name=copy_file_result.file_copy_name,
                              file_copy_full_path=image_copy_pdf_path,
                              file_copies=file_copies)
    finally:
        await image.close()

"""
Returns a wrapper with the full path of the incoming file's copy.

Arguments:
file  – the file to be processed
"""
async def make_file_copy(file: UploadFile = File(...)) -> FileCopyResult:
    try:
        _, file_extension = os.path.splitext(file.filename)
        audio_copy_file_name = datetime.now().strftime("%d-%m-%Y-%H-%M-%S") + file_extension
        audio_copy_full_path = FILES_DIR + '/' + audio_copy_file_name

        # Write incoming audio to our local volume for further processing
        with open(audio_copy_full_path, 'wb+') as buffer:
            shutil.copyfileobj(file.file, buffer)

        assert os.path.exists(audio_copy_full_path), "Something went wrong while processing the file."

        return FileCopyResult(file_copy_name=audio_copy_file_name,
                              file_copy_full_path=audio_copy_full_path,
                              file_copies=[audio_copy_full_path])
    finally:
        await file.close()

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
The valid format is considered to be %m-%d-%Y
"""
def is_valid_date(date_input: str) -> bool:
    try:
        datetime.strptime(date_input, DATE_FORMAT)
        return True
    except:
        return False

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
Returns a formatted version of the incoming date, for internal use.
The valid format is considered to be %m-%d-%Y
"""
def convert_to_internal_date_format(session_date: str) -> str:
    try:
        session_date_as_date = datetime.strptime(session_date, '%Y-%m-%d')
        return datetime.strftime(session_date_as_date, DATE_FORMAT)
    except:
        raise Exception("Something went wrong while formatting the incoming date.")
