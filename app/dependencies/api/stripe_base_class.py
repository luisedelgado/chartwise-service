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
    def construct_webhook_event(payload,
                                sig_header,
                                webhook_secret):
        pass

    @abstractmethod
    def retrieve_session(session_id):
        pass

    @abstractmethod
    def retrieve_product(product_id):
        pass

    @abstractmethod
    def retrieve_payment_method(payment_method_id):
        pass

    @abstractmethod
    def retrieve_subscription(self, subscription_id):
        pass

    @abstractmethod
    def retrieve_customer_subscriptions(customer_id: str) -> dict:
        pass

    @abstractmethod
    def delete_customer_subscription(subscription_id: str):
        pass

    @abstractmethod
    def update_customer_subscription(subscription_id: str,
                                     product_id: str,
                                     price_id: str):
        pass

    @abstractmethod
    def retrieve_product_catalog(self) -> list:
        pass

    @abstractmethod
    def attach_subscription_metadata(subscription_id: str, metadata: dict):
        pass

    @abstractmethod
    def attach_invoice_metadata(invoice_id: str, metadata: dict):
        pass

    @staticmethod
    def is_signature_verification_error(e: Exception) -> bool:
        return isinstance(e, SignatureVerificationError)
