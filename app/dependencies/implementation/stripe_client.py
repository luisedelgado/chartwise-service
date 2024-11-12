import stripe
from stripe._error import SignatureVerificationError

from ..api.stripe_base_class import StripeBaseClass

class StripeClient(StripeBaseClass):

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
                    'session_id': session_id,
                    'therapist_id': therapist_id
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
            payload=payload, sig_header=sig_header, secret=webhook_secret
        )

    def is_signature_verification_error(e: Exception) -> bool:
        return isinstance(e, SignatureVerificationError)
