from ..api.stripe_base_class import StripeBaseClass

class FakeStripeClient(StripeBaseClass):

    def generate_payment_session(self,
                                 price_id: str,
                                 success_url: str,
                                 cancel_url: str) -> str | None:
        pass

    def construct_webhook_event(self,
                                payload,
                                sig_header,
                                webhook_secret):
        pass
