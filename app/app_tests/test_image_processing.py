from datetime import timedelta

from fastapi.testclient import TestClient

from ..dependencies.fake.fake_async_openai import FakeAsyncOpenAI
from ..dependencies.fake.fake_docupanda_client import FakeDocupandaClient
from ..dependencies.fake.fake_supabase_client import FakeSupabaseClient
from ..dependencies.fake.fake_supabase_client_factory import FakeSupabaseClientFactory
from ..internal.router_dependencies import RouterDependencies
from ..managers.assistant_manager import AssistantManager
from ..managers.image_processing_manager import ImageProcessingManager
from ..managers.auth_manager import AuthManager
from ..routers.image_processing_router import ImageProcessingRouter
from ..service_coordinator import EndpointServiceCoordinator

FAKE_PATIENT_ID = "a789baad-6eb1-44f9-901e-f19d4da910ab"
FAKE_THERAPIST_ID = "4987b72e-dcbb-41fb-96a6-bf69756942cc"
FAKE_SESSION_REPORT_ID = "09b6da8d-a58e-45e2-9022-7d58ca02266b"
FAKE_REFRESH_TOKEN = "3ac77394-86b5-42dc-be14-0b92414d8443"
FAKE_ACCESS_TOKEN = "884f507c-f391-4248-91c4-7c25a138633a"
TZ_IDENTIFIER = "UTC"
ENVIRONMENT = "testing"
DUMMY_PDF_FILE_LOCATION = "app/app_tests/data/test2.pdf"
DUMMY_PNG_FILE_LOCATION = "app/app_tests/data/test2.png"
IMAGE_PDF_FILETYPE = "application/pdf"
IMAGE_PNG_FILETYPE = "image/png"

# SOAP_TEMPLATE = "soap"
# FAKE_AUTH_COOKIE = "my-auth-cookie"
# FAKE_PATIENT_ID = "a789baad-6eb1-44f9-901e-f19d4da910ab"
# FAKE_THERAPIST_ID = "4987b72e-dcbb-41fb-96a6-bf69756942cc"
# ENVIRONMENT = "testing"

class TestingHarnessImageProcessingRouter:

    def setup_method(self):
        self.auth_manager = AuthManager()
        self.assistant_manager = AssistantManager()
        self.image_processing_manager = ImageProcessingManager()
        self.fake_openai_client = FakeAsyncOpenAI()
        self.fake_docupanda_client = FakeDocupandaClient()
        self.fake_supabase_admin_client = FakeSupabaseClient()
        self.fake_supabase_user_client = FakeSupabaseClient()
        self.fake_supabase_client_factory = FakeSupabaseClientFactory(fake_supabase_admin_client=self.fake_supabase_admin_client,
                                                                      fake_supabase_user_client=self.fake_supabase_user_client)
        self.auth_cookie = self.auth_manager.create_access_token(data={"sub": FAKE_THERAPIST_ID},
                                                                 expires_delta=timedelta(minutes=5))

        coordinator = EndpointServiceCoordinator(routers=[ImageProcessingRouter(auth_manager=self.auth_manager,
                                                                                assistant_manager=self.assistant_manager,
                                                                                image_processing_manager=self.image_processing_manager,
                                                                                router_dependencies=RouterDependencies(supabase_client_factory=self.fake_supabase_client_factory,
                                                                                                                       openai_client=self.fake_openai_client,
                                                                                                                       docupanda_client=self.fake_docupanda_client)).router],
                                                 environment=ENVIRONMENT)
        self.client = TestClient(coordinator.app)

    def test_invoke_image_upload_with_no_auth(self):
        files = {
            "image": (DUMMY_PDF_FILE_LOCATION, open(DUMMY_PDF_FILE_LOCATION, 'rb'), IMAGE_PDF_FILETYPE)
        }
        response = self.client.post(ImageProcessingRouter.IMAGE_UPLOAD_ENDPOINT,
                                    data={"patient_id": FAKE_PATIENT_ID,
                                          "therapist_id": FAKE_THERAPIST_ID},
                                    files=files)
        assert response.status_code == 401

    def test_invoke_png_image_upload_success(self):
        self.fake_supabase_user_client.return_authenticated_session = True
        self.fake_supabase_user_client.fake_access_token = FAKE_ACCESS_TOKEN
        self.fake_supabase_user_client.fake_refresh_token = FAKE_REFRESH_TOKEN
        self.fake_supabase_user_client.select_returns_data = True
        files = {
            "image": (DUMMY_PNG_FILE_LOCATION, open(DUMMY_PNG_FILE_LOCATION, 'rb'), IMAGE_PNG_FILETYPE)
        }
        response = self.client.post(ImageProcessingRouter.IMAGE_UPLOAD_ENDPOINT,
                                    data={
                                        "patient_id": FAKE_PATIENT_ID,
                                        "therapist_id": FAKE_THERAPIST_ID
                                    },
                                    files=files,
                                    cookies={
                                        "authorization": self.auth_cookie,
                                    })
        assert response.status_code == 200
        assert "document_id" in response.json()

    def test_invoke_pdf_image_upload_success(self):
        self.fake_supabase_user_client.return_authenticated_session = True
        self.fake_supabase_user_client.fake_access_token = FAKE_ACCESS_TOKEN
        self.fake_supabase_user_client.fake_refresh_token = FAKE_REFRESH_TOKEN
        self.fake_supabase_user_client.select_returns_data = True
        files = {
            "image": (DUMMY_PDF_FILE_LOCATION, open(DUMMY_PDF_FILE_LOCATION, 'rb'), IMAGE_PDF_FILETYPE)
        }
        response = self.client.post(ImageProcessingRouter.IMAGE_UPLOAD_ENDPOINT,
                                    data={
                                        "patient_id": FAKE_PATIENT_ID,
                                        "therapist_id": FAKE_THERAPIST_ID
                                    },
                                    files=files,
                                    cookies={
                                        "authorization": self.auth_cookie,
                                    })
        assert response.status_code == 200
        assert "document_id" in response.json()

    def test_invoke_textraction_with_no_auth(self):
        response = self.client.get(ImageProcessingRouter.TEXT_EXTRACTION_ENDPOINT,
                                    params={
                                        "patient_id": FAKE_PATIENT_ID,
                                        "therapist_id": FAKE_THERAPIST_ID,
                                        "document_id": "12345",
                                        "template": "free_form"
                                        })
        assert response.status_code == 401

    def test_invoke_textraction_with_auth_but_empty_doc_id(self):
        response = self.client.get(ImageProcessingRouter.TEXT_EXTRACTION_ENDPOINT,
                                    params={
                                        "patient_id": FAKE_PATIENT_ID,
                                        "therapist_id": FAKE_THERAPIST_ID,
                                        "document_id": "",
                                        "template": "free_form"
                                        },
                                        cookies={
                                            "authorization": self.auth_cookie,
                                        },)
        assert response.status_code == 400

    def test_invoke_textraction_with_auth_but_nonexistent_doc_id(self):
        self.fake_docupanda_client.retrieving_non_existing_doc_id = True
        response = self.client.get(ImageProcessingRouter.TEXT_EXTRACTION_ENDPOINT,
                               params={
                                   "patient_id": FAKE_PATIENT_ID,
                                   "therapist_id": FAKE_THERAPIST_ID,
                                   "document_id": "000",
                                    "template": "free_form"
                                },
                                cookies={
                                    "authorization": self.auth_cookie,
                                },)
        assert response.status_code == 400

    def test_invoke_free_form_textraction_with_auth_and_valid_doc_id(self):
        response = self.client.get(ImageProcessingRouter.TEXT_EXTRACTION_ENDPOINT,
                               params={
                                   "patient_id": FAKE_PATIENT_ID,
                                   "therapist_id": FAKE_THERAPIST_ID,
                                   "document_id": "12345",
                                    "template": "free_form"
                                },
                                cookies={
                                    "authorization": self.auth_cookie,
                                })
        assert response.status_code == 200
        assert "textraction" in response.json()

    def test_invoke_soap_textraction_with_auth_and_valid_doc_id(self):
        response = self.client.get(ImageProcessingRouter.TEXT_EXTRACTION_ENDPOINT,
                               params={
                                   "patient_id": FAKE_PATIENT_ID,
                                   "therapist_id": FAKE_THERAPIST_ID,
                                   "document_id": "12345",
                                    "template": "soap"
                                },
                                cookies={
                                    "authorization": self.auth_cookie,
                                })
        assert response.status_code == 200
        assert "soap_textraction" in response.json()
