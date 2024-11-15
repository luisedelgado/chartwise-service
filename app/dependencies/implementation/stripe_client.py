import os, stripe

from ..api.stripe_base_class import StripeBaseClass

class StripeClient(StripeBaseClass):

    def __init__(self):
        stripe.api_key = os.environ.get("STRIPE_API_KEY")

    def generate_payment_session(self,
                                 session_id: str,
                                 therapist_id: str,
                                 price_id: str,
                                 success_url: str,
                                 cancel_url: str) -> str | None:
        try:
            session = stripe.checkout.Session.create(
                success_url=success_url,
                cancel_url=cancel_url,
                mode='subscription',
                line_items=[{
                    'price': price_id,
                    'quantity': 1
                }],
                 metadata={
                    'session_id': str(session_id),
                    'therapist_id': str(therapist_id)
                }
            )
            return session['url']
        except Exception as e:
            raise Exception(e)

    def construct_webhook_event(self,
                                payload,
                                sig_header,
                                webhook_secret):
        return stripe.Webhook.construct_event(
            payload=payload,
            sig_header=sig_header,
            secret=webhook_secret
        )

    def retrieve_session(self, session_id):
        return stripe.checkout.Session.retrieve(session_id)

    def add_subscription_metadata(self, subscription_id: str, metadata: dict):
        stripe.Subscription.modify(subscription_id, metadata=metadata)

    def add_invoice_metadata(self, invoice_id: str, metadata: dict):
        res = stripe.Invoice.modify(invoice_id, metadata=metadata)
        print(res)
