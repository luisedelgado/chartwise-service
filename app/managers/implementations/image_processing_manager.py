import base64, os, requests

from fastapi import (File, HTTPException, status, UploadFile)
from portkey_ai import Portkey

from ...api.image_processing_base_class import ImageProcessingManagerBaseClass
from ...api.auth_base_class import AuthManagerBaseClass
from ...internal.utilities import file_copiers

class ImageProcessingManager(ImageProcessingManagerBaseClass):

    async def upload_image_for_textraction(self,
                                           auth_manager: AuthManagerBaseClass,
                                           image: UploadFile = File(...)) -> str:
        files_to_clean = None
        try:
            base_url = os.getenv("DOCUPANDA_BASE_URL")
            document_endpoint = os.getenv("DOCUPANDA_DOCUMENT_ENDPOINT")
            pdf_extension = "pdf"
            file_name, _ = os.path.splitext(image.filename)

            image_copy_result: file_copiers.FileCopyResult = await file_copiers.make_image_pdf_copy(image)
            image_copy_path = image_copy_result.file_copy_full_path
            files_to_clean = image_copy_result.file_copies

            if not os.path.exists(image_copy_path):
                await file_copiers.clean_up_files(files_to_clean)
                raise Exception("Something went wrong while processing the image.")

            # Send to DocuPanda
            payload = {"file": {
                "contents": base64.b64encode(open(image_copy_path, 'rb').read()).decode(),
                "filename": file_name + pdf_extension
            }}

            if auth_manager.is_monitoring_proxy_reachable():
                portkey = Portkey(
                    api_key=os.environ.get("PORTKEY_API_KEY"),
                    virtual_key=os.environ.get("PORTKEY_DOCUPANDA_VIRTUAL_KEY"),
                    custom_host=base_url
                )
                response = portkey.post('/document', document=payload)
                response_as_dict = response.dict()
                doc_id = response_as_dict["documentId"]
                assert response_as_dict['status'].lower() == "processing"
            else:
                headers = {
                    "accept": "application/json",
                    "content-type": "application/json",
                    "X-API-Key": os.getenv("DOCUPANDA_API_KEY"),
                }
                url = base_url + document_endpoint
                response = requests.post(url, json={"document": payload}, headers=headers)
                assert response.status_code == 200, f"Got HTTP code {response.status} while uploading the image"
                doc_id = response.json()['documentId']

            # Clean up the image copies we used for processing.
            await file_copiers.clean_up_files(files_to_clean)

            return doc_id
        except Exception as e:
            await file_copiers.clean_up_files(files_to_clean)
            raise Exception(str(e))

    def extract_text(self, document_id: str) -> str:
        try:
            base_url = os.getenv("DOCUPANDA_BASE_URL")
            document_endpoint = os.getenv("DOCUPANDA_DOCUMENT_ENDPOINT")
            url = base_url + document_endpoint + "/" + document_id

            headers = {
                "accept": "application/json",
                "X-API-Key": os.getenv("DOCUPANDA_API_KEY")
            }

            response = requests.get(url, headers=headers)

            if response.status_code != status.HTTP_200_OK:
                raise HTTPException(status_code=response.status_code,
                                    detail=response.text)

            json_response = response.json()

            if json_response['status'] == 'processing':
                raise HTTPException(status_code=status.HTTP_204_NO_CONTENT,
                                    detail="Image textraction is still being processed")

            text_sections = json_response['result']['pages'][0]['sections']
            full_text = ""
            for section in text_sections:
                full_text = full_text + section['text'] + " "

            return full_text
        except Exception as e:
            raise Exception(e)
