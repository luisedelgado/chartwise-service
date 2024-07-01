from fastapi import File, UploadFile

from ...api.auth_base_class import AuthManagerBaseClass
from ...api.image_processing_base_class import ImageProcessingManagerBaseClass

class FakeImageProcessingManager(ImageProcessingManagerBaseClass):

    FAKE_DOCUMENT_ID = "12345"
    FAKE_TEXTRACT_RESULT = '''A frog leaping upward off his lily pad is pulled downward by gravity and 
    lands on another lily pad instead of continuing on in a straight line.'''

    async def upload_image_for_textraction(self,
                                           auth_manager: AuthManagerBaseClass,
                                           image: UploadFile = File(...)) -> str:
        return self.FAKE_DOCUMENT_ID

    def extract_text(self, document_id: str) -> str:
        if document_id != self.FAKE_DOCUMENT_ID:
            raise Exception("Invalid document id")
        return self.FAKE_TEXTRACT_RESULT
