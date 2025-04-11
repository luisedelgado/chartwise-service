from abc import ABC, abstractmethod
from typing import Tuple

class DocupandaBaseClass(ABC):

    @abstractmethod
    async def upload_image(image_filepath: str,
                           image_filename: str) -> str:
        """
        Uploads an image for future textraction. Returns the job id.

        Arguments:
        image_filepath – the local filepath for the image that will be uploaded.
        image_filename – the file name of the image that will be uploaded.
        """
        pass

    @abstractmethod
    async def retrieve_text_from_document(document_id) -> Tuple[int, str]:
        """
        Perform textraction from an incoming document_id, and returns the resulting status code and text.

        Arguments:
        document_id – the document id to be textracted.
        """
        pass
