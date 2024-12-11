import os, stripe

from ..api.stripe_base_class import StripeBaseClass
from ...internal.utilities.general_utilities import format_currency_amount

class StripeClient(StripeBaseClass):

    FREE_TRIAL_DURATION_IN_DAYS = 30

    def __init__(self):
        stripe.api_key = os.environ.get("STRIPE_API_KEY")

    def generate_checkout_session(self,
                                  session_id: str,
                                  therapist_id: str,
                                  price_id: str,
                                  success_url: str,
                                  cancel_url: str,
                                  is_new_customer: bool) -> str | None:
        try:
            if is_new_customer:
                subscription_data = {
                    'trial_period_days': self.FREE_TRIAL_DURATION_IN_DAYS
                }
            else:
                subscription_data = {}

            checkout_session = stripe.checkout.Session.create(
                success_url=success_url,
                cancel_url=cancel_url,
                mode='subscription',
                line_items=[{
                    'price': price_id,
                    'quantity': 1
                }],
                subscription_data=subscription_data,
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
        return stripe.Product.retrieve(product_id)

    def retrieve_customer_subscriptions(self, customer_id: str) -> dict:
        return stripe.Subscription.list(customer=customer_id)

    def retrieve_payment_intent_history(self,
                                        customer_id: str,
                                        limit: int,
                                        starting_after: str | None):
        return stripe.PaymentIntent.list(customer=customer_id,
                                         limit=limit,
                                         starting_after=starting_after)

    def cancel_customer_subscription(self, subscription_id: str):
        return stripe.Subscription.modify(subscription_id,
                                          cancel_at_period_end=True)

    def delete_customer_subscription_immediately(self, subscription_id: str):
        return stripe.Subscription.cancel(subscription_id)

    def update_customer_subscription_plan(self,
                                          subscription_id: str,
                                          subscription_item_id: str,
                                          price_id: str):
        stripe.Subscription.modify(subscription_id,
                                   items=[{"id": subscription_item_id, "price": price_id}])

    def update_subscription_payment_method(self,
                                           subscription_id: str,
                                           payment_method_id: str):
        return stripe.Subscription.modify(subscription_id,
                                          default_payment_method=payment_method_id)

    def retrieve_product_catalog(self) -> list:
        products = stripe.Product.list(active=True)
        product_prices = {}

        for product in products['data']:
            price = stripe.Price.retrieve(product['default_price'])
            currency = price['currency']
            formatted_price_amount = format_currency_amount(amount=float(price['unit_amount']),
                                                            currency_code=currency)

            product_prices[product['id']] = {
                "name": product['name'],
                "description": product['description'],
                "metadata": product['metadata'],
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
