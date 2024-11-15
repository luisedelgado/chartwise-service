import os, stripe

from ..api.stripe_base_class import StripeBaseClass

class StripeClient(StripeBaseClass):

    def __init__(self):
        stripe.api_key = os.environ.get("STRIPE_API_KEY")

    def generate_payment_session(self,
                                 session_id: str,
                                 therapist_id: str,
                                 price_id: str,
                                 success_url: str,
                                 cancel_url: str) -> str | None:
        try:
            session = stripe.checkout.Session.create(
                success_url=success_url,
                cancel_url=cancel_url,
                mode='subscription',
                line_items=[{
                    'price': price_id,
                    'quantity': 1
                }],
                 metadata={
                    'session_id': str(session_id),
                    'therapist_id': str(therapist_id)
                }
            )
            return session['url']
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

    def retrieve_customer_subscriptions(self, customer_id: str) -> dict:
        return stripe.Subscription.list(customer=customer_id)

    def delete_customer_subscription(self, subscription_id: str):
        return stripe.Subscription.modify(subscription_id,
                                          cancel_at_period_end=True)

    def update_customer_subscription(self,
                                     subscription_id: str,
                                     product_id: str,
                                     price_id: str):
        return stripe.Subscription.modify(subscription_id,
                                          items=[{"id": product_id, "price": price_id}])

    def retrieve_product_catalog(self) -> list:
        products = stripe.Product.list(active=True)
        product_prices = {}

        for product in products['data']:
            prices = stripe.Price.list(product=product['id'])
            product_prices[product['id']] = {
                "name": product['name'],
                "description": product['description'],
                "prices": [
                    {
                        "id": price['id'],
                        "unit_amount": price['unit_amount'],
                        "currency": price['currency'],
                        "recurring_interval": price['recurring']['interval'],  # Optional for recurring prices
                    }
                    for price in prices['data']
                ],
            }

        catalog = []
        for product_id, details in product_prices.items():
            price_data = []
            for price in details['prices']:
                price_data.append({
                    "price_id": price['id'],
                    "amount": f"{price['unit_amount']}",
                    "currency": price['currency'],
                    "recurring_interval": price['recurring_interval']
                })

            catalog.append({
                "product": details['name'],
                "product_id": product_id,
                "description": details['description'],
                "price_data": price_data
            })
        return catalog

    def add_subscription_metadata(self, subscription_id: str, metadata: dict):
        stripe.Subscription.modify(subscription_id, metadata=metadata)

    def add_invoice_metadata(self, invoice_id: str, metadata: dict):
        res = stripe.Invoice.modify(invoice_id, metadata=metadata)
        print(res)
