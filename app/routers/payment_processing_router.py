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
from typing import Annotated, Tuple, Union

from ..internal import security
from ..internal.dependency_container import dependency_container
from ..internal.logging import (API_METHOD_DELETE,
                                API_METHOD_POST,
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

class UpdateSubscriptionPayload(BaseModel):
    subscription_id: str

class PaymentProcessingRouter:

    PAYMENT_SESSION_ENDPOINT = "/v1/payment-session"
    SUBSCRIPTIONS_ENDPOINT = "/v1/subscriptions"
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

        @self.router.get(self.SUBSCRIPTIONS_ENDPOINT, tags=[self.ROUTER_TAG])
        async def retrieve_subscriptions(response: Response,
                                         background_tasks: BackgroundTasks,
                                         store_access_token: Annotated[str | None, Header()],
                                         store_refresh_token: Annotated[str | None, Header()],
                                         customer_id: str = None,
                                         authorization: Annotated[Union[str, None], Cookie()] = None,
                                         session_id: Annotated[Union[str, None], Cookie()] = None):
            return await self._retrieve_subscriptions_internal(authorization=authorization,
                                                               customer_id=customer_id,
                                                               background_tasks=background_tasks,
                                                               response=response,
                                                               session_id=session_id,
                                                               store_access_token=store_access_token,
                                                               store_refresh_token=store_refresh_token)

        @self.router.put(self.SUBSCRIPTIONS_ENDPOINT, tags=[self.ROUTER_TAG])
        async def update_subscription(payload: UpdateSubscriptionPayload,
                                      response: Response,
                                      background_tasks: BackgroundTasks,
                                      store_access_token: Annotated[str | None, Header()],
                                      store_refresh_token: Annotated[str | None, Header()],
                                      authorization: Annotated[Union[str, None], Cookie()] = None,
                                      session_id: Annotated[Union[str, None], Cookie()] = None):
            return await self._update_subscription_internal()

        @self.router.delete(self.SUBSCRIPTIONS_ENDPOINT, tags=[self.ROUTER_TAG])
        async def delete_subscription(response: Response,
                                      background_tasks: BackgroundTasks,
                                      store_access_token: Annotated[str | None, Header()],
                                      store_refresh_token: Annotated[str | None, Header()],
                                      subscription_id: str = None,
                                      authorization: Annotated[Union[str, None], Cookie()] = None,
                                      session_id: Annotated[Union[str, None], Cookie()] = None):
            return await self._delete_subscription_internal(authorization=authorization,
                                                            subscription_id=subscription_id,
                                                            background_tasks=background_tasks,
                                                            response=response,
                                                            session_id=session_id,
                                                            store_access_token=store_access_token,
                                                            store_refresh_token=store_refresh_token)

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
    Retrieves the set of subscriptions associated with the incoming customer ID.

    Arguments:
    background_tasks – object for scheduling concurrent tasks.
    authorization – the authorization cookie, if exists.
    store_access_token – the store access token.
    store_refresh_token – the store refresh token.
    session_id – the session_id cookie, if exists.
    response – the response model with which to create the final response.
    customer_id – the customer_id to be used for fetching subscriptions.
    """
    async def _retrieve_subscriptions_internal(self,
                                               background_tasks: BackgroundTasks,
                                               authorization: str,
                                               store_access_token: str,
                                               store_refresh_token: str,
                                               session_id: str,
                                               response: Response,
                                               customer_id: str):
        if not self._auth_manager.access_token_is_valid(authorization):
            raise AUTH_TOKEN_EXPIRED_ERROR

        if store_access_token is None or store_refresh_token is None:
            raise security.STORE_TOKENS_ERROR

        post_api_method = API_METHOD_POST
        log_api_request(background_tasks=background_tasks,
                        session_id=session_id,
                        method=post_api_method,
                        endpoint_name=self.SUBSCRIPTIONS_ENDPOINT)

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
                      endpoint_name=self.SUBSCRIPTIONS_ENDPOINT,
                      error_code=status_code,
                      description=str(e),
                      method=post_api_method)
            raise security.STORE_TOKENS_ERROR

        try:
            stripe_client = dependency_container.inject_stripe_client()
            response = stripe_client.retrieve_customer_subscriptions(customer_id=customer_id)
        except Exception as e:
            status_code = general_utilities.extract_status_code(e, fallback=status.HTTP_417_EXPECTATION_FAILED)
            message = str(e)
            log_error(background_tasks=background_tasks,
                      session_id=session_id,
                      endpoint_name=self.SUBSCRIPTIONS_ENDPOINT,
                      error_code=status_code,
                      description=message,
                      method=post_api_method)
            raise HTTPException(detail=message, status_code=status_code)

        log_api_response(background_tasks=background_tasks,
                         session_id=session_id,
                         therapist_id=therapist_id,
                         endpoint_name=self.SUBSCRIPTIONS_ENDPOINT,
                         http_status_code=status.HTTP_200_OK,
                         method=post_api_method)

        return {"subscriptions": response}

    """
    Deletes the subscriptions associated with the incoming ID.

    Arguments:
    background_tasks – object for scheduling concurrent tasks.
    authorization – the authorization cookie, if exists.
    store_access_token – the store access token.
    store_refresh_token – the store refresh token.
    session_id – the session_id cookie, if exists.
    response – the response model with which to create the final response.
    subscription_id – the subscription to be deleted.
    """
    async def _delete_subscription_internal(self,
                                            background_tasks: BackgroundTasks,
                                            authorization: str,
                                            store_access_token: str,
                                            store_refresh_token: str,
                                            session_id: str,
                                            response: Response,
                                            subscription_id: str):
        if not self._auth_manager.access_token_is_valid(authorization):
            raise AUTH_TOKEN_EXPIRED_ERROR

        if store_access_token is None or store_refresh_token is None:
            raise security.STORE_TOKENS_ERROR

        delete_api_method = API_METHOD_DELETE
        log_api_request(background_tasks=background_tasks,
                        session_id=session_id,
                        method=delete_api_method,
                        endpoint_name=self.SUBSCRIPTIONS_ENDPOINT)

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
                      endpoint_name=self.SUBSCRIPTIONS_ENDPOINT,
                      error_code=status_code,
                      description=str(e),
                      method=delete_api_method)
            raise security.STORE_TOKENS_ERROR

        try:
            stripe_client = dependency_container.inject_stripe_client()
            delete_success: bool = stripe_client.delete_customer_subscription(subscription_id=subscription_id)
        except Exception as e:
            status_code = general_utilities.extract_status_code(e, fallback=status.HTTP_417_EXPECTATION_FAILED)
            message = str(e)
            log_error(background_tasks=background_tasks,
                      session_id=session_id,
                      endpoint_name=self.SUBSCRIPTIONS_ENDPOINT,
                      error_code=status_code,
                      description=message,
                      method=delete_api_method)
            raise HTTPException(detail="Subscription not found", status_code=status_code)

        log_api_response(background_tasks=background_tasks,
                         session_id=session_id,
                         therapist_id=therapist_id,
                         endpoint_name=self.SUBSCRIPTIONS_ENDPOINT,
                         http_status_code=status.HTTP_200_OK,
                         method=delete_api_method)

        return {}

    async def _update_subscription_internal(self):
        ...

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

        try:
            self._handle_stripe_event(event)
        except Exception as e:
            print(f"EXCEPTION = {e}")
            raise HTTPException(e)

        return {}

    # Private

    def _get_metadata_from_invoice_event(self, event) -> Tuple[str | None, str | None]:
        invoice = event['data']['object']

        if not 'checkout_session' in invoice.get('metadata', {}):
            return (None, None)

        stripe_session_id = invoice['metadata']['checkout_session']

        stripe_client = dependency_container.inject_stripe_client()
        session = stripe_client.retrieve_session(stripe_session_id)
        metadata = session.get('metadata', {})
        if 'therapist_id' not in metadata and 'session_id' in metadata:
            return (None, metadata['session_id'])
        if 'therapist_id' in metadata and 'session_id' not in metadata:
            return (metadata['therapist_id'], None)
        if 'therapist_id' not in metadata and 'session_id' not in metadata:
            return (None, None)
        return (metadata['therapist_id'], metadata['session_id'])

    def _get_metadata_from_subscription_event(self, event) -> Tuple[str | None, str | None]:
        subscription = event['data']['object']
        metadata = subscription.get('metadata', {})
        if 'therapist_id' not in metadata and 'session_id' in metadata:
            return (None, metadata['session_id'])
        if 'therapist_id' in metadata and 'session_id' not in metadata:
            return (metadata['therapist_id'], None)
        if 'therapist_id' not in metadata and 'session_id' not in metadata:
            return (None, None)
        return (metadata['therapist_id'], metadata['session_id'])

    def _handle_stripe_event(self, event):
        event_type: str = event["type"]

        if event_type == 'checkout.session.completed':
            # Payment is successful and the subscription is created.
            # You should provision the subscription, grant access to the platform,
            # and save the customer ID to your database.
            data_object = event["data"]["object"]
            metadata = data_object['metadata']
            therapist_id = None if 'therapist_id' not in metadata else metadata['therapist_id']
            session_id = None if 'session_id' not in metadata else metadata['session_id']

            # Update the subscription with metadata
            subscription_id = data_object.get('subscription')
            if subscription_id:
                stripe_client = dependency_container.inject_stripe_client()
                stripe_client.add_subscription_metadata(subscription_id=subscription_id,
                                                        metadata=data_object.get('metadata', {}))

            return

        if event_type == 'invoice.created':
            invoice = event['data']['object']
            subscription_id = invoice.get('subscription')

            print("INVOICE CREATED")
            print(f"{invoice}")
            # if subscription_id:
            #     # Retrieve the subscription to access its metadata
            #     print(f"ABOUT TO RETRIEVE SESSION WITH ID: {subscription_id}")
            #     stripe_client = dependency_container.inject_stripe_client()
            #     subscription = stripe_client.retrieve_session(subscription_id)
            #     print("ABOUT TO ATTACH METADATA TO INVOICE")
            #     stripe_client.add_invoice_metadata(invoice_id=invoice['id'],
            #                                        metadata=subscription.get('metadata', {}))
        elif event_type == 'invoice.updated':
            invoice = event['data']['object']
            subscription_id = invoice.get('subscription')

            print("INVOICE UPDATED")
            print(f"{invoice}")
            # if subscription_id:
            #     # Retrieve the subscription to access its metadata
            #     print(f"ABOUT TO RETRIEVE SESSION WITH ID: {subscription_id}")
            #     stripe_client = dependency_container.inject_stripe_client()
            #     subscription = stripe_client.retrieve_session(subscription_id)
            #     print("ABOUT TO ATTACH METADATA TO INVOICE")
            #     stripe_client.add_invoice_metadata(invoice_id=invoice['id'],
            #                                        metadata=subscription.get('metadata', {}))
        elif event_type == 'invoice.paid':
            # Log event, and send ChartWise receipt to user.
            # Update Subscription Renewal Date in any UI that may be showing it.
            # metadata = self._get_metadata_from_invoice_event(event)
            # therapist_id = metadata['therapist_id']
            # session_id = metadata['session_id']
            # print(f"THERAPIST_ID: {therapist_id}")
            # print(f"SESSION_ID: {session_id}")
            print("Invoice payment_succeeded!")
        elif event_type == 'invoice.upcoming':
            # Notify Customers of Upcoming Payment: Alert users of an upcoming charge
            # if you want to provide transparency or avoid surprises, especially
            # for annual subscriptions.
            # metadata = self._get_metadata_from_invoice_event(event)
            # therapist_id = metadata['therapist_id']
            # session_id = metadata['session_id']
            # print(f"THERAPIST_ID: {therapist_id}")
            # print(f"SESSION_ID: {session_id}")
            print("upcoming!")
        elif event_type == 'invoice.payment_failed':
            # The payment failed or the customer does not have a valid payment method.
            # The subscription becomes past_due. Notify your customer and send them to the
            # customer portal to update their payment information.
            # metadata = self._get_metadata_from_invoice_event(event)
            # therapist_id = metadata['therapist_id']
            # session_id = metadata['session_id']
            # print(f"THERAPIST_ID: {therapist_id}")
            # print(f"SESSION_ID: {session_id}")
            print("Invoice payment failed!")
        elif event_type == 'customer.subscription.created':
            # Handle Plan Upgrades/Downgrades: If a user changes their plan (e.g: monthly to annually),
            # this event lets you adjust access or resource allocations accordingly. You could also trigger
            # welcome or upsell emails when users upgrade.
            #
            # Detect Subscription Status Changes: If a subscription moves to past_due, you could set up
            # notifications or alerts.
            therapist_id, session_id = self._get_metadata_from_subscription_event(event)
            print("Subscription created!")
        elif event_type == 'customer.subscription.updated':
            # Handle Plan Upgrades/Downgrades: If a user changes their plan (e.g: monthly to annually),
            # this event lets you adjust access or resource allocations accordingly. You could also trigger
            # welcome or upsell emails when users upgrade.
            # 
            # Detect Subscription Status Changes: If a subscription moves to past_due, you could set up
            # notifications or alerts. 
            therapist_id, session_id = self._get_metadata_from_subscription_event(event)
            print("Subscription updated!")
        elif event_type == 'customer.subscription.paused':
            # Send an automated email confirming the pause.
            therapist_id, session_id = self._get_metadata_from_subscription_event(event)
            print("Subscription paused!")
        elif event_type == 'customer.subscription.deleted':
            # Send an automated email confirming the cancellation, offering a reactivation discount,
            # or sharing helpful info about resuming their subscription in the future.
            therapist_id, session_id = self._get_metadata_from_subscription_event(event)
            print("Subscription deleted!")
        else:
            print(f'Unhandled event type {event_type}')
