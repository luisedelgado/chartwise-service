from typing import Tuple

from ..api.docupanda_base_class import DocupandaBaseClass

class FakeDocupandaClient(DocupandaBaseClass):

    retrieving_non_existing_doc_id = False
    return_processing_status_code = False

    async def upload_image(
        self,
        image_filepath: str,
        image_filename: str
    ) -> str:
        return "Fake ID"

    async def retrieve_text_from_document(
        self,
        document_id
    ) -> Tuple[int, str]:
        if self.return_processing_status_code:
            return 202, "Still processing"
        if self.retrieving_non_existing_doc_id:
            raise Exception("Non existent")

        return 200, "This is my fake textraction"
