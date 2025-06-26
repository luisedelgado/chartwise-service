from abc import ABC, abstractmethod
from stripe._error import SignatureVerificationError

class StripeBaseClass(ABC):

    @abstractmethod
    def generate_checkout_session(
        self,
        session_id: str,
        therapist_id: str,
        price_id: str,
        success_url: str,
        cancel_url: str,
    ) -> str | None:
        """
        Generates a checkout session URL for the customer.

        Arguments:
        session_id – the current user session id.
        therapist_id – the therapist_id associated with the customer.
        price_id – the price id for the selected product.
        success_url – the url to be used for resolving a successful payment.
        cancel_url – the url to be used for resolving a cancel action.
        """
        pass

    @abstractmethod
    def construct_webhook_event(
        self,
        payload,
        sig_header,
        webhook_secret
    ):
        """
        Constructs a webhook event from the incoming Stripe data to be handled internally.

        Arguments:
        payload – the payload to be used for constructing the event.
        sig_header – the signature header for authentication.
        webhook_secret – the secret associated with the webhook.
        """
        pass

    @abstractmethod
    def retrieve_session(
        self,
        session_id: str
    ):
        """
        Retrieves the session associated with the incoming id

        Arguments:
        session_id – the checkout session ID to be retrieved
        """
        pass

    @abstractmethod
    def retrieve_payment_intent_history(
        self,
        customer_id: str,
        limit: int,
        starting_after: str | None
    ):
        """
        Retrieves the payment history associated with the incoming customer id

        Arguments:
        customer_id – the customer ID to be used for pulling a payment history.
        limit – the limit for the batch size to be returned.
        starting_after – the id of the last intent that was retrieved (for pagination purposes).
        """
        pass

    @abstractmethod
    def retrieve_price(
        self,
        price_id: str
    ):
        """
        Retrieves a price

        Arguments:
        price_id – the price ID to be retrieved.
        """
        pass

    @abstractmethod
    def retrieve_invoice(
        self,
        invoice_id: str
    ):
        """
        Retrieves the invoice associated with the incoming id

        Arguments:
        invoice_id – the invoice ID to be fetched.
        """
        pass

    @abstractmethod
    def retrieve_product(
        self,
        product_id: str
    ):
        """
        Retrieves the product associated with the incoming id

        Arguments:
        product_id – the product ID to be retrieved
        """
        pass

    @abstractmethod
    def retrieve_payment_method(
        self,
        payment_method_id: str
    ):
        """
        Retrieves the payment method associated with the incoming id

        Arguments:
        payment_method_id – the payment method ID to be retrieved
        """
        pass

    @abstractmethod
    def retrieve_subscription(
        self,
        subscription_id: str
    ):
        """
        Retrieves the subscription associated with the incoming id

        Arguments:
        subscription_id – the subscription ID to be retrieved
        """
        pass

    @abstractmethod
    def retrieve_customer_subscriptions(
        self,
        customer_id: str
    ) -> dict:
        """
        Retrieves the subscriptions associated with the incoming customer id

        Arguments:
        customer_id – the customer whose subscriptions will be retrieved.
        """
        pass

    @abstractmethod
    def cancel_customer_subscription(
        self,
        subscription_id: str
    ):
        """
        Cancels the subscription associated with the incoming id while
        leaving it active until the current billing period end.

        Arguments:
        subscription_id – the subscription ID to be deleted.
        """
        pass

    @abstractmethod
    def delete_customer_subscription_immediately(
        self,
        subscription_id: str
    ):
        """
        Cancels and deletes a subscription immediately.

        Arguments:
        subscription_id – the subscription ID to be deleted.
        """
        pass

    @abstractmethod
    def resume_cancelled_subscription(
        self,
        subscription_id: str
    ):
        """
        Attempts to resume a subscription that was previously scheduled for cancellation.

        Arguments:
        subscription_id – the subscription ID to be resumed.
        """
        pass

    @abstractmethod
    def update_customer_subscription_plan(
        self,
        subscription_id: str,
        subscription_item_id: str,
        price_id: str,
    ):
        """
        Updates the subscription associated with the incoming id

        Arguments:
        subscription_id – the subscription ID to be updated.
        subscription_item_id – the unique identifier for a specific item within a subscription.
        price_id – the new price ID to be assigned to the subscription.
        """
        pass

    @abstractmethod
    def attach_customer_payment_method(
        self,
        customer_id: str,
        payment_method_id: str
    ):
        """
        Attaches an incoming payment method to the given customer.

        Arguments:
        customer_id – the customer ID to be updated.
        payment_method_id – the new payment method ID to be linked to the customer.
        """
        pass

    @abstractmethod
    def update_subscription_payment_method(
        self,
        subscription_id: str,
        payment_method_id: str
    ):
        """
        Updates the subscription's associated payment method

        Arguments:
        subscription_id – the subscription ID to be updated.
        payment_method_id – the new payment method ID to be linked to the subscription.
        """
        pass

    @abstractmethod
    def retrieve_product_catalog(
        self,
        country_iso: str | None = None
    ) -> list:
        """
        Retrieves the product catalog.

        Arguments:
        country_iso – the country ISO to be used for retrieving the product catalog.
        """
        pass

    @abstractmethod
    def attach_subscription_metadata(
        self,
        subscription_id: str,
        metadata: dict,
    ):
        """
        Attaches metadata to the subscription associated with the incoming ID

        Arguments:
        subscription_id – the subscription ID to be updated.
        metadata the – metadata to be attached to the subscription
        """
        pass

    @abstractmethod
    def attach_invoice_metadata(
        self,
        invoice_id: str,
        metadata: dict,
    ):
        """
        Attaches metadata to the invoice associated with the incoming ID

        Arguments:
        invoice_id – the invoice ID to be updated.
        metadata the – metadata to be attached to the invoice
        """
        pass

    @abstractmethod
    def attach_payment_intent_metadata(
        self,
        payment_intent_id: str,
        metadata: dict,
    ):
        """
        Attach metadata to the payment intent associated with the incoming ID

        Arguments:
        payment_intent_id – the payment intent ID to be updated.
        metadata the – metadata to be attached to the payment intent.
        """
        pass

    @abstractmethod
    def generate_payment_method_update_session(
        self,
        customer_id: str,
        success_url: str,
        cancel_url: str,
    ) -> str:
        """
        Generates a 'update-payment-method' session URL for the customer.

        Arguments:
        customer_id – the current user's customer id'.
        success_url – the url to be used for resolving a successful payment.
        cancel_url – the url to be used for resolving a cancel action.
        """
        pass

    @staticmethod
    def is_signature_verification_error(e: Exception) -> bool:
        """
        Determines if the incoming exception is a SignatureVerificationError

        Arguments:
        e – the exception to be revised.
        """
        return isinstance(e, SignatureVerificationError)
