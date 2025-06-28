import os, stripe

from ..api.stripe_base_class import StripeBaseClass
from ...internal.utilities.subscription_utilities import format_currency_amount

class StripeClient(StripeBaseClass):

    def __init__(self):
        stripe.api_key = os.environ.get("STRIPE_API_KEY")
        self.environment = os.environ.get("ENVIRONMENT")

    def generate_checkout_session(
        self,
        therapist_id: str,
        price_id: str,
        success_url: str,
        cancel_url: str,
        session_id: str | None,
    ) -> str | None:
        try:
            global_metadata = {
                'session_id': str(session_id) if session_id is not None else None,
                'therapist_id': str(therapist_id),
                'environment': self.environment
            }

            checkout_session = stripe.checkout.Session.create(
                success_url=success_url,
                cancel_url=cancel_url,
                mode='subscription',
                line_items=[{
                    'price': price_id,
                    'quantity': 1
                }],
                subscription_data={
                    'metadata': global_metadata,
                },
                metadata=global_metadata
            )
            return checkout_session['url']
        except Exception as e:
            raise RuntimeError(e) from e

    def construct_webhook_event(
        self,
        payload,
        sig_header,
        webhook_secret
    ):
        return stripe.Webhook.construct_event(
            payload=payload,
            sig_header=sig_header,
            secret=webhook_secret
        )

    def retrieve_session(self, session_id):
        return stripe.checkout.Session.retrieve(session_id)

    def retrieve_subscription(self, subscription_id) -> dict:
        return stripe.Subscription.retrieve(subscription_id)

    def retrieve_payment_method(self, payment_method_id):
        return stripe.PaymentMethod.retrieve(payment_method_id)

    def retrieve_product(self, product_id):
        return stripe.Product.retrieve(product_id)

    def retrieve_customer_subscriptions(self, customer_id: str) -> dict:
        return stripe.Subscription.list(customer=customer_id)

    def retrieve_payment_intent_history(
        self,
        customer_id: str,
        limit: int,
        starting_after: str | None
    ) -> dict:
        assert starting_after is not None, "Cannot use a null `starting_after` value"
        return stripe.PaymentIntent.list(
            customer=customer_id,
            limit=limit,
            starting_after=starting_after
        )

    def cancel_customer_subscription(self, subscription_id: str):
        return stripe.Subscription.modify(
            subscription_id,
            cancel_at_period_end=True
        )

    def delete_customer_subscription_immediately(self, subscription_id: str):
        return stripe.Subscription.cancel(subscription_id)

    def resume_cancelled_subscription(self, subscription_id: str):
        return stripe.Subscription.modify(
            subscription_id,
            cancel_at_period_end=False
        )

    def update_customer_subscription_plan(
        self,
        subscription_id: str,
        subscription_item_id: str,
        price_id: str
    ):
        stripe.Subscription.modify(
            subscription_id,
            items=[{"id": subscription_item_id, "price": price_id}]
        )

    def attach_customer_payment_method(
        self,
        customer_id: str,
        payment_method_id: str
    ):
        stripe.PaymentMethod.attach(
            payment_method=payment_method_id,
            customer=customer_id
        )

    def update_subscription_payment_method(
        self,
        subscription_id: str,
        payment_method_id: str
    ):
        return stripe.Subscription.modify(subscription_id,
                                          default_payment_method=payment_method_id)

    def retrieve_product_catalog(
            self,
            country_iso: str | None = None,
        ) -> list:
        try:
            if country_iso is None or country_iso.lower() == "us":
                country_iso = "default"

            products = stripe.Product.search(
                query=f"metadata['country_iso']:'{country_iso}' AND active:'true'"
            )

            if len(products['data']) == 0:
                # If no products are found for the specified country, fall back to the default product catalog
                products = stripe.Product.search(
                    query="metadata['country_iso']:'default' AND active:'true'"
                )

            product_prices = {}
            for product in products['data']:
                price = stripe.Price.retrieve(product['default_price']) # type: ignore
                currency = price['currency']
                formatted_price_amount = format_currency_amount(
                    amount=float(price['unit_amount']),
                    currency_code=currency
                )

                product_prices[product['id']] = { # type: ignore
                    "name": product['name'], # type: ignore
                    "description": product['description'], # type: ignore
                    "metadata": product['metadata'], # type: ignore
                    "price": {
                        "id": price['id'],
                        "unit_amount": formatted_price_amount,
                        "currency": price['currency'],
                        "recurring_interval": price['recurring']['interval'],
                    },
                }

            catalog = []
            for product_id, details in product_prices.items():
                catalog.append({
                    "product": details['name'],
                    "product_id": product_id,
                    "description": details['description'],
                    "price_data": details['price'],
                    "metadata": details['metadata'],
                })
            return catalog
        except Exception as e:
            error_country = None if country_iso is None else ""
            error_msg = f"Encountered an issue while retrieving product catalog for country {error_country}: {e}"
            raise RuntimeError(error_msg) from e

    def retrieve_price(self, price_id: str):
        return stripe.Price.retrieve(price_id)

    def attach_subscription_metadata(self, subscription_id: str, metadata: dict):
        stripe.Subscription.modify(subscription_id, metadata=metadata)

    def attach_payment_intent_metadata(self, payment_intent_id: str, metadata: dict):
        stripe.PaymentIntent.modify(payment_intent_id, metadata=metadata)

    def attach_invoice_metadata(self, invoice_id: str, metadata: dict):
        stripe.Invoice.modify(invoice_id, metadata=metadata)

    def retrieve_invoice(self, invoice_id: str):
        return stripe.Invoice.retrieve(invoice_id)

    def generate_payment_method_update_session(
        self,
        customer_id: str,
        success_url: str,
        cancel_url
    ) -> str:
        try:
            update_payment_method_session = stripe.checkout.Session.create(
                customer=customer_id,
                mode="setup",
                payment_method_types=["card"],
                success_url=success_url,
                cancel_url=cancel_url,
            )
            return update_payment_method_session['url']
        except Exception as e:
            raise RuntimeError(e) from e
