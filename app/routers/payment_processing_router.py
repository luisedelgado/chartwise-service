import logging, os

from enum import Enum
from datetime import datetime
from fastapi import (APIRouter,
                     BackgroundTasks,
                     Cookie,
                     Header,
                     HTTPException,
                     Request,
                     Response,
                     status)
from pydantic import BaseModel
from typing import Annotated, Optional, Union

from ..dependencies.dependency_container import dependency_container, StripeBaseClass
from ..internal.internal_alert import CustomerRelationsAlert, PaymentsActivityAlert
from ..internal.schemas import DEV_ENVIRONMENT, PROD_ENVIRONMENT, STAGING_ENVIRONMENT
from ..internal.security.security_schema import AUTH_TOKEN_EXPIRED_ERROR, STORE_TOKENS_ERROR
from ..internal.utilities import datetime_handler, general_utilities
from ..internal.utilities.datetime_handler import DATE_FORMAT
from ..managers.auth_manager import AuthManager
from ..managers.email_manager import EmailManager

class PaymentSessionPayload(BaseModel):
    price_id: str
    success_callback_url: str
    cancel_callback_url: str

class UpdateSubscriptionBehavior(Enum):
    UNSPECIFIED = "unspecified"
    CHANGE_TIER = "tier_change"
    UNDO_CANCELLATION = "undo_cancellation"

class UpdateSubscriptionPayload(BaseModel):
    behavior: UpdateSubscriptionBehavior
    new_price_tier_id: Optional[str] = None

class UpdatePaymentMethodPayload(BaseModel):
    success_callback_url: str
    cancel_callback_url: str

class PaymentProcessingRouter:

    CHECKOUT_SESSION_ENDPOINT = "/v1/checkout-session"
    SUBSCRIPTIONS_ENDPOINT = "/v1/subscriptions"
    PAYMENT_EVENT_ENDPOINT = "/v1/payment-event"
    UPDATE_PAYMENT_METHOD_SESSION_ENDPOINT = "/v1/payment-method-session"
    PAYMENT_HISTORY_ENDPOINT = "/v1/payment-history"
    PRODUCT_CATALOG = "/v1/product-catalog"
    ROUTER_TAG = "payments"
    ACTIVE_SUBSCRIPTION_STATES = ['active', 'trialing']

    def __init__(self, environment: str):
        self._environment = environment
        self._auth_manager = AuthManager()
        self._email_manager = EmailManager()
        self.router = APIRouter()
        self._register_routes()

    """
    Registers the set of routes that the class' router can access.
    """
    def _register_routes(self):
        @self.router.post(self.CHECKOUT_SESSION_ENDPOINT, tags=[self.ROUTER_TAG])
        async def create_checkout_session(request: Request,
                                          response: Response,
                                          payload: PaymentSessionPayload,
                                          background_tasks: BackgroundTasks,
                                          store_access_token: Annotated[str | None, Header()],
                                          store_refresh_token: Annotated[str | None, Header()],
                                          authorization: Annotated[Union[str, None], Cookie()] = None,
                                          session_id: Annotated[Union[str, None], Cookie()] = None):
            return await self._create_checkout_session_internal(authorization=authorization,
                                                                payload=payload,
                                                                background_tasks=background_tasks,
                                                                request=request,
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
                                         request: Request,
                                         background_tasks: BackgroundTasks,
                                         store_access_token: Annotated[str | None, Header()],
                                         store_refresh_token: Annotated[str | None, Header()],
                                         authorization: Annotated[Union[str, None], Cookie()] = None,
                                         session_id: Annotated[Union[str, None], Cookie()] = None):
            return await self._retrieve_subscriptions_internal(authorization=authorization,
                                                               background_tasks=background_tasks,
                                                               request=request,
                                                               response=response,
                                                               session_id=session_id,
                                                               store_access_token=store_access_token,
                                                               store_refresh_token=store_refresh_token)

        @self.router.put(self.SUBSCRIPTIONS_ENDPOINT, tags=[self.ROUTER_TAG])
        async def update_subscription(payload: UpdateSubscriptionPayload,
                                      response: Response,
                                      request: Request,
                                      background_tasks: BackgroundTasks,
                                      store_access_token: Annotated[str | None, Header()],
                                      store_refresh_token: Annotated[str | None, Header()],
                                      authorization: Annotated[Union[str, None], Cookie()] = None,
                                      session_id: Annotated[Union[str, None], Cookie()] = None):
            return await self._update_subscription_internal(authorization=authorization,
                                                            price_id=payload.new_price_tier_id,
                                                            behavior=payload.behavior,
                                                            background_tasks=background_tasks,
                                                            request=request,
                                                            response=response,
                                                            session_id=session_id,
                                                            store_access_token=store_access_token,
                                                            store_refresh_token=store_refresh_token)

        @self.router.delete(self.SUBSCRIPTIONS_ENDPOINT, tags=[self.ROUTER_TAG])
        async def delete_subscription(response: Response,
                                      request: Request,
                                      background_tasks: BackgroundTasks,
                                      store_access_token: Annotated[str | None, Header()],
                                      store_refresh_token: Annotated[str | None, Header()],
                                      authorization: Annotated[Union[str, None], Cookie()] = None,
                                      session_id: Annotated[Union[str, None], Cookie()] = None):
            return await self._delete_subscription_internal(authorization=authorization,
                                                            background_tasks=background_tasks,
                                                            request=request,
                                                            response=response,
                                                            session_id=session_id,
                                                            store_access_token=store_access_token,
                                                            store_refresh_token=store_refresh_token)

        @self.router.get(self.PRODUCT_CATALOG, tags=[self.ROUTER_TAG])
        async def retrieve_product_catalog(request: Request,
                                           response: Response,
                                           background_tasks: BackgroundTasks,
                                           store_access_token: Annotated[str | None, Header()],
                                           store_refresh_token: Annotated[str | None, Header()],
                                           authorization: Annotated[Union[str, None], Cookie()] = None,
                                           session_id: Annotated[Union[str, None], Cookie()] = None):
            return await self._retrieve_product_catalog_internal(authorization=authorization,
                                                                 background_tasks=background_tasks,
                                                                 request=request,
                                                                 response=response,
                                                                 session_id=session_id,
                                                                 store_access_token=store_access_token,
                                                                 store_refresh_token=store_refresh_token)

        @self.router.post(self.UPDATE_PAYMENT_METHOD_SESSION_ENDPOINT, tags=[self.ROUTER_TAG])
        async def create_update_payment_method_session(request: Request,
                                                       response: Response,
                                                       payload: UpdatePaymentMethodPayload,
                                                       background_tasks: BackgroundTasks,
                                                       store_access_token: Annotated[str | None, Header()],
                                                       store_refresh_token: Annotated[str | None, Header()],
                                                       authorization: Annotated[Union[str, None], Cookie()] = None,
                                                       session_id: Annotated[Union[str, None], Cookie()] = None):
            return await self._create_update_payment_method_session_internal(authorization=authorization,
                                                                             background_tasks=background_tasks,
                                                                             request=request,
                                                                             response=response,
                                                                             session_id=session_id,
                                                                             payload=payload,
                                                                             store_access_token=store_access_token,
                                                                             store_refresh_token=store_refresh_token)

        @self.router.get(self.PAYMENT_HISTORY_ENDPOINT, tags=[self.ROUTER_TAG])
        async def retrieve_payment_history(request: Request,
                                           response: Response,
                                           background_tasks: BackgroundTasks,
                                           store_access_token: Annotated[str | None, Header()],
                                           store_refresh_token: Annotated[str | None, Header()],
                                           authorization: Annotated[Union[str, None], Cookie()] = None,
                                           session_id: Annotated[Union[str, None], Cookie()] = None,
                                           batch_size: int = 0,
                                           pagination_last_item_id_retrieved: str = None):
            return await self._retrieve_payment_history_internal(background_tasks=background_tasks,
                                                                 authorization=authorization,
                                                                 store_access_token=store_access_token,
                                                                 store_refresh_token=store_refresh_token,
                                                                 session_id=session_id,
                                                                 request=request,
                                                                 response=response,
                                                                 limit=batch_size,
                                                                 starting_after=pagination_last_item_id_retrieved)

    """
    Creates a new checkout session.

    Arguments:
    background_tasks – object for scheduling concurrent tasks.
    authorization – the authorization cookie, if exists.
    store_access_token – the store access token.
    store_refresh_token – the store refresh token.
    session_id – the session_id cookie, if exists.
    request – the request object.
    response – the response model with which to create the final response.
    payload – the incoming request's payload.
    """
    async def _create_checkout_session_internal(self,
                                                background_tasks: BackgroundTasks,
                                                authorization: str,
                                                store_access_token: str,
                                                store_refresh_token: str,
                                                session_id: str,
                                                request: Request,
                                                response: Response,
                                                payload: PaymentSessionPayload):
        request.state.session_id = session_id
        if not self._auth_manager.access_token_is_valid(authorization):
            raise AUTH_TOKEN_EXPIRED_ERROR

        if store_access_token is None or store_refresh_token is None:
            raise STORE_TOKENS_ERROR

        try:
            supabase_client = dependency_container.inject_supabase_client_factory().supabase_user_client(access_token=store_access_token,
                                                                                                         refresh_token=store_refresh_token)
            therapist_id = supabase_client.get_current_user_id()
            request.state.therapist_id = therapist_id
            await self._auth_manager.refresh_session(user_id=therapist_id, response=response)
        except Exception as e:
            status_code = general_utilities.extract_status_code(e, fallback=status.HTTP_401_UNAUTHORIZED)
            dependency_container.inject_influx_client().log_error(endpoint_name=request.url.path,
                                                                  method=request.method,
                                                                  error_code=status_code,
                                                                  description=str(e),
                                                                  session_id=session_id)
            raise STORE_TOKENS_ERROR

        try:
            customer_data = supabase_client.select(fields="*",
                                                   filters={
                                                       'therapist_id': therapist_id,
                                                   },
                                                   table_name="subscription_status")
            is_new_customer = (0 == len(customer_data['data']))

            stripe_client = dependency_container.inject_stripe_client()
            payment_session_url = stripe_client.generate_checkout_session(price_id=payload.price_id,
                                                                          session_id=session_id,
                                                                          therapist_id=therapist_id,
                                                                          success_url=payload.success_callback_url,
                                                                          cancel_url=payload.cancel_callback_url,
                                                                          is_new_customer=is_new_customer)
            assert len(payment_session_url or '') > 0, "Received invalid checkout URL"
        except Exception as e:
            status_code = general_utilities.extract_status_code(e, fallback=status.HTTP_417_EXPECTATION_FAILED)
            message = str(e)
            dependency_container.inject_influx_client().log_error(endpoint_name=request.url.path,
                                                                  method=request.method,
                                                                  error_code=status_code,
                                                                  description=message,
                                                                  session_id=session_id)
            raise HTTPException(detail=message, status_code=status_code)

        return {"payment_session_url": payment_session_url}

    """
    Retrieves the set of subscriptions associated with the incoming customer ID.

    Arguments:
    background_tasks – object for scheduling concurrent tasks.
    authorization – the authorization cookie, if exists.
    store_access_token – the store access token.
    store_refresh_token – the store refresh token.
    session_id – the session_id cookie, if exists.
    request – the request object.
    response – the response model with which to create the final response.
    """
    async def _retrieve_subscriptions_internal(self,
                                               background_tasks: BackgroundTasks,
                                               authorization: str,
                                               store_access_token: str,
                                               store_refresh_token: str,
                                               session_id: str,
                                               request: Request,
                                               response: Response):
        request.state.session_id = session_id
        if not self._auth_manager.access_token_is_valid(authorization):
            raise AUTH_TOKEN_EXPIRED_ERROR

        if store_access_token is None or store_refresh_token is None:
            raise STORE_TOKENS_ERROR

        try:
            supabase_client = dependency_container.inject_supabase_client_factory().supabase_user_client(access_token=store_access_token,
                                                                                                         refresh_token=store_refresh_token)
            therapist_id = supabase_client.get_current_user_id()
            request.state.therapist_id = therapist_id
            await self._auth_manager.refresh_session(user_id=therapist_id,
                                                     response=response)
        except Exception as e:
            status_code = general_utilities.extract_status_code(e, fallback=status.HTTP_401_UNAUTHORIZED)
            dependency_container.inject_influx_client().log_error(endpoint_name=request.url.path,
                                                                  method=request.method,
                                                                  error_code=status_code,
                                                                  description=str(e),
                                                                  session_id=session_id)
            raise STORE_TOKENS_ERROR

        try:
            customer_data = supabase_client.select(fields="*",
                                                   filters={
                                                       'therapist_id': therapist_id,
                                                   },
                                                   table_name="subscription_status")
            if (0 == len(customer_data['data'])):
                return {"subscriptions": []}

            customer_id = customer_data['data'][0]['customer_id']

            stripe_client = dependency_container.inject_stripe_client()
            response = stripe_client.retrieve_customer_subscriptions(customer_id=customer_id)

            subscription_data = response['data']
            filtered_data = []
            for object in subscription_data:
                payment_method_id = object.get("default_payment_method")
                payment_method_data = stripe_client.retrieve_payment_method(payment_method_id)

                subscription_status = object['status']
                current_subscription = {
                    "subscription_id": object['id'],
                    "price_id": object['plan']['id'],
                    "product_id": object['items']['data'][0]['id'],
                    "status": subscription_status,
                    "payment_method_data": {
                        "id": payment_method_data['id'],
                        "type": payment_method_data['type'],
                        "data": payment_method_data['card'],
                    },
                }

                if subscription_status == 'trialing':
                    trial_end = datetime.fromtimestamp(object['trial_end'])
                    formatted_trial_end = trial_end.strftime(DATE_FORMAT)
                    current_subscription['trial_end'] = formatted_trial_end

                filtered_data.append(current_subscription)

        except Exception as e:
            status_code = general_utilities.extract_status_code(e, fallback=status.HTTP_417_EXPECTATION_FAILED)
            message = str(e)
            dependency_container.inject_influx_client().log_error(endpoint_name=request.url.path,
                                                                  method=request.method,
                                                                  error_code=status_code,
                                                                  description=message,
                                                                  session_id=session_id)
            raise HTTPException(detail=message, status_code=status_code)

        return {"subscriptions": filtered_data}

    """
    Deletes the subscriptions associated with the incoming ID.

    Arguments:
    background_tasks – object for scheduling concurrent tasks.
    authorization – the authorization cookie, if exists.
    store_access_token – the store access token.
    store_refresh_token – the store refresh token.
    session_id – the session_id cookie, if exists.
    request – the request object.
    response – the response model with which to create the final response.
    subscription_id – the subscription to be deleted.
    """
    async def _delete_subscription_internal(self,
                                            background_tasks: BackgroundTasks,
                                            authorization: str,
                                            store_access_token: str,
                                            store_refresh_token: str,
                                            session_id: str,
                                            request: Request,
                                            response: Response):
        request.state.session_id = session_id
        if not self._auth_manager.access_token_is_valid(authorization):
            raise AUTH_TOKEN_EXPIRED_ERROR

        if store_access_token is None or store_refresh_token is None:
            raise STORE_TOKENS_ERROR

        try:
            supabase_client = dependency_container.inject_supabase_client_factory().supabase_user_client(access_token=store_access_token,
                                                                                                         refresh_token=store_refresh_token)
            therapist_id = supabase_client.get_current_user_id()
            request.state.therapist_id = therapist_id
            await self._auth_manager.refresh_session(user_id=therapist_id,
                                                     response=response)
        except Exception as e:
            status_code = general_utilities.extract_status_code(e, fallback=status.HTTP_401_UNAUTHORIZED)
            dependency_container.inject_influx_client().log_error(endpoint_name=request.url.path,
                                                                  method=request.method,
                                                                  error_code=status_code,
                                                                  description=str(e),
                                                                  session_id=session_id)
            raise STORE_TOKENS_ERROR

        try:
            customer_data = supabase_client.select(fields="*",
                                                   filters={
                                                       'therapist_id': therapist_id,
                                                   },
                                                   table_name="subscription_status")
            assert (0 != len(customer_data['data'])), "There isn't a subscription associated with the incoming therapist."
            subscription_id = customer_data['data'][0]['subscription_id']

            stripe_client = dependency_container.inject_stripe_client()
            stripe_client.cancel_customer_subscription(subscription_id=subscription_id)
        except Exception as e:
            status_code = general_utilities.extract_status_code(e, fallback=status.HTTP_417_EXPECTATION_FAILED)
            message = str(e)
            dependency_container.inject_influx_client().log_error(endpoint_name=request.url.path,
                                                                  method=request.method,
                                                                  error_code=status_code,
                                                                  description=message,
                                                                  session_id=session_id)
            raise HTTPException(detail="Subscription not found", status_code=status_code)

        return {}

    """
    Updates the incoming subscription ID with the incoming product information.

    Arguments:
    background_tasks – object for scheduling concurrent tasks.
    authorization – the authorization cookie, if exists.
    store_access_token – the store access token.
    store_refresh_token – the store refresh token.
    session_id – the session_id cookie, if exists.
    request – the request object.
    response – the response model with which to create the final response.
    behavior – the update behavior to be invoked.
    price_id – the new price_id to be associated with the subscription.
    """
    async def _update_subscription_internal(self,
                                            background_tasks: BackgroundTasks,
                                            authorization: str,
                                            store_access_token: str,
                                            store_refresh_token: str,
                                            session_id: str,
                                            request: Request,
                                            response: Response,
                                            behavior: UpdateSubscriptionBehavior,
                                            price_id: str):
        request.state.session_id = session_id
        if not self._auth_manager.access_token_is_valid(authorization):
            raise AUTH_TOKEN_EXPIRED_ERROR

        if store_access_token is None or store_refresh_token is None:
            raise STORE_TOKENS_ERROR

        try:
            supabase_client = dependency_container.inject_supabase_client_factory().supabase_user_client(access_token=store_access_token,
                                                                                                         refresh_token=store_refresh_token)
            therapist_id = supabase_client.get_current_user_id()
            request.state.therapist_id = therapist_id
            await self._auth_manager.refresh_session(user_id=therapist_id,
                                                     response=response)
        except Exception as e:
            status_code = general_utilities.extract_status_code(e, fallback=status.HTTP_401_UNAUTHORIZED)
            dependency_container.inject_influx_client().log_error(endpoint_name=request.url.path,
                                                                  method=request.method,
                                                                  error_code=status_code,
                                                                  description=str(e),
                                                                  session_id=session_id)
            raise STORE_TOKENS_ERROR

        try:
            assert behavior != UpdateSubscriptionBehavior.UNSPECIFIED, "Unspecified update behavior"

            customer_data = supabase_client.select(fields="*",
                                                   filters={
                                                       'therapist_id': therapist_id,
                                                   },
                                                   table_name="subscription_status")
            assert (0 != len(customer_data['data'])), "There isn't a subscription associated with the incoming therapist."
            subscription_id = customer_data['data'][0]['subscription_id']

            stripe_client = dependency_container.inject_stripe_client()
            subscription_data = stripe_client.retrieve_subscription(subscription_id=subscription_id)

            if behavior == UpdateSubscriptionBehavior.CHANGE_TIER:
                assert len(price_id or '') > 0, "Missing the new tier price ID parameter."
                subscription_item_id = subscription_data["items"]["data"][0]["id"]
                stripe_client.update_customer_subscription_plan(subscription_id=subscription_id,
                                                                subscription_item_id=subscription_item_id,
                                                                price_id=price_id)
            elif behavior == UpdateSubscriptionBehavior.UNDO_CANCELLATION:
                # Check if subscription is already in a canceled state
                assert subscription_data['status'] != 'canceled', "The incoming subscription is already in a canceled state and cannot be resumed."
                stripe_client.resume_cancelled_subscription(subscription_id=subscription_id)
            else:
                raise Exception("Untracked update behavior")

        except Exception as e:
            status_code = general_utilities.extract_status_code(e, fallback=status.HTTP_417_EXPECTATION_FAILED)
            message = str(e)
            dependency_container.inject_influx_client().log_error(endpoint_name=request.url.path,
                                                                  method=request.method,
                                                                  error_code=status_code,
                                                                  description=message,
                                                                  session_id=session_id)
            raise HTTPException(detail=message, status_code=status_code)

        return {}

    async def _retrieve_product_catalog_internal(self,
                                                 background_tasks: BackgroundTasks,
                                                 authorization: str,
                                                 store_access_token: str,
                                                 store_refresh_token: str,
                                                 session_id: str,
                                                 request: Request,
                                                 response: Response):
        request.state.session_id = session_id
        if not self._auth_manager.access_token_is_valid(authorization):
            raise AUTH_TOKEN_EXPIRED_ERROR

        if store_access_token is None or store_refresh_token is None:
            raise STORE_TOKENS_ERROR

        try:
            supabase_client = dependency_container.inject_supabase_client_factory().supabase_user_client(access_token=store_access_token,
                                                                                                         refresh_token=store_refresh_token)
            therapist_id = supabase_client.get_current_user_id()
            request.state.therapist_id = therapist_id
            await self._auth_manager.refresh_session(user_id=therapist_id,
                                                     response=response)
        except Exception as e:
            status_code = general_utilities.extract_status_code(e, fallback=status.HTTP_401_UNAUTHORIZED)
            dependency_container.inject_influx_client().log_error(endpoint_name=request.url.path,
                                                                  method=request.method,
                                                                  error_code=status_code,
                                                                  description=str(e),
                                                                  session_id=session_id)
            raise STORE_TOKENS_ERROR

        try:
            stripe_client = dependency_container.inject_stripe_client()
            response = stripe_client.retrieve_product_catalog()
        except Exception as e:
            status_code = general_utilities.extract_status_code(e, fallback=status.HTTP_417_EXPECTATION_FAILED)
            message = str(e)
            dependency_container.inject_influx_client().log_error(endpoint_name=request.url.path,
                                                                  method=request.method,
                                                                  error_code=status_code,
                                                                  description=message,
                                                                  session_id=session_id)
            raise HTTPException(detail="Subscription not found", status_code=status_code)

        return {"catalog": response}

    """
    Generates a URL for updating a subscription's payment method with the incoming data.

    Arguments:
    background_tasks – object for scheduling concurrent tasks.
    authorization – the authorization cookie, if exists.
    store_access_token – the store access token.
    store_refresh_token – the store refresh token.
    session_id – the session_id cookie, if exists.
    request – the request object.
    response – the response model with which to create the final response.
    payload – the JSON payload containing the update data.
    """
    async def _create_update_payment_method_session_internal(self,
                                                             background_tasks: BackgroundTasks,
                                                             authorization: str,
                                                             store_access_token: str,
                                                             store_refresh_token: str,
                                                             session_id: str,
                                                             request: Request,
                                                             response: Response,
                                                             payload: UpdatePaymentMethodPayload):
        request.state.session_id = session_id
        if not self._auth_manager.access_token_is_valid(authorization):
            raise AUTH_TOKEN_EXPIRED_ERROR

        if store_access_token is None or store_refresh_token is None:
            raise STORE_TOKENS_ERROR

        try:
            supabase_client = dependency_container.inject_supabase_client_factory().supabase_user_client(access_token=store_access_token,
                                                                                                         refresh_token=store_refresh_token)
            therapist_id = supabase_client.get_current_user_id()
            request.state.therapist_id = therapist_id
            await self._auth_manager.refresh_session(user_id=therapist_id,
                                                     response=response)
        except Exception as e:
            status_code = general_utilities.extract_status_code(e, fallback=status.HTTP_401_UNAUTHORIZED)
            dependency_container.inject_influx_client().log_error(endpoint_name=request.url.path,
                                                                  method=request.method,
                                                                  error_code=status_code,
                                                                  description=str(e),
                                                                  session_id=session_id)
            raise STORE_TOKENS_ERROR

        try:
            customer_data = supabase_client.select(fields="*",
                                                   filters={
                                                       'therapist_id': therapist_id,
                                                   },
                                                   table_name="subscription_status")
            assert (0 != len(customer_data['data'])), "There isn't a subscription associated with the incoming therapist."
            customer_id = customer_data['data'][0]['customer_id']

            stripe_client = dependency_container.inject_stripe_client()
            update_payment_method_url = stripe_client.generate_payment_method_update_session(customer_id=customer_id,
                                                                                             success_url=payload.success_callback_url,
                                                                                             cancel_url=payload.cancel_callback_url)
        except Exception as e:
            status_code = general_utilities.extract_status_code(e, fallback=status.HTTP_417_EXPECTATION_FAILED)
            message = str(e)
            dependency_container.inject_influx_client().log_error(endpoint_name=request.url.path,
                                                                  method=request.method,
                                                                  error_code=status_code,
                                                                  description=message,
                                                                  session_id=session_id)
            raise HTTPException(detail=message, status_code=status_code)

        return { "update_payment_method_url": update_payment_method_url }

    """
    Retrieves the payment history for the current user (customer).

    Arguments:
    background_tasks – object for scheduling concurrent tasks.
    authorization – the authorization cookie, if exists.
    store_access_token – the store access token.
    store_refresh_token – the store refresh token.
    session_id – the session_id cookie, if exists.
    request – the request object.
    response – the response model with which to create the final response.
    limit – the limit for the batch size to be returned.
    starting_after – the id of the last payment that was retrieved (for pagination purposes).
    """
    async def _retrieve_payment_history_internal(self,
                                                 background_tasks: BackgroundTasks,
                                                 authorization: str,
                                                 store_access_token: str,
                                                 store_refresh_token: str,
                                                 session_id: str,
                                                 request: Request,
                                                 response: Response,
                                                 limit: int,
                                                 starting_after: str | None):
        request.state.session_id = session_id
        if not self._auth_manager.access_token_is_valid(authorization):
            raise AUTH_TOKEN_EXPIRED_ERROR

        if store_access_token is None or store_refresh_token is None:
            raise STORE_TOKENS_ERROR

        try:
            supabase_client = dependency_container.inject_supabase_client_factory().supabase_user_client(access_token=store_access_token,
                                                                                                         refresh_token=store_refresh_token)
            therapist_id = supabase_client.get_current_user_id()
            request.state.therapist_id = therapist_id
            await self._auth_manager.refresh_session(user_id=therapist_id,
                                                     response=response)
        except Exception as e:
            status_code = general_utilities.extract_status_code(e, fallback=status.HTTP_401_UNAUTHORIZED)
            dependency_container.inject_influx_client().log_error(endpoint_name=request.url.path,
                                                                  method=request.method,
                                                                  error_code=status_code,
                                                                  description=str(e),
                                                                  session_id=session_id)
            raise STORE_TOKENS_ERROR

        try:
            customer_data = supabase_client.select(fields="*",
                                                   filters={
                                                       'therapist_id': therapist_id,
                                                   },
                                                   table_name="subscription_status")
            if (0 == len(customer_data['data'])):
                return {"payments": []}

            customer_id = customer_data['data'][0]['customer_id']

            stripe_client = dependency_container.inject_stripe_client()
            payment_intent_history = stripe_client.retrieve_payment_intent_history(customer_id=customer_id,
                                                                                   limit=limit,
                                                                                   starting_after=starting_after)

            successful_payments = []
            for intent in payment_intent_history["data"]:
                if intent["status"] != "succeeded":
                    continue

                # Format amount
                formatted_price_amount = general_utilities.format_currency_amount(amount=float(intent["amount"]),
                                                                                  currency_code=intent["currency"])

                # Format date
                date_from_unix_timestamp = datetime.fromtimestamp(intent["created"])
                formatted_date = date_from_unix_timestamp.strftime(DATE_FORMAT)
                successful_payments.append({
                    "id": intent["id"],
                    "amount": formatted_price_amount,
                    "status": intent["status"],
                    "description": intent["description"],
                    "date": formatted_date,
                    "currency": intent["currency"],
                    "payment_method": intent.get("payment_method_types", []),
                    "metadata": intent.get("metadata", {})
                })

        except Exception as e:
            status_code = general_utilities.extract_status_code(e, fallback=status.HTTP_417_EXPECTATION_FAILED)
            message = str(e)
            dependency_container.inject_influx_client().log_error(endpoint_name=request.url.path,
                                                                  method=request.method,
                                                                  error_code=status_code,
                                                                  description=message,
                                                                  session_id=session_id)
            raise HTTPException(detail=message, status_code=status_code)

        return {"payments": successful_payments}

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
        environment = os.environ.get("ENVIRONMENT")

        logging.info(f"Received webhook for environment: {environment}")

        try:
            if environment == DEV_ENVIRONMENT:
                webhook_secret = os.getenv("STRIPE_WEBHOOK_SECRET_DEBUG")
            elif environment == STAGING_ENVIRONMENT:
                webhook_secret = os.getenv("STRIPE_WEBHOOK_SECRET_STAGING")
            elif environment == PROD_ENVIRONMENT:
                webhook_secret = os.getenv("STRIPE_WEBHOOK_SECRET_PROD")
            else:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid environment")

            payload = await request.body()
            sig_header = request.headers.get("stripe-signature")
            event = stripe_client.construct_webhook_event(payload=payload,
                                                          sig_header=sig_header,
                                                          webhook_secret=webhook_secret)

            logging.info("Successfully constructed Stripe event")

            # In deployed environments, block requests from localhost
            if environment in [STAGING_ENVIRONMENT, PROD_ENVIRONMENT] and request.client.host in ["localhost", "127.0.0.1"]:
                logging.info(f"Blocking localhost request for {environment}")
                raise HTTPException(
                    status_code=403, detail="Webhooks from localhost are not allowed in staging."
                )
        except ValueError:
            # Invalid payload
            logging.error(f"ValueError encountered: {str(e)}")
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid payload")
        except Exception as e:
            # Check for invalid signature
            logging.error(f"Exception encountered trying to construct the webhook event: {str(e)}")
            if stripe_client.is_signature_verification_error(e=e):
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid signature")
            else:
                raise HTTPException(status_code=status.HTTP_417_EXPECTATION_FAILED, detail=str(e))

        try:
            await self._handle_stripe_event(event=event,
                                            stripe_client=stripe_client,
                                            background_tasks=background_tasks)
        except Exception as e:
            logging.error(f"Exception encountered handling the Stripe event: {str(e)}")
            raise HTTPException(e)

        return {}

    # Private

    """
    Internal funnel for specific handlings of Stripe events.

    Arguments:
    event – the Stripe event.
    stripe_client – the Stripe client.
    background_tasks – object for scheduling concurrent tasks.
    """
    async def _handle_stripe_event(self,
                                   event,
                                   stripe_client: StripeBaseClass,
                                   background_tasks: BackgroundTasks):
        event_type: str = event["type"]

        if event_type == 'checkout.session.completed':
            checkout_session = event['data']['object']
            subscription_id = checkout_session.get('subscription')
            customer_id = checkout_session.get('customer')
            metadata = checkout_session.get('metadata', {})
            therapist_id = None if 'therapist_id' not in metadata else metadata['therapist_id']

            if subscription_id:
                # Update the subscription with metadata
                stripe_client.attach_subscription_metadata(subscription_id=subscription_id,
                                                           metadata=metadata)

                # Attach product metadata to the underlying payment intent
                try:
                    subscription = stripe_client.retrieve_subscription(subscription_id)
                    latest_invoice = stripe_client.retrieve_invoice(subscription.get("latest_invoice"))
                    price_id = subscription["items"]["data"][0]["price"]["id"]

                    # Retrieve product metadata associated with the price id.
                    price = stripe_client.retrieve_price(price_id)
                    product_id = price.get("product")
                    product = stripe_client.retrieve_product(product_id)
                    stripe_client.attach_payment_intent_metadata(payment_intent_id=latest_invoice.get("payment_intent"),
                                                                 metadata=product.get("metadata", {}))
                except Exception:
                    pass

        elif event_type == 'invoice.created':
            invoice = event['data']['object']
            subscription_id = invoice.get('subscription')
            invoice_metadata = invoice.get("metadata", {})

            # If the invoice has no metadata, and a subscription exists, let's retrieve
            # the subscription object to attach its metadata to the invoice.
            if len(invoice_metadata) == 0 and len(subscription_id or '') > 0:
                subscription = stripe_client.retrieve_subscription(subscription_id)
                invoice_metadata = subscription.get('metadata', {})
                stripe_client.attach_invoice_metadata(invoice_id=invoice['id'],
                                                      metadata=invoice_metadata)

        elif event_type == 'invoice.updated':
            invoice = event['data']['object']
            subscription_id = invoice.get('subscription')
            invoice_metadata = invoice.get("metadata", {})

            # If the invoice has no metadata, and a subscription exists, let's retrieve
            # the subscription object to attach its metadata to the invoice.
            if len(invoice_metadata) == 0 and len(subscription_id or '') > 0:
                subscription = stripe_client.retrieve_subscription(subscription_id)
                invoice_metadata = subscription.get('metadata', {})
                stripe_client.attach_invoice_metadata(invoice_id=invoice['id'],
                                                      metadata=invoice_metadata)

        elif event_type == 'invoice.payment_succeeded':
            # TODO: Send ChartWise receipt to user.
            invoice = event['data']['object']

            try:
                # Attach metadata containing the product ID to the payment intent
                payment_intent_id = invoice.get("payment_intent")
                assert payment_intent_id, "No ID found for associated payment intent."

                subscription_id = invoice.get("subscription")
                assert subscription_id, "No ID found for associated subscription."

                subscription = stripe_client.retrieve_subscription(subscription_id)
                price_id = subscription["items"]["data"][0]["price"]["id"]
                price = stripe_client.retrieve_price(price_id)
                product_id = price.get("product", {})
                product = stripe_client.retrieve_product(product_id)
                product_metadata = product.get("metadata", {})
                stripe_client.attach_payment_intent_metadata(payment_intent_id=payment_intent_id,
                                                             metadata=product_metadata)
            except:
                pass

        elif event_type == 'invoice.upcoming':
            # TODO: Notify Customers of Upcoming Charge
            invoice = event['data']['object']

        elif event_type == 'invoice.payment_failed':
            # The payment failed or the customer does not have a valid payment method.
            # The subscription becomes past_due. Notify your customer and send them to the
            # customer portal to update their payment information.
            invoice = event['data']['object']

        elif event_type == 'customer.subscription.created':
            await self._handle_subscription_upsert(subscription_upsert_event=event)
        elif event_type == 'customer.subscription.updated':
            # TODO: Handle Plan Upgrades/Downgrades emails when users change their subscription.
            await self._handle_subscription_upsert(subscription_upsert_event=event)
        elif event_type == 'customer.subscription.paused':
            # TODO: Send an automated email confirming the pause.
            pass

        elif event_type == 'customer.subscription.deleted':
            # TODO: Send an automated email confirming the cancellation, offering a reactivation discount,
            # or sharing helpful info about resuming their subscription in the future.
            pass

        elif event_type == 'setup_intent.succeeded':
            setup_intent = event["data"]["object"]
            payment_method_id = setup_intent["payment_method"]
            therapist_id = None
            customer_id = setup_intent["customer"]

            # If the customer ID hasn't been set, we can't proceed.
            # Let's wait for subsequent invocation of this path.
            if customer_id is None:
                return

            try:
                # Fetch corresponding therapist ID
                supabase_client = dependency_container.inject_supabase_client_factory().supabase_admin_client()
                customer_data = supabase_client.select(fields="*",
                                                       filters={
                                                           'customer_id': customer_id,
                                                       },
                                                       table_name="subscription_status")
                assert (0 != len(customer_data['data'])), "No therapist data found for incoming customer ID."
                therapist_id = customer_data['data'][0]['therapist_id']
            except Exception:
                pass

            # Attach the payment method to the customer
            stripe_client.attach_customer_payment_method(customer_id=customer_id,
                                                         payment_method_id=payment_method_id)

            # Update the default payment method for the subscription
            subscriptions = stripe_client.retrieve_customer_subscriptions(customer_id)
            for subscription in subscriptions:
                try:
                    stripe_client.update_subscription_payment_method(subscription_id=subscription.id,
                                                                     payment_method_id=payment_method_id)
                except Exception as e:
                    if therapist_id is not None:
                        # Failed to update a subscription's payment method. Trigger internal alert, and fail silently.
                        internal_alert = PaymentsActivityAlert(description=("(setup_intent.succeeded) This failure usually is related to not "
                                                                            "being able to update a subscription's payment method. "
                                                                            "Please take a look to get a better understanding of the customer's journey."),
                                                                exception=e,
                                                                environment=self._environment,
                                                                therapist_id=therapist_id,
                                                                subscription_id=subscription.get('id', None),
                                                                payment_method_id=payment_method_id,
                                                                customer_id=customer_id)
                        await self._email_manager.send_internal_alert(alert=internal_alert)

        else:
            print(f"[Stripe Event] Unhandled event type: '{event_type}'")

    # Private

    async def _handle_subscription_upsert(self,
                                          subscription_upsert_event: dict):
        subscription = subscription_upsert_event['data']['object']
        subscription_metadata = subscription.get('metadata', {})

        try:
            therapist_id = subscription_metadata.get('therapist_id', None)
            session_id = subscription_metadata.get('session_id', None)

            assert len(therapist_id or '') > 0, "Did not find a therapist ID in the subscription metadata."
        except Exception:
            return

        stripe_client = dependency_container.inject_stripe_client()
        supabase_client = dependency_container.inject_supabase_client_factory().supabase_admin_client()

        try:
            therapist_subscription_query = supabase_client.select(fields="*",
                                                                  filters={ 'therapist_id': therapist_id },
                                                                  table_name="subscription_status")
            is_new_customer = (0 == len(therapist_subscription_query['data']))

            # Get customer data
            billing_interval = subscription['items']['data'][0]['plan']['interval']
            current_period_end = datetime.fromtimestamp(subscription["current_period_end"])
            current_billing_period_end_date = current_period_end.strftime(DATE_FORMAT)
            customer_id = subscription.get('customer')
            subscription_id = subscription.get('id')
            product_id = subscription['items']['data'][0]['price']['product']
            product_data = stripe_client.retrieve_product(product_id)
            stripe_product_name = product_data['metadata']['product_name']
            tier_name = general_utilities.map_stripe_product_name_to_chartwise_tier(stripe_product_name)
            is_trialing = subscription['status'] == 'trialing'
            now_timestamp = datetime.now().strftime(datetime_handler.DATE_TIME_FORMAT)

            payload = {
                "last_updated": now_timestamp,
                "customer_id": customer_id,
                "therapist_id": therapist_id,
                "current_billing_period_end_date": current_billing_period_end_date,
                "recurrence": billing_interval,
                "subscription_id": subscription_id,
                "current_tier": tier_name
            }

            if is_trialing:
                trial_end_date = datetime.fromtimestamp(subscription['trial_end'])
                payload["free_trial_end_date"] = trial_end_date.strftime(DATE_FORMAT)

            if (subscription.get('status') in self.ACTIVE_SUBSCRIPTION_STATES) and not subscription.get('cancel_at_period_end'):
                # Free trial is ongoing, or subscription is active.
                payload['is_active'] = True
                payload['free_trial_active'] = is_trialing
            else:
                # Subscription is not active. Restrict functionality
                payload['is_active'] = False
                payload['free_trial_active'] = False

            supabase_client.upsert(payload=payload,
                                   table_name="subscription_status",
                                   on_conflict="therapist_id")

            if is_new_customer:
                therapist_query_data = supabase_client.select(fields="*",
                                                              filters={ 'id': therapist_id },
                                                              table_name="therapists")
                assert 0 != len(therapist_query_data), "Did not find therapist in internal records."

                therapist_data = therapist_query_data['data'][0]
                alert_description = (f"Customer has just entered an active subscription state for the first time. "
                                        "Consider reaching out directly for a more personal welcome note.")
                therapist_name = "".join([therapist_data['first_name'],
                                            " ",
                                            therapist_data['last_name']])
                alert = CustomerRelationsAlert(description=alert_description,
                                               session_id=session_id,
                                               environment=self._environment,
                                               therapist_id=therapist_id,
                                               therapist_name=therapist_name,
                                               therapist_email=therapist_data['email'])
                await self._email_manager.send_customer_relations_alert(alert)
        except Exception as e:
            internal_alert = PaymentsActivityAlert(description="(customer.subscription.updated) Failure caught in subscription update.",
                                                   session_id=session_id,
                                                   environment=self._environment,
                                                   therapist_id=therapist_id,
                                                   exception=e,
                                                   subscription_id=subscription_id,
                                                   customer_id=customer_id)
            await self._email_manager.send_internal_alert(alert=internal_alert)
