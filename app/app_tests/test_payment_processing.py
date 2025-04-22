import os

from fastapi.testclient import TestClient

from ..dependencies.fake.fake_stripe_client import FakeStripeClient
from ..dependencies.dependency_container import dependency_container
from ..managers.auth_manager import AuthManager
from ..routers.payment_processing_router import UpdateSubscriptionBehavior, PaymentProcessingRouter
from ..service_coordinator import EndpointServiceCoordinator

FAKE_PATIENT_ID = "a789baad-6eb1-44f9-901e-f19d4da910ab"
FAKE_THERAPIST_ID = "4987b72e-dcbb-41fb-96a6-bf69756942cc"
FAKE_SESSION_REPORT_ID = "09b6da8d-a58e-45e2-9022-7d58ca02266b"
FAKE_REFRESH_TOKEN = "3ac77394-86b5-42dc-be14-0b92414d8443"
FAKE_ACCESS_TOKEN = "884f507c-f391-4248-91c4-7c25a138633a"
FAKE_PRICE_ID = "5db60936-4a36-4487-8586-de4aef383a03"
FAKE_CUSTOMER_ID = "ea549096-41a1-4857-be1c-5f2b57a72123"
FAKE_SUBSCRIPTION_ID = "ea549096-41a1-4857-be1c-5f2b57a72123"
FAKE_PRODUCT_ID = "5db60936-4a36-4487-8586-de4aef383a03"
ENVIRONMENT = os.environ.get("ENVIRONMENT")

class TestingHarnessPaymentProcessingRouter:

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
        self.fake_stripe_client: FakeStripeClient = dependency_container.inject_stripe_client()
        self.fake_pinecone_client = dependency_container.inject_pinecone_client()
        self.auth_cookie, _ = AuthManager().create_session_token(user_id=FAKE_THERAPIST_ID)
        coordinator = EndpointServiceCoordinator(routers=[PaymentProcessingRouter(environment=ENVIRONMENT).router],
                                                 environment=ENVIRONMENT)
        self.client = TestClient(coordinator.app)

    def test_generate_checkout_session_without_auth_token(self):
        response = self.client.post(PaymentProcessingRouter.CHECKOUT_SESSION_ENDPOINT,
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

    def test_generate_checkout_session_stripe_client_throws(self):
        self.fake_stripe_client.request_throws_exception = True
        response = self.client.post(PaymentProcessingRouter.CHECKOUT_SESSION_ENDPOINT,
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

    def test_generate_checkout_session_stripe_client_returns_none(self):
        self.fake_stripe_client.request_returns_none = True
        response = self.client.post(PaymentProcessingRouter.CHECKOUT_SESSION_ENDPOINT,
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

    def test_generate_checkout_session_stripe_client_returns_success(self):
        response = self.client.post(PaymentProcessingRouter.CHECKOUT_SESSION_ENDPOINT,
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

    def test_capture_payment_event_with_empty_stripe_signature(self):
        response = self.client.post(PaymentProcessingRouter.PAYMENT_EVENT_ENDPOINT,
                                    headers={})
        assert response.status_code == 401

    def test_capture_payment_event_with_valid_stripe_signature(self):
        response = self.client.post(PaymentProcessingRouter.PAYMENT_EVENT_ENDPOINT,
                                    headers={"stripe-signature": "my_signature"})
        assert response.status_code == 200

    def test_retrieve_subscriptions_without_auth_token(self):
        response = self.client.get(PaymentProcessingRouter.SUBSCRIPTIONS_ENDPOINT,
                                    headers={
                                        "store-access-token": FAKE_ACCESS_TOKEN,
                                        "store-refresh-token": FAKE_REFRESH_TOKEN
                                    })
        assert response.status_code == 401

    def test_retrieve_subscriptions_success(self):
        response = self.client.get(PaymentProcessingRouter.SUBSCRIPTIONS_ENDPOINT,
                                    cookies={
                                        "authorization": self.auth_cookie
                                    },
                                    headers={
                                        "store-access-token": FAKE_ACCESS_TOKEN,
                                        "store-refresh-token": FAKE_REFRESH_TOKEN
                                    })
        assert response.status_code == 200
        response_json = response.json()
        assert "subscriptions" in response_json

    def test_delete_subscription_without_auth_token(self):
        response = self.client.delete(PaymentProcessingRouter.SUBSCRIPTIONS_ENDPOINT,
                                    headers={
                                        "store-access-token": FAKE_ACCESS_TOKEN,
                                        "store-refresh-token": FAKE_REFRESH_TOKEN
                                    })
        assert response.status_code == 401

    def test_delete_subscription_success(self):
        response = self.client.delete(PaymentProcessingRouter.SUBSCRIPTIONS_ENDPOINT,
                                    cookies={
                                        "authorization": self.auth_cookie
                                    },
                                    headers={
                                        "store-access-token": FAKE_ACCESS_TOKEN,
                                        "store-refresh-token": FAKE_REFRESH_TOKEN
                                    })
        assert response.status_code == 200

    def test_update_subscription_plan_without_auth_token(self):
        response = self.client.put(PaymentProcessingRouter.SUBSCRIPTIONS_ENDPOINT,
                                    headers={
                                        "store-access-token": FAKE_ACCESS_TOKEN,
                                        "store-refresh-token": FAKE_REFRESH_TOKEN
                                    },
                                    json={
                                        "new_price_tier_id": FAKE_PRICE_ID,
                                        "behavior": UpdateSubscriptionBehavior.CHANGE_TIER.value
                                    })
        assert response.status_code == 401

    def test_update_subscription_upgrade_without_new_tier_price_id(self):
        response = self.client.put(PaymentProcessingRouter.SUBSCRIPTIONS_ENDPOINT,
                                    cookies={
                                        "authorization": self.auth_cookie
                                    },
                                    headers={
                                        "store-access-token": FAKE_ACCESS_TOKEN,
                                        "store-refresh-token": FAKE_REFRESH_TOKEN
                                    },
                                    json={
                                        "behavior": UpdateSubscriptionBehavior.CHANGE_TIER.value
                                    })
        assert response.status_code == 417

    def test_update_subscription_plan_success(self):
        response = self.client.put(PaymentProcessingRouter.SUBSCRIPTIONS_ENDPOINT,
                                    cookies={
                                        "authorization": self.auth_cookie
                                    },
                                    headers={
                                        "store-access-token": FAKE_ACCESS_TOKEN,
                                        "store-refresh-token": FAKE_REFRESH_TOKEN
                                    },
                                    json={
                                        "behavior": UpdateSubscriptionBehavior.CHANGE_TIER.value,
                                        "new_price_tier_id": FAKE_PRICE_ID
                                    })
        assert response.status_code == 200

    def test_retrieve_product_catalog_without_auth_token(self):
        response = self.client.get(PaymentProcessingRouter.PRODUCT_CATALOG,
                                    headers={
                                        "store-access-token": FAKE_ACCESS_TOKEN,
                                        "store-refresh-token": FAKE_REFRESH_TOKEN
                                    })
        assert response.status_code == 401

    def test_retrieve_product_catalog_success(self):
        response = self.client.get(PaymentProcessingRouter.PRODUCT_CATALOG,
                                    cookies={
                                        "authorization": self.auth_cookie
                                    },
                                    headers={
                                        "store-access-token": FAKE_ACCESS_TOKEN,
                                        "store-refresh-token": FAKE_REFRESH_TOKEN
                                    })
        assert response.status_code == 200
        assert "catalog" in response.json()

    def test_generate_update_payment_method_session_url_without_auth_token(self):
        response = self.client.post(PaymentProcessingRouter.UPDATE_PAYMENT_METHOD_SESSION_ENDPOINT,
                                    headers={
                                        "store-access-token": FAKE_ACCESS_TOKEN,
                                        "store-refresh-token": FAKE_REFRESH_TOKEN
                                    },
                                    json={
                                        "customer_id": FAKE_CUSTOMER_ID,
                                        "success_callback_url": "https://www.chartwise.ai/payment-success",
                                        "cancel_callback_url": "https://www.chartwise.ai",
                                    })
        assert response.status_code == 401

    def test_generate_update_payment_method_session_url_success(self):
        response = self.client.post(PaymentProcessingRouter.UPDATE_PAYMENT_METHOD_SESSION_ENDPOINT,
                                    cookies={
                                        "authorization": self.auth_cookie
                                    },
                                    headers={
                                        "store-access-token": FAKE_ACCESS_TOKEN,
                                        "store-refresh-token": FAKE_REFRESH_TOKEN
                                    },
                                    json={
                                        "success_callback_url": "https://www.chartwise.ai/payment-success",
                                        "cancel_callback_url": "https://www.chartwise.ai",
                                    })
        assert response.status_code == 200
        response_json = response.json()
        assert "update_payment_method_url" in response_json

    def test_retrieve_payment_history_without_auth_token(self):
        response = self.client.get(PaymentProcessingRouter.PAYMENT_HISTORY_ENDPOINT,
                                    headers={
                                        "store-access-token": FAKE_ACCESS_TOKEN,
                                        "store-refresh-token": FAKE_REFRESH_TOKEN
                                    })
        assert response.status_code == 401

    def test_retrieve_payment_history_success(self):
        response = self.client.get(PaymentProcessingRouter.PAYMENT_HISTORY_ENDPOINT,
                                    cookies={
                                        "authorization": self.auth_cookie
                                    }, headers={
                                        "store-access-token": FAKE_ACCESS_TOKEN,
                                        "store-refresh-token": FAKE_REFRESH_TOKEN
                                    })
        assert response.status_code == 200
        assert "payments" in response.json()
