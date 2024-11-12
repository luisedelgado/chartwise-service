import os

from fastapi import (APIRouter,
                     BackgroundTasks,
                     Cookie,
                     HTTPException,
                     Request,
                     Response)
from pydantic import BaseModel
from typing import Annotated, Union

from ..internal.dependency_container import dependency_container
from ..internal.security import AUTH_TOKEN_EXPIRED_ERROR
from ..managers.auth_manager import AuthManager

class PaymentSessionPayload(BaseModel):
    price_id: str
    success_callback_url: str
    cancel_callback_url: str

class PaymentProcessingRouter:

    PAYMENT_PROCESSING_ENDPOINT = "/v1/payment-session"
    PAYMENT_EVENT_ENDPOINT = "/v1/payment-event"
    ROUTER_TAG = "payments"

    def __init__(self, environment: str):
        self._environment = environment
        self._auth_manager = AuthManager()
        self.router = APIRouter()
        self._register_routes()

    """
    Registers the set of routes that the class' router can access.
    """
    def _register_routes(self):
        @self.router.post(self.PAYMENT_PROCESSING_ENDPOINT, tags=[self.ROUTER_TAG])
        def create_payment_session(response: Response,
                                   payload: PaymentSessionPayload,
                                   background_tasks: BackgroundTasks,
                                   authorization: Annotated[Union[str, None], Cookie()] = None,
                                   session_id: Annotated[Union[str, None], Cookie()] = None):
            return self._create_payment_session_internal(authorization=authorization,
                                                         payload=payload)

        @self.router.post(self.PAYMENT_EVENT_ENDPOINT, tags=[self.ROUTER_TAG])
        async def capture_payment_event(request: Request,
                                        response: Response,
                                        background_tasks: BackgroundTasks,
                                        authorization: Annotated[Union[str, None], Cookie()] = None,
                                        session_id: Annotated[Union[str, None], Cookie()] = None):
            return await self._capture_payment_event_internal(request=request)

    def _create_payment_session_internal(self,
                                         authorization: str,
                                         payload: PaymentSessionPayload):
        if not self._auth_manager.access_token_is_valid(authorization):
            raise AUTH_TOKEN_EXPIRED_ERROR

        stripe_client = dependency_container.inject_stripe_client()
        return {
            "payment_session_url": stripe_client.generate_payment_session(price_id=payload.price_id)
        }

    async def _capture_payment_event_internal(self,
                                             request: Request):
        stripe_client = dependency_container.inject_stripe_client()
        payload = await request.body()
        sig_header = request.headers.get("stripe-signature")

        try:
            webhook_secret = os.environ.get('STRIPE_WEBHOOK_SECRET')
            event = stripe_client.construct_webhook_event(payload=payload,
                                                          sig_header=sig_header,
                                                          webhook_secret=webhook_secret)
        except ValueError:
            # Invalid payload
            raise HTTPException(status_code=400, detail="Invalid payload")
        except stripe_client.error.SignatureVerificationError:
            # Invalid signature
            raise HTTPException(status_code=400, detail="Invalid signature")

        # Process the event based on its type
        event_type = event["type"]
        data_object = event["data"]["object"]
        self._handle_stripe_event(event_type=event_type,
                                  data_object=data_object)

        return {"status": "success"}

    def _handle_stripe_event(self, event_type: str, data_object):
        if event_type == 'checkout.session.completed':
            # Payment is successful and the subscription is created.
            # You should provision the subscription, grant access to the platform,
            # and save the customer ID to your database.
            print("Checkout session completed!")
        elif event_type == 'invoice.payment_succeeded':
            # Log event, and send ChartWise receipt to user.
            # Update Subscription Renewal Date in any UI that may be showing it.
            print("Invoice payment_succeeded!")
        elif event_type == 'invoice.upcoming':
            # Notify Customers of Upcoming Payment: Alert users of an upcoming charge
            # if you want to provide transparency or avoid surprises, especially
            # for annual subscriptions.
            print("upcoming!")
        elif event_type == 'invoice.payment_failed':
            # The payment failed or the customer does not have a valid payment method.
            # The subscription becomes past_due. Notify your customer and send them to the
            # customer portal to update their payment information.
            print("Invoice payment failed!")
        elif event_type == 'customer.subscription.updated':
            # Handle Plan Upgrades/Downgrades: If a user changes their plan (e.g: monthly to annually),
            # this event lets you adjust access or resource allocations accordingly. You could also trigger
            # welcome or upsell emails when users upgrade.
            # 
            # Detect Subscription Status Changes: If a subscription moves to past_due, you could set up
            # notifications or alerts. 
            print("Subscription updated!")
        elif event_type == 'customer.subscription.paused':
            # Send an automated email confirming the pause.
            print("Subscription paused!")
        elif event_type == 'customer.subscription.deleted':
            # Send an automated email confirming the cancellation, offering a reactivation discount,
            # or sharing helpful info about resuming their subscription in the future.
            print("Subscription deleted!")
        else:
            print(f'Unhandled event type {event_type}')
