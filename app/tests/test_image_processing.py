from fastapi.testclient import TestClient

from ..routers.image_processing_router import ImageProcessingRouter
from ..routers.security_router import SecurityRouter
from ..service_coordinator import EndpointServiceCoordinator

SOAP_TEMPLATE = "soap"
FAKE_AUTH_COOKIE = "my-auth-cookie"
FAKE_PATIENT_ID = "a789baad-6eb1-44f9-901e-f19d4da910ab"
FAKE_THERAPIST_ID = "4987b72e-dcbb-41fb-96a6-bf69756942cc"
DUMMY_PDF_FILE_LOCATION = "app/tests/data/test2.pdf"
IMAGE_PDF_FILETYPE = "application/pdf"
ENVIRONMENT = "testing"

class TestingHarnessImageProcessingRouter:

    ...
    # def setup_method(self):
    #     self.auth_manager = ManagerFactory().create_auth_manager(ENVIRONMENT)
    #     self.auth_manager.auth_cookie = FAKE_AUTH_COOKIE

    #     self.assistant_manager = ManagerFactory.create_assistant_manager(ENVIRONMENT)
    #     self.audio_processing_manager = ManagerFactory.create_audio_processing_manager(ENVIRONMENT)
    #     self.image_processing_manager = ManagerFactory.create_image_processing_manager(ENVIRONMENT)

    #     coordinator = EndpointServiceCoordinator(routers=[ImageProcessingRouter(assistant_manager=self.assistant_manager,
    #                                                                             auth_manager=self.auth_manager,
    #                                                                             image_processing_manager=self.image_processing_manager).router,
    #                                                       SecurityRouter(auth_manager=self.auth_manager,
    #                                                                      assistant_manager=self.assistant_manager).router],
    #                                              environment="dev")
    #     self.client = TestClient(coordinator.app)

    # def test_invoke_image_upload_with_no_auth(self):
    #     files = {
    #         "image": (DUMMY_PDF_FILE_LOCATION, open(DUMMY_PDF_FILE_LOCATION, 'rb'), IMAGE_PDF_FILETYPE)
    #     }
    #     response = self.client.post(ImageProcessingRouter.IMAGE_UPLOAD_ENDPOINT,
    #                                 data={"patient_id": FAKE_PATIENT_ID,
    #                                       "therapist_id": FAKE_THERAPIST_ID},
    #                                 files=files)
    #     assert response.status_code == 401

    # def test_invoke_image_upload_with_auth(self):
    #     files = {
    #         "image": (DUMMY_PDF_FILE_LOCATION, open(DUMMY_PDF_FILE_LOCATION, 'rb'), IMAGE_PDF_FILETYPE)
    #     }
    #     response = self.client.post(ImageProcessingRouter.IMAGE_UPLOAD_ENDPOINT,
    #                                 data={"patient_id": FAKE_PATIENT_ID, "therapist_id": self.auth_manager.FAKE_USER_ID},
    #                                 files=files,
    #                                 cookies={
    #                                     "authorization": FAKE_AUTH_COOKIE,
    #                                 })
    #     assert response.status_code == 200
    #     assert response.json() == {"document_id": self.image_processing_manager.FAKE_DOCUMENT_ID}
    #     assert response.cookies.get("authorization") == self.auth_manager.FAKE_AUTH_TOKEN
    #     assert response.cookies.get("session_id") == self.auth_manager.FAKE_SESSION_ID

    # def test_invoke_textraction_with_no_auth(self):
    #     response = self.client.get(ImageProcessingRouter.TEXT_EXTRACTION_ENDPOINT,
    #                                 params={
    #                                     "patient_id": FAKE_PATIENT_ID,
    #                                     "therapist_id": FAKE_THERAPIST_ID,
    #                                     "document_id": "12345",
    #                                     "template": SOAP_TEMPLATE
    #                                     })
    #     assert response.status_code == 401

    # def test_invoke_textraction_with_auth_but_empty_doc_id(self):
    #     response = self.client.get(ImageProcessingRouter.TEXT_EXTRACTION_ENDPOINT,
    #                                 params={
    #                                     "patient_id": FAKE_PATIENT_ID,
    #                                     "therapist_id": FAKE_THERAPIST_ID,
    #                                     "document_id": "",
    #                                     "template": SOAP_TEMPLATE
    #                                     },
    #                                     cookies={
    #                                         "authorization": FAKE_AUTH_COOKIE,
    #                                         "datastore_access_token": self.auth_manager.FAKE_DATASTORE_ACCESS_TOKEN,
    #                                         "datastore_refresh_token": self.auth_manager.FAKE_DATASTORE_REFRESH_TOKEN
    #                                     },)
    #     assert response.status_code == 400

    # def test_invoke_textraction_with_auth_but_invalid_doc_id(self):
    #     response = self.client.get(ImageProcessingRouter.TEXT_EXTRACTION_ENDPOINT,
    #                            params={
    #                                "patient_id": FAKE_PATIENT_ID,
    #                                "therapist_id": FAKE_THERAPIST_ID,
    #                                "document_id": "000",
    #                                 "template": SOAP_TEMPLATE
    #                             },
    #                             cookies={
    #                                 "authorization": FAKE_AUTH_COOKIE,
    #                                 "datastore_access_token": self.auth_manager.FAKE_DATASTORE_ACCESS_TOKEN,
    #                                 "datastore_refresh_token": self.auth_manager.FAKE_DATASTORE_REFRESH_TOKEN
    #                             },)
    #     assert response.status_code == 400

    # def test_invoke_free_form_textraction_with_auth_and_valid_doc_id(self):
    #     response = self.client.get(ImageProcessingRouter.TEXT_EXTRACTION_ENDPOINT,
    #                            params={
    #                                "patient_id": FAKE_PATIENT_ID,
    #                                "therapist_id": self.auth_manager.FAKE_USER_ID,
    #                                "document_id": "12345",
    #                                 "template": "free_form"
    #                             },
    #                             cookies={
    #                                 "authorization": FAKE_AUTH_COOKIE,
    #                             })
    #     assert response.status_code == 200
    #     assert "textraction" in response.json()
    #     assert response.cookies.get("authorization") == self.auth_manager.FAKE_AUTH_TOKEN
    #     assert response.cookies.get("session_id") == self.auth_manager.FAKE_SESSION_ID

    # def test_invoke_soap_textraction_with_auth_and_valid_doc_id(self):
    #     response = self.client.get(ImageProcessingRouter.TEXT_EXTRACTION_ENDPOINT,
    #                            params={
    #                                "patient_id": FAKE_PATIENT_ID,
    #                                "therapist_id": self.auth_manager.FAKE_USER_ID,
    #                                "document_id": "12345",
    #                                 "template": SOAP_TEMPLATE
    #                             },
    #                             cookies={
    #                                 "authorization": FAKE_AUTH_COOKIE,
    #                             })
    #     assert response.status_code == 200
    #     assert "soap_textraction" in response.json()
    #     assert response.cookies.get("authorization") == self.auth_manager.FAKE_AUTH_TOKEN
    #     assert response.cookies.get("session_id") == self.auth_manager.FAKE_SESSION_ID
