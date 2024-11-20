import os, stripe
from babel.numbers import format_currency, get_currency_precision

from ..api.stripe_base_class import StripeBaseClass

class StripeClient(StripeBaseClass):

    FREE_TRIAL_DURATION_IN_DAYS = 30

    def __init__(self):
        stripe.api_key = os.environ.get("STRIPE_API_KEY")

    def generate_checkout_session(self,
                                 session_id: str,
                                 therapist_id: str,
                                 price_id: str,
                                 success_url: str,
                                 cancel_url: str) -> str | None:
        try:
            checkout_session = stripe.checkout.Session.create(
                success_url=success_url,
                cancel_url=cancel_url,
                mode='subscription',
                line_items=[{
                    'price': price_id,
                    'quantity': 1
                }],
                subscription_data={
                    'trial_period_days': self.FREE_TRIAL_DURATION_IN_DAYS
                },
                 metadata={
                    'session_id': str(session_id),
                    'therapist_id': str(therapist_id)
                }
            )
            return checkout_session['url']
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

    def retrieve_subscription(self, subscription_id):
        return stripe.Subscription.retrieve(subscription_id)

    def retrieve_payment_method(self, payment_method_id):
        return stripe.PaymentMethod.retrieve(payment_method_id)

    def retrieve_product(self, product_id):
        return stripe.Product.retrieve(id=product_id)

    def retrieve_customer_subscriptions(self, customer_id: str) -> dict:
        return stripe.Subscription.list(customer=customer_id)

    def delete_customer_subscription(self, subscription_id: str):
        return stripe.Subscription.modify(subscription_id,
                                          cancel_at_period_end=True)

    def update_customer_subscription_plan(self,
                                          subscription_id: str,
                                          product_id: str,
                                          price_id: str):
        return stripe.Subscription.modify(subscription_id,
                                          items=[{"id": product_id, "price": price_id}])

    def update_subscription_payment_method(self,
                                           subscription_id: str,
                                           payment_method_id: str):
        return stripe.Subscription.modify(subscription_id,
                                          default_payment_method=payment_method_id)

    def retrieve_product_catalog(self) -> list:
        products = stripe.Product.list(active=True)
        product_prices = {}

        for product in products['data']:
            prices = stripe.Price.list(product=product['id'])
            product_prices[product['id']] = {
                "name": product['name'],
                "description": product['description'],
                "metadata": product['metadata'],
                "prices": [
                    {
                        "id": price['id'],
                        "unit_amount": price['unit_amount'],
                        "currency": price['currency'],
                        "recurring_interval": price['recurring']['interval'],
                    }
                    for price in prices['data']
                ],
            }

        catalog = []
        for product_id, details in product_prices.items():
            price_data = []
            for price in details['prices']:
                currency = price['currency']
                formatted_amount = self._format_currency_amount(amount=float(price['unit_amount']),
                                                                currency_code=currency)
                price_data.append({
                    "price_id": price['id'],
                    "amount": formatted_amount,
                    "currency": currency,
                    "recurring_interval": price['recurring_interval']
                })

            catalog.append({
                "product": details['name'],
                "product_id": product_id,
                "description": details['description'],
                "price_data": price_data,
                "metadata": details['metadata'],
            })
        return catalog

    def attach_subscription_metadata(self, subscription_id: str, metadata: dict):
        stripe.Subscription.modify(subscription_id, metadata=metadata)

    def attach_invoice_metadata(self, invoice_id: str, metadata: dict):
        res = stripe.Invoice.modify(invoice_id, metadata=metadata)

    def generate_payment_method_update_session(self,
                                               customer_id: str,
                                               success_url: str,
                                               cancel_url) -> str:
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
            raise Exception(e)

    # Private

    def _format_currency_amount(self, amount: float, currency_code: str) -> str:
        # Get the currency precision (e.g., 2 for USD, 0 for JPY)
        precision = get_currency_precision(currency_code.upper())

        # Convert the amount to the main currency unit
        divisor = 10 ** precision
        amount = amount / divisor

        # Format the currency
        return format_currency(number=amount, currency=currency_code.upper(), locale='en_US')
