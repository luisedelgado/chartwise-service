from fastapi import File, UploadFile

from ...api.image_processing_base_class import ImageProcessingManagerBaseClass

class FakeImageProcessingManager(ImageProcessingManagerBaseClass):
    async def upload_image_for_textraction(self, image: UploadFile = File(...)) -> str:
        return ""

    def extract_text(document_id: str) -> str:
        return ""
