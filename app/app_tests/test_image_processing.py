import os

from fastapi.testclient import TestClient

from ..dependencies.dependency_container import dependency_container
from ..internal.schemas import SessionProcessingStatus
from ..managers.auth_manager import AuthManager
from ..routers.image_processing_router import ImageProcessingRouter
from ..service_coordinator import EndpointServiceCoordinator

FAKE_PATIENT_ID = "a789baad-6eb1-44f9-901e-f19d4da910ab"
FAKE_THERAPIST_ID = "4987b72e-dcbb-41fb-96a6-bf69756942cc"
FAKE_SESSION_REPORT_ID = "09b6da8d-a58e-45e2-9022-7d58ca02266b"
FAKE_REFRESH_TOKEN = "3ac77394-86b5-42dc-be14-0b92414d8443"
FAKE_ACCESS_TOKEN = "884f507c-f391-4248-91c4-7c25a138633a"
TZ_IDENTIFIER = "UTC"
DUMMY_PDF_FILE_LOCATION = "app/app_tests/data/test2.pdf"
DUMMY_PNG_FILE_LOCATION = "app/app_tests/data/test2.png"
IMAGE_PDF_FILETYPE = "application/pdf"
IMAGE_PNG_FILETYPE = "image/png"
ENVIRONMENT = os.environ.get("ENVIRONMENT")

class TestingHarnessImageProcessingRouter:

    def setup_method(self):
        # Clear out any old state between tests
        dependency_container._openai_client = None
        dependency_container._pinecone_client = None
        dependency_container._docupanda_client = None
        dependency_container._stripe_client = None
        dependency_container._resend_client = None
        dependency_container._influx_client = None
        dependency_container._testing_environment = "testing"

        self.fake_openai_client = dependency_container.inject_openai_client()
        self.fake_docupanda_client = dependency_container.inject_docupanda_client()
        self.fake_pinecone_client = dependency_container.inject_pinecone_client()
        self.auth_cookie, _ = AuthManager().create_auth_token(user_id=FAKE_THERAPIST_ID)
        coordinator = EndpointServiceCoordinator(routers=[ImageProcessingRouter(environment=ENVIRONMENT).router],
                                                 environment=ENVIRONMENT)
        self.client = TestClient(coordinator.app)

    def test_invoke_textraction_with_no_auth(self):
        files = {
            "image": (DUMMY_PDF_FILE_LOCATION, open(DUMMY_PDF_FILE_LOCATION, 'rb'), IMAGE_PDF_FILETYPE)
        }
        response = self.client.post(ImageProcessingRouter.TEXT_EXTRACTION_ENDPOINT,
                                    files=files,
                                    data={
                                        "patient_id": FAKE_PATIENT_ID,
                                        "session_date": "01-01-2000",
                                        "client_timezone_identifier": "UTC",
                                        "template": "soap"
                                    })
        assert response.status_code == 401

    def test_invoke_textraction_with_auth_but_invalid_timezone(self):
        files = {
            "image": (DUMMY_PNG_FILE_LOCATION, open(DUMMY_PNG_FILE_LOCATION, 'rb'), IMAGE_PNG_FILETYPE)
        }
        response = self.client.post(ImageProcessingRouter.TEXT_EXTRACTION_ENDPOINT,
                                    files=files,
                                    data={
                                        "patient_id": FAKE_PATIENT_ID,
                                        "session_date": "01-01-2000",
                                        "client_timezone_identifier": "UTCfdsgdsghds",
                                        "template": "soap"
                                    },
                                    headers={
                                        "store-access-token": FAKE_ACCESS_TOKEN,
                                        "store-refresh-token": FAKE_REFRESH_TOKEN
                                    },
                                    cookies={
                                        "authorization": self.auth_cookie,
                                    })
        assert response.status_code == 400

    def test_invoke_png_textraction_soap_format_success(self):
        files = {
            "image": (DUMMY_PNG_FILE_LOCATION, open(DUMMY_PNG_FILE_LOCATION, 'rb'), IMAGE_PNG_FILETYPE)
        }
        response = self.client.post(ImageProcessingRouter.TEXT_EXTRACTION_ENDPOINT,
                                    files=files,
                                    data={
                                        "patient_id": FAKE_PATIENT_ID,
                                        "session_date": "01-01-2000",
                                        "client_timezone_identifier": "UTC",
                                        "template": "soap"
                                    },
                                    headers={
                                        "store-access-token": FAKE_ACCESS_TOKEN,
                                        "store-refresh-token": FAKE_REFRESH_TOKEN
                                    },
                                    cookies={
                                        "authorization": self.auth_cookie
                                    })
        assert response.status_code == 200
        assert "session_report_id" in response.json()

    def test_invoke_png_textraction_free_format_success(self):
        files = {
            "image": (DUMMY_PNG_FILE_LOCATION, open(DUMMY_PNG_FILE_LOCATION, 'rb'), IMAGE_PNG_FILETYPE)
        }
        response = self.client.post(ImageProcessingRouter.TEXT_EXTRACTION_ENDPOINT,
                                    files=files,
                                    data={
                                        "patient_id": FAKE_PATIENT_ID,
                                        "session_date": "01-01-2000",
                                        "client_timezone_identifier": "UTC",
                                        "template": "free_form"
                                    },
                                    headers={
                                        "store-access-token": FAKE_ACCESS_TOKEN,
                                        "store-refresh-token": FAKE_REFRESH_TOKEN
                                    },
                                    cookies={
                                        "authorization": self.auth_cookie
                                    })
        assert response.status_code == 200
        assert "session_report_id" in response.json()

    def test_invoke_pdf_textraction_success(self):
        files = {
            "image": (DUMMY_PDF_FILE_LOCATION, open(DUMMY_PDF_FILE_LOCATION, 'rb'), IMAGE_PDF_FILETYPE)
        }
        response = self.client.post(ImageProcessingRouter.TEXT_EXTRACTION_ENDPOINT,
                                    files=files,
                                    data={
                                        "patient_id": FAKE_PATIENT_ID,
                                        "session_date": "01-01-2000",
                                        "client_timezone_identifier": "UTC",
                                        "template": "soap"
                                    },
                                    headers={
                                        "store-access-token": FAKE_ACCESS_TOKEN,
                                        "store-refresh-token": FAKE_REFRESH_TOKEN
                                    },
                                    cookies={
                                        "authorization": self.auth_cookie
                                    })
        assert response.status_code == 200
        assert "session_report_id" in response.json()
