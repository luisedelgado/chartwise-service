from ..api.docupanda_base_class import DocuPandaBaseClass
from ...managers.auth_manager import AuthManager

class DocuPandaBaseClass(DocuPandaBaseClass):

    def upload_image(self,
                     auth_manager: AuthManager,
                     image_filepath: str,
                     image_filename: str) -> str:
        pass

    def retrieve_text_from_document(self, document_id) -> str:
        pass
