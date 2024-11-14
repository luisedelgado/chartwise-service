import os

from fastapi.testclient import TestClient

from ..dependencies.fake.fake_stripe_client import FakeStripeClient
from ..internal.dependency_container import dependency_container
from ..managers.auth_manager import AuthManager
from ..routers.payment_processing_router import PaymentProcessingRouter
from ..service_coordinator import EndpointServiceCoordinator

FAKE_PATIENT_ID = "a789baad-6eb1-44f9-901e-f19d4da910ab"
FAKE_THERAPIST_ID = "4987b72e-dcbb-41fb-96a6-bf69756942cc"
FAKE_SESSION_REPORT_ID = "09b6da8d-a58e-45e2-9022-7d58ca02266b"
FAKE_REFRESH_TOKEN = "3ac77394-86b5-42dc-be14-0b92414d8443"
FAKE_ACCESS_TOKEN = "884f507c-f391-4248-91c4-7c25a138633a"
FAKE_PRICE_ID = "5db60936-4a36-4487-8586-de4aef383a03"
ENVIRONMENT = os.environ.get("ENVIRONMENT")

class TestingHarnessPaymentProcessingRouter:

    def setup_method(self):
        # Clear out any old state between tests
        dependency_container._openai_client = None
        dependency_container._pinecone_client = None
        dependency_container._docupanda_client = None
        dependency_container._supabase_client_factory = None
        dependency_container._stripe_client = None
        dependency_container._testing_environment = "testing"

        self.fake_openai_client = dependency_container.inject_openai_client()
        self.fake_docupanda_client = dependency_container.inject_docupanda_client()
        self.fake_supabase_admin_client = dependency_container.inject_supabase_client_factory().supabase_admin_client()
        self.fake_stripe_client: FakeStripeClient = dependency_container.inject_stripe_client()
        self.fake_supabase_user_client = dependency_container.inject_supabase_client_factory().supabase_user_client(access_token=FAKE_ACCESS_TOKEN,
                                                                                                                 refresh_token=FAKE_REFRESH_TOKEN)
        self.fake_pinecone_client = dependency_container.inject_pinecone_client()
        self.fake_supabase_client_factory = dependency_container.inject_supabase_client_factory()
        self.auth_cookie, _ = AuthManager().create_auth_token(user_id=FAKE_THERAPIST_ID)
        coordinator = EndpointServiceCoordinator(routers=[PaymentProcessingRouter(environment=ENVIRONMENT).router],
                                                 environment=ENVIRONMENT)
        self.client = TestClient(coordinator.app)

    def test_invoke_generate_payment_session_without_auth_token(self):
        response = self.client.post(PaymentProcessingRouter.PAYMENT_SESSION_ENDPOINT,
                                    headers={
                                        "store-access-token": FAKE_ACCESS_TOKEN,
                                        "store-refresh-token": FAKE_REFRESH_TOKEN
                                    },
                                    json={
                                        "price_id": FAKE_PRICE_ID,
                                        "success_callback_url": "https://www.chartwise.ai/payment-success",
                                        "cancel_callback_url": "https://www.chartwise.ai",
                                    })
        assert response.status_code == 401

    def test_invoke_generate_payment_session_stripe_client_throws(self):
        self.fake_stripe_client.request_throws_exception = True
        response = self.client.post(PaymentProcessingRouter.PAYMENT_SESSION_ENDPOINT,
                                    cookies={
                                        "authorization": self.auth_cookie
                                    },
                                    headers={
                                        "store-access-token": FAKE_ACCESS_TOKEN,
                                        "store-refresh-token": FAKE_REFRESH_TOKEN
                                    },
                                    json={
                                        "price_id": FAKE_PRICE_ID,
                                        "success_callback_url": "https://www.chartwise.ai/payment-success",
                                        "cancel_callback_url": "https://www.chartwise.ai",
                                    })
        assert response.status_code == 417

    def test_invoke_generate_payment_session_stripe_client_returns_none(self):
        self.fake_stripe_client.request_returns_none = True
        response = self.client.post(PaymentProcessingRouter.PAYMENT_SESSION_ENDPOINT,
                                    cookies={
                                        "authorization": self.auth_cookie
                                    },
                                    headers={
                                        "store-access-token": FAKE_ACCESS_TOKEN,
                                        "store-refresh-token": FAKE_REFRESH_TOKEN
                                    },
                                    json={
                                        "price_id": FAKE_PRICE_ID,
                                        "success_callback_url": "https://www.chartwise.ai/payment-success",
                                        "cancel_callback_url": "https://www.chartwise.ai",
                                    })
        assert response.status_code == 417

    def test_invoke_generate_payment_session_stripe_client_returns_success(self):
        response = self.client.post(PaymentProcessingRouter.PAYMENT_SESSION_ENDPOINT,
                                    cookies={
                                        "authorization": self.auth_cookie
                                    },
                                    headers={
                                        "store-access-token": FAKE_ACCESS_TOKEN,
                                        "store-refresh-token": FAKE_REFRESH_TOKEN
                                    },
                                    json={
                                        "price_id": FAKE_PRICE_ID,
                                        "success_callback_url": "https://www.chartwise.ai/payment-success",
                                        "cancel_callback_url": "https://www.chartwise.ai",
                                    })
        assert response.status_code == 200
        assert "payment_session_url" in response.json()
