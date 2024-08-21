from ..api.docupanda_base_class import DocupandaBaseClass
from ...managers.auth_manager import AuthManager

class FakeDocupandaClient(DocupandaBaseClass):

    retrieving_non_existing_doc_id = False

    async def upload_image(self,
                           auth_manager: AuthManager,
                           image_filepath: str,
                           image_filename: str) -> str:
        return "Fake ID"

    async def retrieve_text_from_document(self, document_id) -> str:
        if self.retrieving_non_existing_doc_id:
            raise Exception("Non existent")

        return "This is my fake textraction"
