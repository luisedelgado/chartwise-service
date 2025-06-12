import mimetypes
import os, shutil

from datetime import datetime

from fastapi import (File, UploadFile)
from PIL import Image
from pillow_heif import register_heif_opener

from .datetime_handler import DATE_TIME_FORMAT_FILE

FILES_DIR = 'app/files'
PDF_EXTENSION = '.pdf'

# Register HEIF opener for Pillow
register_heif_opener()

class FileCopyResult:
    """
    A result representation of an image-copy operation.
    """
    def __init__(
        self,
        file_copy_name_with_ext: str,
        file_copy_full_path: str,
        file_copies: list,
        file_copy_directory: str,
        file_copy_name_without_ext: str
    ):
        self.file_copy_directory = file_copy_directory
        self.file_copy_name_with_ext = file_copy_name_with_ext
        self.file_copy_name_without_ext = file_copy_name_without_ext
        self.file_copy_full_path = file_copy_full_path
        self.file_copies = file_copies

async def make_image_pdf_copy(
    image: UploadFile = File(...)
) -> FileCopyResult:
    """
    Returns a wrapper with the full path of the incoming file's PDF copy.

    Arguments:
    image – the image file to be processed
    """
    try:
        copy_file_result: FileCopyResult = await make_file_copy(image)
        copy_bare_name, copy_extension = os.path.splitext(copy_file_result.file_copy_name_with_ext)

        copy_extension = copy_extension.lower()
        if copy_extension == PDF_EXTENSION:
            # It's already a PDF, we can return as is.
            return copy_file_result
        elif mimetypes.guess_extension(image.content_type).lower() == PDF_EXTENSION:
            return copy_file_result

        # We need to make a PDF copy.
        image_copy_directory = FILES_DIR + '/'
        image_copy_pdf_path = image_copy_directory + copy_bare_name + PDF_EXTENSION
        file_copies = copy_file_result.file_copies

        Image.open(copy_file_result.file_copy_full_path).convert('RGB').save(image_copy_pdf_path)
        file_copies.append(image_copy_pdf_path)

        return FileCopyResult(file_copy_name_with_ext=copy_file_result.file_copy_name_with_ext,
                              file_copy_full_path=image_copy_pdf_path,
                              file_copies=file_copies,
                              file_copy_directory=image_copy_directory,
                              file_copy_name_without_ext=copy_bare_name)
    finally:
        await image.close()

async def make_file_copy(
    file: UploadFile = File(...)
) -> FileCopyResult:
    """
    Returns a wrapper with the full path of the incoming file's copy.

    Arguments:
    file – the file to be processed
    """
    try:
        _, file_extension = os.path.splitext(file.filename)
        file_copy_name_without_ext = datetime.now().strftime(DATE_TIME_FORMAT_FILE)
        file_copy_name_with_ext = file_copy_name_without_ext + file_extension
        file_copy_directory = FILES_DIR + '/'
        file_copy_full_path = file_copy_directory + file_copy_name_with_ext

        # Write incoming audio to our local volume for further processing
        with open(file_copy_full_path, 'wb+') as buffer:
            shutil.copyfileobj(file.file, buffer)

        assert os.path.exists(file_copy_full_path), "Something went wrong while processing the file."

        return FileCopyResult(file_copy_name_with_ext=file_copy_name_with_ext,
                              file_copy_full_path=file_copy_full_path,
                              file_copies=[file_copy_full_path],
                              file_copy_directory=file_copy_directory,
                              file_copy_name_without_ext=file_copy_name_without_ext)
    finally:
        await file.close()

async def clean_up_files(
    files
):
    """
    Cleans up the incoming set of files from the local directory.

    Arguments:
    files – the set of files to be cleaned up
    """
    for file in files:
        if os.path.exists(file):
            os.remove(file)
