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
ENVIRONMENT = "testing"

class TestingHarnessPaymentProcessingRouter:

    def setup_method(self):
        # Clear out any old state between tests
        dependency_container._aws_cognito_client = None
        dependency_container._aws_db_client = None
        dependency_container._aws_kms_client = None
        dependency_container._aws_s3_client = None
        dependency_container._aws_secret_manager_client = None
        dependency_container._chartwise_encryptor = None
        dependency_container._docupanda_client = None
        dependency_container._influx_client = None
        dependency_container._openai_client = None
        dependency_container._pinecone_client = None
        dependency_container._resend_client = None
        dependency_container._stripe_client = None
        dependency_container._testing_environment = "testing"

        self.fake_openai_client = dependency_container.inject_openai_client()
        self.fake_docupanda_client = dependency_container.inject_docupanda_client()
        self.fake_stripe_client: FakeStripeClient = dependency_container.inject_stripe_client()
        self.fake_pinecone_client = dependency_container.inject_pinecone_client()
        self.session_token, _ = AuthManager().create_session_token(user_id=FAKE_THERAPIST_ID)
        coordinator = EndpointServiceCoordinator(routers=[PaymentProcessingRouter(environment=ENVIRONMENT).router],
                                                 environment=ENVIRONMENT)
        self.client = TestClient(coordinator.app)

    def test_generate_checkout_session_without_session_token(self):
        response = self.client.post(
            PaymentProcessingRouter.CHECKOUT_SESSION_ENDPOINT,
            headers={
                "auth-token": "myFakeToken",
            },
            json={
                "price_id": FAKE_PRICE_ID,
                "success_callback_url": "https://www.chartwise.ai/payment-success",
                "cancel_callback_url": "https://www.chartwise.ai",
            }
        )
        assert response.status_code == 401

    def test_generate_checkout_session_stripe_client_throws(self):
        self.fake_stripe_client.request_throws_exception = True
        self.client.cookies.set("session_token", self.session_token)
        response = self.client.post(
            PaymentProcessingRouter.CHECKOUT_SESSION_ENDPOINT,
            headers={
                "auth-token": "myFakeToken",
            },
            json={
                "price_id": FAKE_PRICE_ID,
                "success_callback_url": "https://www.chartwise.ai/payment-success",
                "cancel_callback_url": "https://www.chartwise.ai",
            }
        )
        assert response.status_code == 417

    def test_generate_checkout_session_stripe_client_returns_none(self):
        self.fake_stripe_client.request_returns_none = True
        self.client.cookies.set("session_token", self.session_token)
        response = self.client.post(
            PaymentProcessingRouter.CHECKOUT_SESSION_ENDPOINT,
            headers={
                "auth-token": "myFakeToken",
            },
            json={
                "price_id": FAKE_PRICE_ID,
                "success_callback_url": "https://www.chartwise.ai/payment-success",
                "cancel_callback_url": "https://www.chartwise.ai",
            }
        )
        assert response.status_code == 417

    def test_generate_checkout_session_stripe_client_returns_success(self):
        assert not self.fake_stripe_client.generate_checkout_session_invoked
        self.client.cookies.set("session_token", self.session_token)
        response = self.client.post(
            PaymentProcessingRouter.CHECKOUT_SESSION_ENDPOINT,
            headers={
                "auth-token": "myFakeToken",
            },
            json={
                "price_id": FAKE_PRICE_ID,
                "success_callback_url": "https://www.chartwise.ai/payment-success",
                "cancel_callback_url": "https://www.chartwise.ai",
            }
        )
        assert response.status_code == 200
        assert self.fake_stripe_client.generate_checkout_session_invoked
        assert "payment_session_url" in response.json()

    def test_capture_payment_event_with_empty_stripe_signature(self):
        response = self.client.post(
            PaymentProcessingRouter.PAYMENT_EVENT_ENDPOINT,
            headers={}
        )
        assert response.status_code == 401

    def test_capture_payment_event_with_valid_stripe_signature(self):
        response = self.client.post(
            PaymentProcessingRouter.PAYMENT_EVENT_ENDPOINT,
            headers={
                "stripe-signature": "my_signature"
            }
        )
        assert response.status_code == 200

    def test_retrieve_subscriptions_without_session_token(self):
        response = self.client.get(
            PaymentProcessingRouter.SUBSCRIPTIONS_ENDPOINT,
            headers={
                "auth-token": "myFakeToken",
            },
        )
        assert response.status_code == 401

    def test_retrieve_subscriptions_success(self):
        assert not self.fake_stripe_client.retrieve_customer_subscriptions_invoked
        self.client.cookies.set("session_token", self.session_token)
        response = self.client.get(
            PaymentProcessingRouter.SUBSCRIPTIONS_ENDPOINT,
            headers={
                "auth-token": "myFakeToken",
            },
        )
        assert response.status_code == 200
        assert self.fake_stripe_client.retrieve_customer_subscriptions_invoked
        response_json = response.json()
        assert "subscriptions" in response_json

    def test_delete_subscription_without_session_token(self):
        response = self.client.delete(
            PaymentProcessingRouter.SUBSCRIPTIONS_ENDPOINT,
            headers={
                "auth-token": "myFakeToken",
            }
        )
        assert response.status_code == 401

    def test_delete_subscription_success(self):
        assert not self.fake_stripe_client.subscription_cancellation_invoked
        self.client.cookies.set("session_token", self.session_token)
        response = self.client.delete(
            PaymentProcessingRouter.SUBSCRIPTIONS_ENDPOINT,
            headers={
                "auth-token": "myFakeToken",
            },
        )
        assert response.status_code == 200
        assert self.fake_stripe_client.subscription_cancellation_invoked

    def test_update_subscription_plan_without_session_token(self):
        response = self.client.put(
            PaymentProcessingRouter.SUBSCRIPTIONS_ENDPOINT,
            headers={
                "auth-token": "myFakeToken",
            },
            json={
                "new_price_tier_id": FAKE_PRICE_ID,
                "behavior": UpdateSubscriptionBehavior.CHANGE_TIER.value
            }
        )
        assert response.status_code == 401

    def test_update_subscription_upgrade_without_new_tier_price_id(self):
        self.client.cookies.set("session_token", self.session_token)
        response = self.client.put(
            PaymentProcessingRouter.SUBSCRIPTIONS_ENDPOINT,
            headers={
                "auth-token": "myFakeToken",
            },
            json={
                "behavior": UpdateSubscriptionBehavior.CHANGE_TIER.value
            }
        )
        assert response.status_code == 417

    def test_update_subscription_plan_change_tier_success(self):
        assert not self.fake_stripe_client.update_customer_subscription_plan_invoked
        self.client.cookies.set("session_token", self.session_token)
        response = self.client.put(
            PaymentProcessingRouter.SUBSCRIPTIONS_ENDPOINT,
            headers={
                "auth-token": "myFakeToken",
            },
            json={
                "new_price_tier_id": FAKE_PRICE_ID,
                "behavior": UpdateSubscriptionBehavior.CHANGE_TIER.value
            }
        )
        assert response.status_code == 200
        assert self.fake_stripe_client.update_customer_subscription_plan_invoked

    def test_update_subscription_plan_undo_cancellation_success(self):
        assert not self.fake_stripe_client.resume_cancelled_subscription_invoked
        self.client.cookies.set("session_token", self.session_token)
        response = self.client.put(
            PaymentProcessingRouter.SUBSCRIPTIONS_ENDPOINT,
            headers={
                "auth-token": "myFakeToken",
            },
            json={
                "new_price_tier_id": FAKE_PRICE_ID,
                "behavior": UpdateSubscriptionBehavior.UNDO_CANCELLATION.value
            }
        )
        assert response.status_code == 200
        assert self.fake_stripe_client.resume_cancelled_subscription_invoked

    def test_retrieve_product_catalog_without_session_token(self):
        response = self.client.get(
            PaymentProcessingRouter.PRODUCT_CATALOG_ENDPOINT,
            headers={
                "auth-token": "myFakeToken",
            }
        )
        assert response.status_code == 401

    def test_retrieve_product_catalog_success(self):
        assert not self.fake_stripe_client.retrieve_product_catalog_invoked
        self.client.cookies.set("session_token", self.session_token)
        response = self.client.get(
            PaymentProcessingRouter.PRODUCT_CATALOG_ENDPOINT,
            headers={
                "auth-token": "myFakeToken",
            }
        )
        assert response.status_code == 200
        assert self.fake_stripe_client.retrieve_product_catalog_invoked
        assert "catalog" in response.json()

    def test_generate_update_payment_method_session_url_without_session_token(self):
        response = self.client.post(
            PaymentProcessingRouter.UPDATE_PAYMENT_METHOD_SESSION_ENDPOINT,
            headers={
                "auth-token": "myFakeToken",
            },
            json={
                "customer_id": FAKE_CUSTOMER_ID,
                "success_callback_url": "https://www.chartwise.ai/payment-success",
                "cancel_callback_url": "https://www.chartwise.ai",
            }
        )
        assert response.status_code == 401

    def test_generate_update_payment_method_session_url_success(self):
        assert not self.fake_stripe_client.generate_payment_method_update_session_invoked
        self.client.cookies.set("session_token", self.session_token)
        response = self.client.post(
            PaymentProcessingRouter.UPDATE_PAYMENT_METHOD_SESSION_ENDPOINT,
            headers={
                "auth-token": "myFakeToken",
            },
            json={
                "customer_id": FAKE_CUSTOMER_ID,
                "success_callback_url": "https://www.chartwise.ai/payment-success",
                "cancel_callback_url": "https://www.chartwise.ai",
            }
        )
        assert response.status_code == 200
        assert self.fake_stripe_client.generate_payment_method_update_session_invoked
        response_json = response.json()
        assert "update_payment_method_url" in response_json

    def test_retrieve_payment_history_without_session_token(self):
        response = self.client.get(
            PaymentProcessingRouter.PAYMENT_HISTORY_ENDPOINT,
            headers={
                "auth-token": "myFakeToken",
            }
        )
        assert response.status_code == 401

    def test_retrieve_payment_history_success(self):
        assert not self.fake_stripe_client.retrieve_payment_intent_history_invoked
        self.client.cookies.set("session_token", self.session_token)
        response = self.client.get(
            PaymentProcessingRouter.PAYMENT_HISTORY_ENDPOINT,
            headers={
                "auth-token": "myFakeToken",
            }
        )
        assert response.status_code == 200
        assert self.fake_stripe_client.retrieve_payment_intent_history_invoked
        assert "payments" in response.json()

    def test_get_subscription_status_with_auth_token_but_missing_session_token(self):
        response = self.client.get(
            PaymentProcessingRouter.SUBSCRIPTION_STATUS_ENDPOINT,
            headers={
                "auth-token": FAKE_ACCESS_TOKEN,
            },
        )
        assert response.status_code == 401

    def test_get_subscription_status_success(self):
        self.client.cookies.set("session_token", self.session_token)
        response = self.client.get(
            PaymentProcessingRouter.SUBSCRIPTION_STATUS_ENDPOINT,
            headers={
                "auth-token": FAKE_ACCESS_TOKEN,
            },
        )
        assert response.status_code == 200
        response_json = response.json()
        assert response_json["subscription_status"] is not None
