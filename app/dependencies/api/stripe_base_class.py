from abc import ABC, abstractmethod

class StripeBaseClass(ABC):

    @abstractmethod
    def generate_payment_session(price_id: str,
                                 success_url: str,
                                 cancel_url: str) -> str | None:
        pass

    @abstractmethod
    def construct_webhook_event(self,
                                payload,
                                sig_header,
                                webhook_secret):
        pass
