import time

from stripe._error import SignatureVerificationError

from ..api.stripe_base_class import StripeBaseClass

FAKE_THERAPIST_ID = "4987b72e-dcbb-41fb-96a6-bf69756942cc"
FAKE_SESSION_ID = "884f507c-f391-4248-91c4-7c25a138633a"
FAKE_PAYMENT_METHOD_ID = "884f507c-f391-4248-91c4-7c25a138633a"

class FakeStripeClient(StripeBaseClass):

    request_throws_exception = False
    request_returns_none = False

    def generate_checkout_session(self,
                                  session_id: str,
                                  therapist_id: str,
                                  price_id: str,
                                  success_url: str,
                                  cancel_url: str,
                                  is_new_customer: bool) -> str | None:
        if self.request_returns_none:
            return None

        if self.request_throws_exception:
            raise Exception("Something failed")

        return "my fake url"

    def construct_webhook_event(self,
                                payload,
                                sig_header,
                                webhook_secret):
        if len(sig_header or '') == 0:
            raise SignatureVerificationError(message="invalid signature", sig_header=sig_header)

        return {
            "type": "event_type",
            "data": {
                "object": {
                    "metadata": {
                        "therapist_id": FAKE_THERAPIST_ID,
                        "session_id": FAKE_SESSION_ID
                    }
                }
            }
        }

    def retrieve_price(self, price_id: str):
        pass

    def retrieve_invoice(self, invoice_id: str):
        pass

    def retrieve_payment_intent_history(self,
                                        customer_id: str,
                                        limit: int,
                                        starting_after: str | None):
        return {
            "data": [{
                "status": "succeeded",
                "id": "fakeID",
                "amount": "52",
                "currency": "usd",
                "created": 1733011200,
                "description": "fakePayment",
            }]
        }

    def retrieve_product(self, product_id):
        pass

    def retrieve_session(self, session_id):
        pass

    def retrieve_payment_method(self, payment_method_id):
        return {
            "id": FAKE_PAYMENT_METHOD_ID,
            "type": "card",
            "card": {
                "lastFour": 1111
            }
        }

    def retrieve_subscription(self, subscription_id: str):
        return {
            "items": {
                "data": [{
                    "id": FAKE_PAYMENT_METHOD_ID
                }]
            }
        }

    def retrieve_customer_subscriptions(self, customer_id: str) -> dict:
        return {
            "object": "list",
            "url": "/v1/subscriptions",
            "has_more": "false",
            "data": [
                {
                "id": "su_1NXPiE2eZvKYlo2COk9fohqA",
                "object": "subscription",
                "status": "trialing",
                "trial_end": int(time.time()) + 7 * 24 * 60 * 60,
                "application": "null",
                "application_fee_percent": "null",
                "automatic_tax": {
                    "enabled": "false"
                },
                "plan": {
                    "id": "plan_OK3pbS1dvdQYJP"
                },
                "default_payment_method": "pm_OK3pbS1dvdQYJP",
                "items": {
                    "object": "list",
                    "data": [
                        {
                            "id": "si_OK3pbS1dvdQYJP",
                            "object": "subscription_item",
                            "billing_thresholds": "null",
                            "created": "1690208774",
                            "metadata": {},
                            "price": {
                            "id": "price_1NOhvg2eZvKYlo2CqkpQDVRT",
                            "object": "price"
                            }
                        }
                    ]
                }
                }
            ]
        }

    def cancel_customer_subscription(self, subscription_id: str):
        pass

    def delete_customer_subscription_immediately(self, subscription_id: str):
        pass

    def resume_cancelled_subscription(self, subscription_id: str):
        pass

    def update_customer_subscription_plan(self,
                                          subscription_id: str,
                                          subscription_item_id: str,
                                          price_id: str):
        pass

    def attach_customer_payment_method(self,
                                       customer_id: str,
                                       payment_method_id: str):
        pass

    def update_subscription_payment_method(self,
                                           subscription_id: str,
                                           payment_method_id: str):
        pass

    def retrieve_product_catalog(self) -> list:
        return {
                "catalog": [{
                    "product": "myproduct",
                    "product_id": "prod_RCr6wwfVmOVvly",
                    "description": "(created by Stripe CLI)",
                    "price_data": [{
                            "price_id": "price_1QKROSL2OU4L8JdeMZIxSIt0",
                            "amount": "1500 usd"
                        }
                    ]
                }, {
                    "product": "Premium Plan",
                    "product_id": "prod_RCpduG3DY2CCQU",
                    "description": "Our premium plan for unlimited usage",
                    "price_data": [{
                            "price_id": "price_1QKPyiL2OU4L8JdeoVF2QXS2",
                            "amount": "81000 usd"
                        }
                    ]
                }]
        }

    def attach_subscription_metadata(self, subscription_id: str, metadata: dict):
        pass

    def attach_payment_intent_metadata(self, payment_intent_id: str, metadata: dict):
        pass

    def attach_invoice_metadata(self, invoice_id: str, metadata: dict):
        pass

    def generate_payment_method_update_session(self,
                                               customer_id: str,
                                               success_url: str,
                                               cancel_url) -> str:
        return "fakePaymentMethodURL"
