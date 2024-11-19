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
                                API_METHOD_GET,
                                API_METHOD_POST,
                                API_METHOD_PUT,
                                log_api_request,
                                log_api_response,
                                log_payment_event,
                                log_metadata_from_stripe_invoice_event,
                                log_metadata_from_stripe_subscription_event,
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
    existing_product_id: str
    new_price_id: str

class PaymentProcessingRouter:

    PAYMENT_SESSION_ENDPOINT = "/v1/payment-session"
    SUBSCRIPTIONS_ENDPOINT = "/v1/subscriptions"
    PAYMENT_EVENT_ENDPOINT = "/v1/payment-event"
    PRODUCT_CATALOG = "/v1/product-catalog"
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
            return await self._update_subscription_internal(authorization=authorization,
                                                            subscription_id=payload.subscription_id,
                                                            price_id=payload.new_price_id,
                                                            product_id=payload.existing_product_id,
                                                            background_tasks=background_tasks,
                                                            response=response,
                                                            session_id=session_id,
                                                            store_access_token=store_access_token,
                                                            store_refresh_token=store_refresh_token)

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

        @self.router.get(self.PRODUCT_CATALOG, tags=[self.ROUTER_TAG])
        async def retrieve_product_catalog(response: Response,
                                           background_tasks: BackgroundTasks,
                                           store_access_token: Annotated[str | None, Header()],
                                           store_refresh_token: Annotated[str | None, Header()],
                                           authorization: Annotated[Union[str, None], Cookie()] = None,
                                           session_id: Annotated[Union[str, None], Cookie()] = None):
            return await self._retrieve_product_catalog_internal(authorization=authorization,
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

            subscription_data = response['data']
            filtered_data = []
            for object in subscription_data:
                payment_method_id = object.get("default_payment_method")
                payment_method_data = stripe_client.retrieve_payment_method(payment_method_id)

                filtered_data.append({
                    "subscription_id": object['id'],
                    "price_id": object['plan']['id'],
                    "product_id": object['items']['data'][0]['id'],
                    "payment_method_data": {
                        "id": payment_method_data['id'],
                        "type": payment_method_data['type'],
                        "data": payment_method_data['card'],
                    },
                })

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

        return {"subscriptions": filtered_data}

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
            stripe_client.delete_customer_subscription(subscription_id=subscription_id)
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

    """
    Updates the incoming subscription ID with the incoming product information.

    Arguments:
    background_tasks – object for scheduling concurrent tasks.
    authorization – the authorization cookie, if exists.
    store_access_token – the store access token.
    store_refresh_token – the store refresh token.
    session_id – the session_id cookie, if exists.
    response – the response model with which to create the final response.
    subscription_id – the subscription to be deleted.
    product_id – the new product to be associated with the subscription.
    price_id – the new price_id to be associated with the subscription.
    """
    async def _update_subscription_internal(self,
                                            background_tasks: BackgroundTasks,
                                            authorization: str,
                                            store_access_token: str,
                                            store_refresh_token: str,
                                            session_id: str,
                                            response: Response,
                                            subscription_id: str,
                                            product_id: str,
                                            price_id: str):
        if not self._auth_manager.access_token_is_valid(authorization):
            raise AUTH_TOKEN_EXPIRED_ERROR

        if store_access_token is None or store_refresh_token is None:
            raise security.STORE_TOKENS_ERROR

        update_api_method = API_METHOD_PUT
        log_api_request(background_tasks=background_tasks,
                        session_id=session_id,
                        method=update_api_method,
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
                      method=update_api_method)
            raise security.STORE_TOKENS_ERROR

        try:
            stripe_client = dependency_container.inject_stripe_client()
            stripe_client.update_customer_subscription(subscription_id=subscription_id,
                                                       product_id=product_id,
                                                       price_id=price_id)
        except Exception as e:
            status_code = general_utilities.extract_status_code(e, fallback=status.HTTP_417_EXPECTATION_FAILED)
            message = str(e)
            log_error(background_tasks=background_tasks,
                      session_id=session_id,
                      endpoint_name=self.SUBSCRIPTIONS_ENDPOINT,
                      error_code=status_code,
                      description=message,
                      method=update_api_method)
            raise HTTPException(detail="Subscription not found", status_code=status_code)

        log_api_response(background_tasks=background_tasks,
                         session_id=session_id,
                         therapist_id=therapist_id,
                         endpoint_name=self.SUBSCRIPTIONS_ENDPOINT,
                         http_status_code=status.HTTP_200_OK,
                         method=update_api_method)

        return {}

    async def _retrieve_product_catalog_internal(self,
                                                 background_tasks: BackgroundTasks,
                                                 authorization: str,
                                                 store_access_token: str,
                                                 store_refresh_token: str,
                                                 session_id: str,
                                                 response: Response):
        if not self._auth_manager.access_token_is_valid(authorization):
            raise AUTH_TOKEN_EXPIRED_ERROR

        if store_access_token is None or store_refresh_token is None:
            raise security.STORE_TOKENS_ERROR

        get_api_method = API_METHOD_GET
        log_api_request(background_tasks=background_tasks,
                        session_id=session_id,
                        method=get_api_method,
                        endpoint_name=self.PRODUCT_CATALOG)

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
                      endpoint_name=self.PRODUCT_CATALOG,
                      error_code=status_code,
                      description=str(e),
                      method=get_api_method)
            raise security.STORE_TOKENS_ERROR

        try:
            stripe_client = dependency_container.inject_stripe_client()
            response = stripe_client.retrieve_product_catalog()
        except Exception as e:
            status_code = general_utilities.extract_status_code(e, fallback=status.HTTP_417_EXPECTATION_FAILED)
            message = str(e)
            log_error(background_tasks=background_tasks,
                      session_id=session_id,
                      endpoint_name=self.PRODUCT_CATALOG,
                      error_code=status_code,
                      description=message,
                      method=get_api_method)
            raise HTTPException(detail="Subscription not found", status_code=status_code)

        log_api_response(background_tasks=background_tasks,
                         session_id=session_id,
                         therapist_id=therapist_id,
                         endpoint_name=self.PRODUCT_CATALOG,
                         http_status_code=status.HTTP_200_OK,
                         method=get_api_method)

        return {"catalog": response}

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
            self._handle_stripe_event(event=event, background_tasks=background_tasks)
        except Exception as e:
            raise HTTPException(e)

        return {}

    # Private

    """
    Internal funnel for specific handlings of Stripe events.

    Arguments:
    event – the Stripe event.
    background_tasks – object for scheduling concurrent tasks.
    """
    def _handle_stripe_event(self,
                             event,
                             background_tasks: BackgroundTasks):
        event_type: str = event["type"]

        if event_type == 'checkout.session.completed':
            # Payment is successful and the subscription is created.
            # You should provision the subscription, grant access to the platform,
            # and save the customer ID to your database.
            checkout_session = event['data']['object']
            customer_id = checkout_session['customer']
            subscription_id = checkout_session.get('subscription')
            invoice_id = checkout_session.get('invoice')

            # Update the subscription with metadata
            if subscription_id:
                stripe_client = dependency_container.inject_stripe_client()
                metadata = checkout_session.get('metadata', {})
                stripe_client.attach_subscription_metadata(subscription_id=subscription_id,
                                                           metadata=metadata)
                therapist_id = None if 'therapist_id' not in metadata else metadata['therapist_id']
                session_id = None if 'session_id' not in metadata else metadata['session_id']
            else:
                therapist_id = None
                session_id = None

            try:
                price_id = checkout_session["line_items"]["data"][0]["price"]["id"]
            except:
                price_id = None

            log_payment_event(background_tasks=background_tasks,
                              event_name=event_type,
                              invoice_id=invoice_id,
                              customer_id=customer_id,
                              subscription_id=subscription_id,
                              price_id=price_id,
                              therapist_id=therapist_id,
                              session_id=session_id)
        elif event_type == 'invoice.created':
            invoice = event['data']['object']
            subscription_id = invoice.get('subscription')
            invoice_metadata = invoice.get("metadata", {})

            # If the invoice has no metadata, and a subscription exists, let's retrieve
            # the subscription object to attach its metadata to the invoice.
            if len(invoice_metadata) == 0 and len(subscription_id or '') > 0:
                stripe_client = dependency_container.inject_stripe_client()
                subscription = stripe_client.retrieve_subscription(subscription_id)
                invoice_metadata = subscription.get('metadata', {})
                stripe_client.attach_invoice_metadata(invoice_id=invoice['id'],
                                                      metadata=invoice_metadata)

            log_metadata_from_stripe_invoice_event(event=event,
                                                   metadata=invoice_metadata,
                                                   background_tasks=background_tasks)

        elif event_type == 'invoice.updated':
            invoice = event['data']['object']
            subscription_id = invoice.get('subscription')
            invoice_metadata = invoice.get("metadata", {})

            # If the invoice has no metadata, and a subscription exists, let's retrieve
            # the subscription object to attach its metadata to the invoice.
            if len(invoice_metadata) == 0 and len(subscription_id or '') > 0:
                stripe_client = dependency_container.inject_stripe_client()
                subscription = stripe_client.retrieve_subscription(subscription_id)
                invoice_metadata = subscription.get('metadata', {})
                stripe_client.attach_invoice_metadata(invoice_id=invoice['id'],
                                                      metadata=invoice_metadata)

            log_metadata_from_stripe_invoice_event(event=event,
                                                   metadata=invoice_metadata,
                                                   background_tasks=background_tasks)
        elif event_type == 'invoice.paid':
            # Log event, and send ChartWise receipt to user.
            # Update Subscription Renewal Date in any UI that may be showing it.
            invoice = event['data']['object']
            log_metadata_from_stripe_invoice_event(event=event,
                                                   metadata=invoice.get("metadata", {}),
                                                   background_tasks=background_tasks)
        elif event_type == 'invoice.upcoming':
            # Notify Customers of Upcoming Payment: Alert users of an upcoming charge
            # if you want to provide transparency or avoid surprises, especially
            # for annual subscriptions.
            invoice = event['data']['object']
            log_metadata_from_stripe_invoice_event(event=event,
                                                   metadata=invoice.get("metadata", {}),
                                                   background_tasks=background_tasks)
        elif event_type == 'invoice.payment_failed':
            # The payment failed or the customer does not have a valid payment method.
            # The subscription becomes past_due. Notify your customer and send them to the
            # customer portal to update their payment information.
            invoice = event['data']['object']
            log_metadata_from_stripe_invoice_event(event=event,
                                                   metadata=invoice.get("metadata", {}),
                                                   background_tasks=background_tasks)
        elif event_type == 'customer.subscription.created':
            # Handle Plan Upgrades/Downgrades: If a user changes their plan (e.g: monthly to annually),
            # this event lets you adjust access or resource allocations accordingly. You could also trigger
            # welcome or upsell emails when users upgrade.
            #
            # Detect Subscription Status Changes: If a subscription moves to past_due, you could set up
            # notifications or alerts.
            log_metadata_from_stripe_subscription_event(event=event,
                                                        background_tasks=background_tasks)
        elif event_type == 'customer.subscription.updated':
            # Handle Plan Upgrades/Downgrades: If a user changes their plan (e.g: monthly to annually),
            # this event lets you adjust access or resource allocations accordingly. You could also trigger
            # welcome or upsell emails when users upgrade.
            # 
            # Detect Subscription Status Changes: If a subscription moves to past_due, you could set up
            # notifications or alerts. 
            log_metadata_from_stripe_subscription_event(event=event,
                                                        background_tasks=background_tasks)
        elif event_type == 'customer.subscription.paused':
            # Send an automated email confirming the pause.
            log_metadata_from_stripe_subscription_event(event=event,
                                                        background_tasks=background_tasks)
        elif event_type == 'customer.subscription.deleted':
            # Send an automated email confirming the cancellation, offering a reactivation discount,
            # or sharing helpful info about resuming their subscription in the future.
            log_metadata_from_stripe_subscription_event(event=event,
                                                        background_tasks=background_tasks)
        else:
            print(f"[Stripe Event] Unhandled event type: '{event_type}'")
