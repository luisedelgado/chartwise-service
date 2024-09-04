from abc import ABC
from typing import Tuple

from ...managers.auth_manager import AuthManager

class DocupandaBaseClass(ABC):

    """
    Uploads an image for future textraction. Returns the job id.

    Arguments:
    auth_manager – the auth manager to be leveraged internally.
    image_filepath – the local filepath for the image that will be uploaded.
    image_filename – the file name of the image that will be uploaded.
    """
    async def upload_image(auth_manager: AuthManager,
                           image_filepath: str,
                           image_filename: str) -> str:
        pass

    """
    Perform textraction from an incoming document_id, and returns the resulting status code and text.

    Arguments:
    document_id – the document id to be textracted.
    """
    async def retrieve_text_from_document(document_id) -> Tuple[int, str]:
        pass
