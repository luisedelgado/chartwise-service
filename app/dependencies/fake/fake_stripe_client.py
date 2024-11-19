from stripe._error import SignatureVerificationError

from ..api.stripe_base_class import StripeBaseClass

FAKE_THERAPIST_ID = "4987b72e-dcbb-41fb-96a6-bf69756942cc"
FAKE_SESSION_ID = "884f507c-f391-4248-91c4-7c25a138633a"

class FakeStripeClient(StripeBaseClass):

    request_throws_exception = False
    request_returns_none = False

    def generate_payment_session(self,
                                 session_id: str,
                                 therapist_id: str,
                                 price_id: str,
                                 success_url: str,
                                 cancel_url: str) -> str | None:
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

    def retrieve_session(self, session_id):
        pass

    def retrieve_payment_method(self, payment_method_id):
        pass

    def retrieve_subscription(self, subscription_id):
        pass

    def retrieve_customer_subscriptions(self, customer_id: str) -> dict:
        return {
            "object": "list",
            "url": "/v1/subscriptions",
            "has_more": "false",
            "data": [
                {
                "id": "su_1NXPiE2eZvKYlo2COk9fohqA",
                "object": "subscription",
                "application": "null",
                "application_fee_percent": "null",
                "automatic_tax": {
                    "enabled": "false"
                },
                "plan": {
                    "id": "plan_OK3pbS1dvdQYJP"
                },
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

    def delete_customer_subscription(self, subscription_id: str):
        pass

    def update_customer_subscription(self,
                                     subscription_id: str,
                                     product_id: str,
                                     price_id: str):
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

    def attach_invoice_metadata(self, invoice_id: str, metadata: dict):
        pass
