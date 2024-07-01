from fastapi.testclient import TestClient

from ..managers.manager_factory import ManagerFactory
from ..routers.assistant_router import AssistantRouter
from ..routers.audio_processing_router import AudioProcessingRouter
from ..routers.image_processing_router import ImageProcessingRouter
from ..routers.security_router import SecurityRouter
from ..service_coordinator import EndpointServiceCoordinator

DUMMY_AUTH_COOKIE = ""
DUMMY_PATIENT_ID = "a789baad-6eb1-44f9-901e-f19d4da910ab"
DUMMY_PNG_FILENAME = "test2.png"
DUMMY_PDF_FILENAME = "test2.pdf"
DUMMY_PNG_FILE_LOCATION = "app/tests/data/test2.png"
DUMMY_PDF_FILE_LOCATION = "app/tests/data/test2.pdf"
IMAGE_PDF_FILETYPE = "application/pdf"
IMAGE_PNG_FILETYPE = "image/png"
DUMMY_THERAPIST_ID = "4987b72e-dcbb-41fb-96a6-bf69756942cc"
TEXT_PLAIN_FILETYPE = "text/plain"

environment = "testing"
auth_manager = ManagerFactory().create_auth_manager(environment)
auth_manager.auth_cookie = DUMMY_AUTH_COOKIE

assistant_manager = ManagerFactory.create_assistant_manager(environment)
audio_processing_manager = ManagerFactory.create_audio_processing_manager(environment)
image_processing_manager = ManagerFactory.create_image_processing_manager(environment)

coordinator = EndpointServiceCoordinator(environment=environment,
                                                    routers=[
                                                        AssistantRouter(environment=environment,
                                                                        auth_manager=auth_manager,
                                                                        assistant_manager=assistant_manager).router,
                                                        AudioProcessingRouter(auth_manager=auth_manager,
                                                                              assistant_manager=assistant_manager,
                                                                              audio_processing_manager=audio_processing_manager).router,
                                                        ImageProcessingRouter(auth_manager=auth_manager,
                                                                              image_processing_manager=image_processing_manager).router,
                                                        SecurityRouter(auth_manager=auth_manager).router,
                                                    ])
client = TestClient(coordinator.service_app)

class TestingHarness:

    # Image Processing Tests

    def test_invoke_image_upload_with_no_auth(self):
        files = {
            "image": (DUMMY_PDF_FILE_LOCATION, open(DUMMY_PDF_FILE_LOCATION, 'rb'), IMAGE_PDF_FILETYPE)
        }
        response = client.post(ImageProcessingRouter.IMAGE_UPLOAD_ENDPOINT,
                            data={"patient_id": DUMMY_PATIENT_ID, "therapist_id": DUMMY_THERAPIST_ID},
                            files=files)
        assert response.status_code == 401

    def test_invoke_image_upload_with_auth(self):
        files = {
            "image": (DUMMY_PDF_FILE_LOCATION, open(DUMMY_PDF_FILE_LOCATION, 'rb'), IMAGE_PDF_FILETYPE)
        }
        response = client.post(ImageProcessingRouter.IMAGE_UPLOAD_ENDPOINT,
                            data={"patient_id": DUMMY_PATIENT_ID, "therapist_id": DUMMY_THERAPIST_ID},
                            files=files,
                            cookies={
                                "authorization": DUMMY_AUTH_COOKIE,
                            })
        assert response.status_code == 200
        assert response.json() == {"document_id": image_processing_manager.FAKE_DOCUMENT_ID}

    # def test_invoke_endpoint_without_auth_token():
    #     response = client.post("/v1/sessions", json={})
    #     assert response.status_code == 401

    # def test_auth_token_endpoint():
    #     response = client.post("/v1/token", data={"username": "testonly",
    #                                               "password": os.getenv("FASTAPI_ENDPOINTS_TEST_PSWD")})
    #     assert response.status_code == 200

    #     local_token: str = response.json()['access_token']
    #     assert len(local_token) > 0

    # def test_upload_session_endpoint_with_missing_tokens():
    #     response = client.post("/v1/sessions",
    #                            headers={"Authorization": token},
    #                            json=__get_session_upload_payload("", ""))
    #     assert response.status_code == 400

    # def test_upload_session_endpoint_with_invalid_tokens():
    #     response = client.post("/v1/sessions",
    #                            headers={"Authorization": token},
    #                            json=__get_session_upload_payload("123", "123"))
    #     assert response.status_code == 400

    # def test_assistant_query_invalid_response_language_code():
    #     response = client.post("/v1/assistant-queries",
    #                            headers={"Authorization": token},
    #                            json=__get_assistant_queries_payload("123",
    #                                                                 "123",
    #                                                                 "kjhbvbkub"))
    #     assert response.status_code == 400

    # # Helper methods

    # def __get_session_upload_payload(access_token, refresh_token):
    #     return {
    #     "patient_id": "126b4c15-2301-48f4-9674-75ec9f1e707a",
    #     "therapist_id": "1e19ead4-8b30-4be8-898c-7b4356743a1b",
    #     "text": "The sky is blue today",
    #     "date": "05/30/2024",
    #     "datastore_access_token": access_token,
    #     "datastore_refresh_token": refresh_token
    #     }

    # def __get_assistant_queries_payload(access_token, refresh_token, language_code):
    #     return {
    #     "patient_id": "126b4c15-2301-48f4-9674-75ec9f1e707a",
    #     "therapist_id": "1e19ead4-8b30-4be8-898c-7b4356743a1b",
    #     "text": "What color is the sky today?",
    #     "response_language_code": language_code,
    #     "datastore_access_token": access_token,
    #     "datastore_refresh_token": refresh_token
    #     }
