import os

from fastapi import (APIRouter,
                     BackgroundTasks,
                     Cookie,
                     Header,
                     HTTPException,
                     Request,
                     Response,
                     status)
from pydantic import BaseModel
from typing import Annotated, Union

from ..internal import security
from ..internal.dependency_container import dependency_container
from ..internal.logging import (API_METHOD_POST,
                                log_api_request,
                                log_api_response,
                                log_error)
from ..internal.security import AUTH_TOKEN_EXPIRED_ERROR
from ..internal.utilities import general_utilities
from ..managers.auth_manager import AuthManager

class PaymentSessionPayload(BaseModel):
    price_id: str
    success_callback_url: str
    cancel_callback_url: str

class PaymentProcessingRouter:

    PAYMENT_SESSION_ENDPOINT = "/v1/payment-session"
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
        @self.router.post(self.PAYMENT_SESSION_ENDPOINT, tags=[self.ROUTER_TAG])
        async def create_payment_session(response: Response,
                                         payload: PaymentSessionPayload,
                                         background_tasks: BackgroundTasks,
                                         store_access_token: Annotated[str | None, Header()],
                                         store_refresh_token: Annotated[str | None, Header()],
                                         authorization: Annotated[Union[str, None], Cookie()] = None,
                                         session_id: Annotated[Union[str, None], Cookie()] = None):
            return await self._create_payment_session_internal(authorization=authorization,
                                                               payload=payload,
                                                               background_tasks=background_tasks,
                                                               response=response,
                                                               session_id=session_id,
                                                               store_access_token=store_access_token,
                                                               store_refresh_token=store_refresh_token)

        @self.router.post(self.PAYMENT_EVENT_ENDPOINT, tags=[self.ROUTER_TAG])
        async def capture_payment_event(request: Request,
                                        background_tasks: BackgroundTasks):
            return await self._capture_payment_event_internal(request=request,
                                                              background_tasks=background_tasks)

    """
    Creates a new payment session.

    Arguments:
    background_tasks – object for scheduling concurrent tasks.
    authorization – the authorization cookie, if exists.
    store_access_token – the store access token.
    store_refresh_token – the store refresh token.
    session_id – the session_id cookie, if exists.
    response – the response model with which to create the final response.
    payload – the incoming request's payload.
    """
    async def _create_payment_session_internal(self,
                                               background_tasks: BackgroundTasks,
                                               authorization: str,
                                               store_access_token: str,
                                               store_refresh_token: str,
                                               session_id: str,
                                               response: Response,
                                               payload: PaymentSessionPayload):
        if not self._auth_manager.access_token_is_valid(authorization):
            raise AUTH_TOKEN_EXPIRED_ERROR

        if store_access_token is None or store_refresh_token is None:
            raise security.STORE_TOKENS_ERROR

        post_api_method = API_METHOD_POST
        log_api_request(background_tasks=background_tasks,
                        session_id=session_id,
                        method=post_api_method,
                        endpoint_name=self.PAYMENT_SESSION_ENDPOINT)

        try:
            supabase_client = dependency_container.inject_supabase_client_factory().supabase_user_client(access_token=store_access_token,
                                                                                                         refresh_token=store_refresh_token)
            therapist_id = supabase_client.get_current_user_id()
            await self._auth_manager.refresh_session(user_id=therapist_id,
                                                     response=response)
        except Exception as e:
            status_code = general_utilities.extract_status_code(e, fallback=status.HTTP_401_UNAUTHORIZED)
            log_error(background_tasks=background_tasks,
                      session_id=session_id,
                      endpoint_name=self.PAYMENT_SESSION_ENDPOINT,
                      error_code=status_code,
                      description=str(e),
                      method=post_api_method)
            raise security.STORE_TOKENS_ERROR

        try:
            stripe_client = dependency_container.inject_stripe_client()
            payment_session_url = stripe_client.generate_payment_session(price_id=payload.price_id,
                                                                         session_id=session_id,
                                                                         therapist_id=therapist_id,
                                                                         success_url=payload.success_callback_url,
                                                                         cancel_url=payload.cancel_callback_url)
            assert len(payment_session_url or '') > 0, "Received invalid checkout URL"
        except Exception as e:
            status_code = general_utilities.extract_status_code(e, fallback=status.HTTP_417_EXPECTATION_FAILED)
            message = str(e)
            log_error(background_tasks=background_tasks,
                      session_id=session_id,
                      endpoint_name=self.PAYMENT_SESSION_ENDPOINT,
                      error_code=status_code,
                      description=message,
                      method=post_api_method)
            raise HTTPException(detail=message, status_code=status_code)

        log_api_response(background_tasks=background_tasks,
                         session_id=session_id,
                         therapist_id=therapist_id,
                         endpoint_name=self.PAYMENT_SESSION_ENDPOINT,
                         http_status_code=status.HTTP_200_OK,
                         method=post_api_method)

        return {"payment_session_url": payment_session_url}

    """
    Webhook for handling Stripe events.

    Arguments:
    background_tasks – object for scheduling concurrent tasks.
    request – the incoming request object.
    """
    async def _capture_payment_event_internal(self,
                                              request: Request,
                                              background_tasks: BackgroundTasks):
        stripe_client = dependency_container.inject_stripe_client()

        try:
            environment = os.environ.get('ENVIRONMENT')
            if environment == "prod":
                webhook_secret = os.getenv("STRIPE_WEBHOOK_SECRET_PROD")
            elif environment == "staging":
                webhook_secret = os.getenv("STRIPE_WEBHOOK_SECRET_STAGING")
            else:
                webhook_secret = os.getenv("STRIPE_WEBHOOK_SECRET_DEV")

            payload = await request.body()
            sig_header = request.headers.get("stripe-signature")
            event = stripe_client.construct_webhook_event(payload=payload,
                                                          sig_header=sig_header,
                                                          webhook_secret=webhook_secret)
        except ValueError:
            # Invalid payload
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid payload")
        except Exception as e:
            # Check for invalid signature
            if stripe_client.is_signature_verification_error(e=e):
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid signature")
            else:
                raise HTTPException(status_code=status.HTTP_417_EXPECTATION_FAILED, detail="Expectation failed")

        # Process the event based on its type
        event_type = event["type"]
        data_object = event["data"]["object"]
        metadata = data_object['metadata']
        therapist_id = None if 'user_id' not in metadata else metadata['user_id']
        session_id = None if 'session_id' not in metadata else metadata['session_id']

        post_api_method = API_METHOD_POST
        log_api_request(background_tasks=background_tasks,
                        session_id=session_id,
                        therapist_id=therapist_id,
                        method=post_api_method,
                        endpoint_name=self.PAYMENT_EVENT_ENDPOINT)

        self._handle_stripe_event(event_type=event_type,
                                  data_object=data_object)

        log_api_response(background_tasks=background_tasks,
                         session_id=session_id,
                         therapist_id=therapist_id,
                         endpoint_name=self.PAYMENT_EVENT_ENDPOINT,
                         http_status_code=status.HTTP_200_OK,
                         method=post_api_method)

        return {}

    # Private

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
