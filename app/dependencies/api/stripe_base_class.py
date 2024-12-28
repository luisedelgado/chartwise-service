from abc import ABC, abstractmethod
from stripe._error import SignatureVerificationError

class StripeBaseClass(ABC):

    """
    Generates a checkout session URL for the customer.

    Arguments:
    session_id – the current user session id.
    therapist_id – the therapist_id associated with the customer.
    price_id – the price id for the selected product.
    success_url – the url to be used for resolving a successful payment.
    cancel_url – the url to be used for resolving a cancel action.
    """
    @abstractmethod
    def generate_checkout_session(session_id: str,
                                  therapist_id: str,
                                  price_id: str,
                                  success_url: str,
                                  cancel_url: str,
                                  is_new_customer: bool) -> str | None:
        pass

    """
    Constructs a webhook event from the incoming Stripe data to be handled internally.

    Arguments:
    payload – the payload to be used for constructing the event.
    sig_header – the signature header for authentication.
    webhook_secret – the secret associated with the webhook.
    """
    @abstractmethod
    def construct_webhook_event(payload,
                                sig_header,
                                webhook_secret):
        pass

    """
    Retrieves the session associated with the incoming id

    Arguments:
    session_id – the checkout session ID to be retrieved
    """
    @abstractmethod
    def retrieve_session(session_id: str):
        pass

    """
    Retrieves the payment history associated with the incoming customer id

    Arguments:
    customer_id – the customer ID to be used for pulling a payment history.
    limit – the limit for the batch size to be returned.
    starting_after – the id of the last intent that was retrieved (for pagination purposes).
    """
    @abstractmethod
    def retrieve_payment_intent_history(customer_id: str,
                                        limit: int,
                                        starting_after: str | None):
        pass

    """
    Retrieves a price

    Arguments:
    price_id – the price ID to be retrieved.
    """
    @abstractmethod
    def retrieve_price(self, price_id: str):
        pass

    """
    Retrieves the invoice associated with the incoming id

    Arguments:
    invoice_id – the invoice ID to be fetched.
    """
    @abstractmethod
    def retrieve_invoice(invoice_id: str):
        pass

    """
    Retrieves the product associated with the incoming id

    Arguments:
    product_id – the product ID to be retrieved
    """
    @abstractmethod
    def retrieve_product(product_id: str):
        pass

    """
    Retrieves the payment method associated with the incoming id

    Arguments:
    payment_method_id – the payment method ID to be retrieved
    """
    @abstractmethod
    def retrieve_payment_method(payment_method_id: str):
        pass

    """
    Retrieves the subscription associated with the incoming id

    Arguments:
    subscription_id – the subscription ID to be retrieved
    """
    @abstractmethod
    def retrieve_subscription(subscription_id: str):
        pass

    """
    Retrieves the subscriptions associated with the incoming customer id

    Arguments:
    customer_id – the customer whose subscriptions will be retrieved.
    """
    @abstractmethod
    def retrieve_customer_subscriptions(customer_id: str) -> dict:
        pass

    """
    Cancels the subscription associated with the incoming id while
    leaving it active until the current billing period end.

    Arguments:
    subscription_id – the subscription ID to be deleted.
    """
    @abstractmethod
    def cancel_customer_subscription(subscription_id: str):
        pass

    """
    Cancels and deletes a subscription immediately.

    Arguments:
    subscription_id – the subscription ID to be deleted.
    """
    @abstractmethod
    def delete_customer_subscription_immediately(subscription_id: str):
        pass

    """
    Attempts to resume a subscription that was previously scheduled for cancellation.

    Arguments:
    subscription_id – the subscription ID to be resumed.
    """
    @abstractmethod
    def resume_cancelled_subscription(subscription_id: str):
        pass

    """
    Updates the subscription associated with the incoming id

    Arguments:
    subscription_id – the subscription ID to be updated.
    subscription_item_id – the unique identifier for a specific item within a subscription.
    price_id – the new price ID to be assigned to the subscription.
    """
    @abstractmethod
    def update_customer_subscription_plan(subscription_id: str,
                                          subscription_item_id: str,
                                          price_id: str):
        pass

    """
    Updates the subscription's associated payment method

    Arguments:
    subscription_id – the subscription ID to be updated.
    payment_method_id – the new payment method ID to be linked to the subscription.
    """
    @abstractmethod
    def update_subscription_payment_method(subscription_id: str,
                                           payment_method_id: str):
        pass

    """
    Retrieves the product catalog.
    """
    @abstractmethod
    def retrieve_product_catalog() -> list:
        pass

    """
    Attaches metadata to the subscription associated with the incoming ID

    Arguments:
    subscription_id – the subscription ID to be updated.
    metadata the – metadata to be attached to the subscription
    """
    @abstractmethod
    def attach_subscription_metadata(subscription_id: str, metadata: dict):
        pass

    """
    Attaches metadata to the invoice associated with the incoming ID

    Arguments:
    invoice_id – the invoice ID to be updated.
    metadata the – metadata to be attached to the invoice
    """
    @abstractmethod
    def attach_invoice_metadata(invoice_id: str, metadata: dict):
        pass

    """
    Attach metadata to the payment intent associated with the incoming ID

    Arguments:
    payment_intent_id – the payment intent ID to be updated.
    metadata the – metadata to be attached to the payment intent.
    """
    @abstractmethod
    def attach_payment_intent_metadata(payment_intent_id: str, metadata: dict):
        pass

    """
    Generates a 'update-payment-method' session URL for the customer.

    Arguments:
    customer_id – the current user's customer id'.
    success_url – the url to be used for resolving a successful payment.
    cancel_url – the url to be used for resolving a cancel action.
    """
    @abstractmethod
    def generate_payment_method_update_session(customer_id: str,
                                               success_url: str,
                                               cancel_url) -> str:
        pass

    """
    Determines if the incoming exception is a SignatureVerificationError

    Arguments:
    e – the exception to be revised.
    """
    @staticmethod
    def is_signature_verification_error(e: Exception) -> bool:
        return isinstance(e, SignatureVerificationError)
