import os, shutil

from datetime import datetime

from fastapi import (File, UploadFile)
from PIL import Image

"""
A result representation of an image-copy operation.
"""
class ImageCopyResult():
    def __init__(self, image_copy_path: str, file_copies: list):
        self.image_copy_path = image_copy_path
        self.file_copies = file_copies

"""
Returns a PDF copy of the incoming image file.

Arguments:
image  – the image file to be processed
"""
def make_image_pdf_copy(image: UploadFile = File(...)) -> ImageCopyResult:
    _, file_extension = os.path.splitext(image.filename)

    # Format name to be used for image copy using current timestamp
    files_dir = 'app/files'
    pdf_extension = '.pdf'
    image_copy_bare_name = datetime.now().strftime("%d-%m-%Y-%H-%M-%S")
    image_copy_path = files_dir + '/' + image_copy_bare_name + file_extension
    image_copy_pdf_path = files_dir + '/' + image_copy_bare_name + pdf_extension
    files_to_clean = [image_copy_path]

    # Write incoming image to our local volume for further processing
    with open(image_copy_path, 'wb+') as buffer:
        shutil.copyfileobj(image.file, buffer)

    # Convert to PDF if necessary
    if file_extension.lower() != pdf_extension:
        Image.open(image_copy_path).convert('RGB').save(image_copy_pdf_path)
        files_to_clean.append(image_copy_pdf_path)

    return ImageCopyResult(image_copy_path=image_copy_pdf_path,
                           file_copies=files_to_clean)

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
