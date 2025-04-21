import base64, os, requests

from fastapi import status
from portkey_ai import Portkey
from typing import Tuple

from ..api.docupanda_base_class import DocupandaBaseClass
from ...internal.monitoring_proxy import use_monitoring_proxy

class DocupandaClient(DocupandaBaseClass):

    async def upload_image(self,
                           image_filepath: str,
                           image_filename: str) -> str:
        base_url = os.getenv("DOCUPANDA_BASE_URL")
        document_endpoint = os.getenv("DOCUPANDA_DOCUMENT_ENDPOINT")
        pdf_extension = "pdf"
        file_name, _ = os.path.splitext(image_filename)

        payload = {"file": {
            "contents": base64.b64encode(open(image_filepath, 'rb').read()).decode(),
            "filename": file_name + pdf_extension
        }}

        if use_monitoring_proxy():
            portkey = Portkey(
                api_key=os.environ.get("PORTKEY_API_KEY"),
                virtual_key=os.environ.get("PORTKEY_DOCUPANDA_VIRTUAL_KEY"),
                custom_host=base_url,
                metadata={
                    "hidden_provider": "docupanda"
                }
            )
            response = portkey.post(document_endpoint, document=payload)
            response_as_dict = response.dict()
            doc_id = response_as_dict["documentId"]
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

        return doc_id

    async def retrieve_text_from_document(self, document_id) -> Tuple[int, str]:
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
                return response.status_code, None

            json_response = response.json()

            if json_response['status'] == 'processing':
                return status.HTTP_202_ACCEPTED, None

            text_sections = json_response['result']['pages'][0]['sections']
            full_text = ""
            for section in text_sections:
                full_text = " ".join([full_text, section['text']])
            return status.HTTP_200_OK, full_text
        except Exception as e:
            raise RuntimeError from e
