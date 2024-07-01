from abc import ABC

from fastapi import File, UploadFile

from ..api.auth_base_class import AuthManagerBaseClass

class ImageProcessingManagerBaseClass(ABC):
    """
    Uploads an image file to the textraction service.
    Returns an ID associated with the textraction job.
    Arguments:
    auth_manager – the auth manager to be leveraged internally.
    image – the image to be uploaded.
    """
    async def upload_image_for_textraction(auth_manager: AuthManagerBaseClass,
                                           image: UploadFile = File(...)) -> str:
        pass

    """
    Returns a textraction result based on the incoming id.
    Arguments:
    document_id – the id of the document that was processed for textraction.
    """
    def extract_text(document_id: str) -> str:
        pass
