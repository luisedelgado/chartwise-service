from abc import ABC

from fastapi import File, UploadFile

class ImageProcessingManagerBaseClass(ABC):
    """
    Uploads an image file to the textraction service.
    Returns an ID associated with the textraction job.
    Arguments:
    image – the image to be uploaded.
    """
    async def upload_image_for_textraction(image: UploadFile = File(...)) -> str:
        pass

    """
    Returns a textraction result based on the incoming id.
    Arguments:
    document_id – the id of the document that was processed for textraction.
    """
    def extract_text(document_id: str) -> str:
        pass
