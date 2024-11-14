from ..api.stripe_base_class import StripeBaseClass

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
        pass

    def is_signature_verification_error(e: Exception) -> bool:
        pass
