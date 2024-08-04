import os

from fastapi import (File, UploadFile)

from ..dependencies.api.docupanda_base_class import DocupandaBaseClass
from ..internal.utilities import file_copiers
from ..managers.auth_manager import AuthManager

class ImageProcessingManager:

    async def upload_image_for_textraction(self,
                                           auth_manager: AuthManager,
                                           docupanda_client: DocupandaBaseClass,
                                           image: UploadFile = File(...)) -> str:
        files_to_clean = None
        try:
            image_copy_result: file_copiers.FileCopyResult = await file_copiers.make_image_pdf_copy(image)
            image_copy_path = image_copy_result.file_copy_full_path
            files_to_clean = image_copy_result.file_copies

            if not os.path.exists(image_copy_path):
                await file_copiers.clean_up_files(files_to_clean)
                raise Exception("Something went wrong while processing the image.")

            doc_id = docupanda_client.upload_image(auth_manager=auth_manager,
                                                   image_filepath=image_copy_path,
                                                   image_filename=image.filename)

            # Clean up the image copies we used for processing.
            await file_copiers.clean_up_files(files_to_clean)

            return doc_id
        except Exception as e:
            await file_copiers.clean_up_files(files_to_clean)
            raise Exception(str(e))

    def extract_text(self,
                     docupanda_client: DocupandaBaseClass,
                     document_id: str) -> str:
        try:
            return docupanda_client.retrieve_text_from_document(document_id)
        except Exception as e:
            raise Exception(e)
