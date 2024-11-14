from abc import ABC, abstractmethod
from stripe._error import SignatureVerificationError

class StripeBaseClass(ABC):

    @abstractmethod
    def generate_payment_session(session_id: str,
                                 therapist_id: str,
                                 price_id: str,
                                 success_url: str,
                                 cancel_url: str) -> str | None:
        pass

    @abstractmethod
    def construct_webhook_event(self,
                                payload,
                                sig_header,
                                webhook_secret):
        pass

    @staticmethod
    def is_signature_verification_error(e: Exception) -> bool:
        return isinstance(e, SignatureVerificationError)
