import logging, os

from enum import Enum
from datetime import datetime
from fastapi import (APIRouter,
                     Cookie,
                     Depends,
                     HTTPException,
                     Request,
                     Response,
                     status)
from pydantic import BaseModel
from typing import Annotated, Optional, Union

from ..dependencies.dependency_container import (
    dependency_container,
    AwsDbBaseClass,
    AwsSecretManagerBaseClass,
    StripeBaseClass
)
from ..internal.alerting.internal_alert import CustomerRelationsAlert, PaymentsActivityAlert
from ..internal.schemas import (
    DEV_ENVIRONMENT,
    PROD_ENVIRONMENT,
    STAGING_ENVIRONMENT,
    SUBSCRIPTION_STATUS_TABLE_NAME,
    USER_ID_KEY,
)
from ..internal.security.security_schema import SESSION_TOKEN_MISSING_OR_EXPIRED_ERROR
from ..internal.utilities import general_utilities, subscription_utilities
from ..internal.utilities.datetime_handler import DATE_FORMAT
from ..internal.utilities.general_utilities import retrieve_ip_address
from ..internal.utilities.route_verification import get_user_info
from ..managers.auth_manager import AuthManager
from ..managers.subscription_manager import SubscriptionManager

class SubscriptionTier(Enum):
    UNSPECIFIED = "unspecified"
    MONTHLY_BASIC = "basic_plan_monthly"
    MONTHLY_PREMIUM = "premium_plan_monthly"
    YEARLY_BASIC = "basic_plan_yearly"
    YEARLY_PREMIUM = "premium_plan_yearly"

class PaymentSessionPayload(BaseModel):
    subscription_tier: SubscriptionTier
    success_callback_url: str
    cancel_callback_url: str

class UpdateSubscriptionBehavior(Enum):
    UNSPECIFIED = "unspecified"
    CHANGE_TIER = "tier_change"
    UNDO_CANCELLATION = "undo_cancellation"

class UpdateSubscriptionPayload(BaseModel):
    behavior: UpdateSubscriptionBehavior
    new_subscription_tier: Optional[SubscriptionTier] = None

class UpdatePaymentMethodPayload(BaseModel):
    success_callback_url: str
    cancel_callback_url: str

class PaymentProcessingRouter:

    CHECKOUT_SESSION_ENDPOINT = "/v1/checkout-session"
    SUBSCRIPTIONS_ENDPOINT = "/v1/subscriptions"
    PAYMENT_EVENT_ENDPOINT = "/v1/payment-event"
    UPDATE_PAYMENT_METHOD_SESSION_ENDPOINT = "/v1/payment-method-session"
    PAYMENT_HISTORY_ENDPOINT = "/v1/payment-history"
    PRODUCT_CATALOG_ENDPOINT = "/v1/product-catalog"
    SUBSCRIPTION_STATUS_ENDPOINT = "/v1/subscription_status"
    ROUTER_TAG = "payments"
    TRIALING = "trialing"
    ACTIVE_SUBSCRIPTION_STATES = ['active', TRIALING]

    def __init__(
        self,
        environment: str
    ):
        self._environment = environment
        self._auth_manager = AuthManager()
        self._subscription_manager = SubscriptionManager()
        self.router = APIRouter()
        self._register_routes()

    def _register_routes(self):
        """
        Registers the set of routes that the class' router can access.
        """
        @self.router.post(type(self).CHECKOUT_SESSION_ENDPOINT, tags=[type(self).ROUTER_TAG])
        async def create_checkout_session(
            request: Request,
            response: Response,
            payload: PaymentSessionPayload,
            _: dict = Depends(get_user_info),
            session_token: Annotated[Union[str, None], Cookie()] = None,
            session_id: Annotated[Union[str, None], Cookie()] = None
        ):
            return await self._create_checkout_session_internal(
                session_token=session_token,
                payload=payload,
                request=request,
                response=response,
                session_id=session_id
            )

        @self.router.post(type(self).PAYMENT_EVENT_ENDPOINT, tags=[type(self).ROUTER_TAG])
        async def capture_payment_event(
            request: Request,
        ):
            return await self._capture_payment_event_internal(
                request=request
            )

        @self.router.get(type(self).SUBSCRIPTIONS_ENDPOINT, tags=[type(self).ROUTER_TAG])
        async def retrieve_subscriptions(
            response: Response,
            request: Request,
            _: dict = Depends(get_user_info),
            session_token: Annotated[Union[str, None], Cookie()] = None,
            session_id: Annotated[Union[str, None], Cookie()] = None
        ):
            return await self._retrieve_subscriptions_internal(
                session_token=session_token,
                request=request,
                response=response,
                session_id=session_id
            )

        @self.router.put(type(self).SUBSCRIPTIONS_ENDPOINT, tags=[type(self).ROUTER_TAG])
        async def update_subscription(
            payload: UpdateSubscriptionPayload,
            response: Response,
            request: Request,
            _: dict = Depends(get_user_info),
            session_token: Annotated[Union[str, None], Cookie()] = None,
            session_id: Annotated[Union[str, None], Cookie()] = None
        ):
            return await self._update_subscription_internal(
                session_token=session_token,
                subscription_tier=payload.new_subscription_tier,
                behavior=payload.behavior,
                request=request,
                response=response,
                session_id=session_id
            )

        @self.router.delete(type(self).SUBSCRIPTIONS_ENDPOINT, tags=[type(self).ROUTER_TAG])
        async def delete_subscription(
            response: Response,
            request: Request,
            _: dict = Depends(get_user_info),
            session_token: Annotated[Union[str, None], Cookie()] = None,
            session_id: Annotated[Union[str, None], Cookie()] = None
        ):
            return await self._delete_subscription_internal(
                session_token=session_token,
                request=request,
                response=response,
                session_id=session_id
            )

        @self.router.get(type(self).PRODUCT_CATALOG_ENDPOINT, tags=[type(self).ROUTER_TAG])
        async def retrieve_product_catalog(
            request: Request,
            response: Response,
            _: dict = Depends(get_user_info),
            session_token: Annotated[Union[str, None], Cookie()] = None,
            session_id: Annotated[Union[str, None], Cookie()] = None
        ):
            return await self._retrieve_product_catalog_internal(
                session_token=session_token,
                request=request,
                response=response,
                session_id=session_id
            )

        @self.router.post(type(self).UPDATE_PAYMENT_METHOD_SESSION_ENDPOINT, tags=[type(self).ROUTER_TAG])
        async def create_update_payment_method_session(
            request: Request,
            response: Response,
            payload: UpdatePaymentMethodPayload,
            _: dict = Depends(get_user_info),
            session_token: Annotated[Union[str, None], Cookie()] = None,
            session_id: Annotated[Union[str, None], Cookie()] = None
        ):
            return await self._create_update_payment_method_session_internal(
                session_token=session_token,
                request=request,
                response=response,
                session_id=session_id,
                payload=payload
            )

        @self.router.get(type(self).PAYMENT_HISTORY_ENDPOINT, tags=[type(self).ROUTER_TAG])
        async def retrieve_payment_history(
            request: Request,
            response: Response,
            _: dict = Depends(get_user_info),
            session_token: Annotated[Union[str, None], Cookie()] = None,
            session_id: Annotated[Union[str, None], Cookie()] = None,
            batch_size: int = 0,
            pagination_last_item_id_retrieved: str = None
        ):
            return await self._retrieve_payment_history_internal(
                session_token=session_token,
                session_id=session_id,
                request=request,
                response=response,
                limit=batch_size,
                starting_after=pagination_last_item_id_retrieved
            )

    async def _create_checkout_session_internal(
        self,
        session_token: str,
        session_id: str,
        request: Request,
        response: Response,
        payload: PaymentSessionPayload
    ):
        """
        Creates a new checkout session.

        Arguments:
        session_token – the session_token cookie, if exists.
        session_id – the session_id cookie, if exists.
        request – the request object.
        response – the response model with which to create the final response.
        payload – the incoming request's payload.
        """
        request.state.session_id = session_id
        if not self._auth_manager.session_token_is_valid(session_token):
            raise SESSION_TOKEN_MISSING_OR_EXPIRED_ERROR

        try:
            user_id = self._auth_manager.extract_data_from_token(session_token)[USER_ID_KEY]
            request.state.therapist_id = user_id
            await self._auth_manager.refresh_session(
                user_id=user_id,
                session_id=session_id,
                response=response
            )
        except Exception as e:
            status_code = general_utilities.extract_status_code(
                e,
                fallback=status.HTTP_401_UNAUTHORIZED
            )
            dependency_container.inject_influx_client().log_error(
                endpoint_name=request.url.path,
                method=request.method,
                error_code=status_code,
                description=str(e),
                session_id=session_id
            )
            raise RuntimeError(e) from e

        try:
            assert payload.subscription_tier != SubscriptionTier.UNSPECIFIED, "Unspecified subscription tier"
        except Exception as e:
            status_code = general_utilities.extract_status_code(
                e,
                fallback=status.HTTP_400_BAD_REQUEST
            )
            dependency_container.inject_influx_client().log_error(
                endpoint_name=request.url.path,
                method=request.method,
                error_code=status_code,
                description=str(e),
                session_id=session_id
            )
            raise RuntimeError(e) from e

        try:
            aws_db_client: AwsDbBaseClass = dependency_container.inject_aws_db_client()
            customer_data = await aws_db_client.select(
                user_id=user_id,
                request=request,
                fields=["*"],
                filters={
                    'therapist_id': user_id,
                },
                table_name=SUBSCRIPTION_STATUS_TABLE_NAME
            )
            is_new_customer = (0 == len(customer_data))

            user_ip_address = retrieve_ip_address(request)
            country_iso = await general_utilities.get_country_iso_code_from_ip(user_ip_address)

            stripe_client = dependency_container.inject_stripe_client()
            product_catalog = stripe_client.retrieve_product_catalog(country_iso=country_iso)
            price_id = None
            for product in product_catalog:
                if product['metadata']['product_name'] == payload.subscription_tier.value:
                    price_id = product['price_data']['id']
                    break

            assert len(price_id or '') > 0, "Could not find a product for the incoming request."
            payment_session_url = stripe_client.generate_checkout_session(
                price_id=price_id,
                session_id=session_id,
                therapist_id=user_id,
                success_url=payload.success_callback_url,
                cancel_url=payload.cancel_callback_url,
                is_new_customer=is_new_customer
            )
            assert len(payment_session_url or '') > 0, "Received invalid checkout URL"
        except Exception as e:
            status_code = general_utilities.extract_status_code(
                e,
                fallback=status.HTTP_417_EXPECTATION_FAILED
            )
            message = str(e)
            dependency_container.inject_influx_client().log_error(
                endpoint_name=request.url.path,
                method=request.method,
                error_code=status_code,
                description=message,
                session_id=session_id
            )
            raise HTTPException(
                detail=message,
                status_code=status_code
            )

        return {"payment_session_url": payment_session_url}

    async def _retrieve_subscriptions_internal(
        self,
        session_token: str,
        session_id: str,
        request: Request,
        response: Response
    ):
        """
        Retrieves the set of subscriptions associated with the incoming customer ID.

        Arguments:
        session_token – the session_token cookie, if exists.
        session_id – the session_id cookie, if exists.
        request – the request object.
        response – the response model with which to create the final response.
        """
        request.state.session_id = session_id
        if not self._auth_manager.session_token_is_valid(session_token):
            raise SESSION_TOKEN_MISSING_OR_EXPIRED_ERROR

        try:
            user_id = self._auth_manager.extract_data_from_token(session_token)[USER_ID_KEY]
            request.state.therapist_id = user_id
            await self._auth_manager.refresh_session(
                user_id=user_id,
                session_id=session_id,
                response=response
            )
        except Exception as e:
            status_code = general_utilities.extract_status_code(
                e,
                fallback=status.HTTP_401_UNAUTHORIZED
            )
            dependency_container.inject_influx_client().log_error(
                endpoint_name=request.url.path,
                method=request.method,
                error_code=status_code,
                description=str(e),
                session_id=session_id
            )
            raise RuntimeError(e) from e

        try:
            aws_db_client: AwsDbBaseClass = dependency_container.inject_aws_db_client()
            customer_data = await aws_db_client.select(
                user_id=user_id,
                request=request,
                fields=["*"],
                filters={
                    'therapist_id': user_id,
                },
                table_name=SUBSCRIPTION_STATUS_TABLE_NAME
            )
            if (0 == len(customer_data)):
                return {"subscriptions": []}

            customer_id = customer_data[0]['customer_id']

            stripe_client = dependency_container.inject_stripe_client()
            response = stripe_client.retrieve_customer_subscriptions(customer_id=customer_id)

            subscription_data = response['data']
            filtered_data = []

            for subscription in subscription_data:
                subscription_status = subscription['status']
                payment_method_id = subscription.get("default_payment_method", None)
                payment_method_data = stripe_client.retrieve_payment_method(payment_method_id)

                subscription_data = await self._subscription_manager.subscription_data(
                    user_id=user_id,
                    request=request,
                )
                current_period_end = datetime.fromtimestamp(subscription["current_period_end"])
                current_billing_period_end_date = current_period_end.date().strftime(DATE_FORMAT)
                current_subscription = {
                    "subscription_id": subscription['id'],
                    "price_id": subscription['plan']['id'],
                    "product_id": subscription['items']['data'][0]['id'],
                    "status": subscription_status,
                    "recurrence": subscription['items']['data'][0]['plan']['interval'],
                    "current_billing_period_end_date": current_billing_period_end_date,
                    "payment_method_data": {
                        "id": None if 'id' not in payment_method_data else payment_method_data['id'],
                        "type": None if 'type' not in payment_method_data else payment_method_data['type'],
                        "data": None if 'data' not in payment_method_data else payment_method_data['card'],
                    },
                }
                current_subscription.update(subscription_data)

                if subscription_status == self.TRIALING:
                    trial_end = datetime.fromtimestamp(subscription['trial_end'])
                    formatted_trial_end = trial_end.strftime(DATE_FORMAT)
                    current_subscription['trial_end'] = formatted_trial_end

                filtered_data.append(current_subscription)

        except Exception as e:
            status_code = general_utilities.extract_status_code(
                e,
                fallback=status.HTTP_417_EXPECTATION_FAILED
            )
            message = str(e)
            dependency_container.inject_influx_client().log_error(
                endpoint_name=request.url.path,
                method=request.method,
                error_code=status_code,
                description=message,
                session_id=session_id
            )
            raise HTTPException(
                detail=message,
                status_code=status_code
            )

        return {"subscriptions": filtered_data}

    async def _delete_subscription_internal(
        self,
        session_token: str,
        session_id: str,
        request: Request,
        response: Response
    ):
        """
        Deletes the subscriptions associated with the incoming ID.

        Arguments:
        session_token – the session_token cookie, if exists.
        session_id – the session_id cookie, if exists.
        request – the request object.
        response – the response model with which to create the final response.
        """
        request.state.session_id = session_id
        if not self._auth_manager.session_token_is_valid(session_token):
            raise SESSION_TOKEN_MISSING_OR_EXPIRED_ERROR

        try:
            user_id = self._auth_manager.extract_data_from_token(session_token)[USER_ID_KEY]
            request.state.therapist_id = user_id
            await self._auth_manager.refresh_session(
                user_id=user_id,
                session_id=session_id,
                response=response
            )
        except Exception as e:
            status_code = general_utilities.extract_status_code(
                e,
                fallback=status.HTTP_401_UNAUTHORIZED
            )
            dependency_container.inject_influx_client().log_error(
                endpoint_name=request.url.path,
                method=request.method,
                error_code=status_code,
                description=str(e),
                session_id=session_id
            )
            raise RuntimeError(e) from e

        try:
            aws_db_client: AwsDbBaseClass = dependency_container.inject_aws_db_client()
            customer_data = await aws_db_client.select(
                user_id=user_id,
                request=request,
                fields=["*"],
                filters={
                    'therapist_id': user_id,
                },
                table_name=SUBSCRIPTION_STATUS_TABLE_NAME
            )
            assert (0 != len(customer_data)), "There isn't a subscription associated with the incoming therapist."
            subscription_id = customer_data[0]['subscription_id']

            stripe_client = dependency_container.inject_stripe_client()
            stripe_client.cancel_customer_subscription(subscription_id=subscription_id)
        except Exception as e:
            status_code = general_utilities.extract_status_code(
                e,
                fallback=status.HTTP_417_EXPECTATION_FAILED
            )
            message = str(e)
            dependency_container.inject_influx_client().log_error(
                endpoint_name=request.url.path,
                method=request.method,
                error_code=status_code,
                description=message,
                session_id=session_id
            )
            raise HTTPException(
                detail="Subscription not found",
                status_code=status_code
            )

        return {}

    async def _update_subscription_internal(
        self,
        session_token: str,
        session_id: str,
        request: Request,
        response: Response,
        behavior: UpdateSubscriptionBehavior,
        subscription_tier: SubscriptionTier
    ):
        """
        Updates the incoming subscription ID with the incoming product information.

        Arguments:
        session_token – the session_token cookie, if exists.
        session_id – the session_id cookie, if exists.
        request – the request object.
        response – the response model with which to create the final response.
        behavior – the update behavior to be invoked.
        subscription_tier – the new tier to be associated with the subscription.
        """
        request.state.session_id = session_id
        if not self._auth_manager.session_token_is_valid(session_token):
            raise SESSION_TOKEN_MISSING_OR_EXPIRED_ERROR

        try:
            user_id = self._auth_manager.extract_data_from_token(session_token)[USER_ID_KEY]
            request.state.therapist_id = user_id
            await self._auth_manager.refresh_session(
                user_id=user_id,
                session_id=session_id,
                response=response
            )
        except Exception as e:
            status_code = general_utilities.extract_status_code(
                e,
                fallback=status.HTTP_401_UNAUTHORIZED
            )
            dependency_container.inject_influx_client().log_error(
                endpoint_name=request.url.path,
                method=request.method,
                error_code=status_code,
                description=str(e),
                session_id=session_id
            )
            raise RuntimeError(e) from e

        try:
            assert behavior != UpdateSubscriptionBehavior.UNSPECIFIED, "Unspecified update behavior"

            aws_db_client: AwsDbBaseClass = dependency_container.inject_aws_db_client()
            customer_data = await aws_db_client.select(
                user_id=user_id,
                request=request,
                fields=["*"],
                filters={
                    'therapist_id': user_id,
                },
                table_name=SUBSCRIPTION_STATUS_TABLE_NAME
            )
            assert (0 != len(customer_data)), "There isn't a subscription associated with the incoming therapist."
            subscription_id = customer_data[0]['subscription_id']

            stripe_client = dependency_container.inject_stripe_client()
            subscription_data = stripe_client.retrieve_subscription(subscription_id=subscription_id)

            if behavior == UpdateSubscriptionBehavior.CHANGE_TIER:
                assert len(subscription_tier.value or '') > 0, "Missing the new tier price ID parameter."

                user_ip_address = retrieve_ip_address(request)
                country_iso = await general_utilities.get_country_iso_code_from_ip(user_ip_address)
                product_catalog = stripe_client.retrieve_product_catalog(country_iso=country_iso)
                price_id = None
                for product in product_catalog:
                    if product['metadata']['product_name'] == subscription_tier.value:
                        price_id = product['price_data']['id']
                        break

                assert len(price_id or '') > 0, "Could not find a product for the incoming request."
                subscription_item_id = subscription_data["items"]["data"][0]["id"]
                stripe_client.update_customer_subscription_plan(
                    subscription_id=subscription_id,
                    subscription_item_id=subscription_item_id,
                    price_id=price_id
                )
            elif behavior == UpdateSubscriptionBehavior.UNDO_CANCELLATION:
                # Check if subscription is already in a canceled state
                assert subscription_data['status'] != 'canceled', "The incoming subscription is already in a canceled state and cannot be resumed."
                stripe_client.resume_cancelled_subscription(subscription_id=subscription_id)
            else:
                raise Exception("Untracked update behavior")

        except Exception as e:
            status_code = general_utilities.extract_status_code(
                e,
                fallback=status.HTTP_417_EXPECTATION_FAILED
            )
            message = str(e)
            dependency_container.inject_influx_client().log_error(
                endpoint_name=request.url.path,
                method=request.method,
                error_code=status_code,
                description=message,
                session_id=session_id
            )
            raise HTTPException(
                detail=message,
                status_code=status_code
            )

        return {}

    async def _retrieve_product_catalog_internal(
        self,
        session_token: str,
        session_id: str,
        request: Request,
        response: Response
    ):
        """
        Retrieves the product catalog for the current user (customer).

        Arguments:
        session_token – the session_token cookie, if exists.
        session_id – the session_id cookie, if exists.
        request – the request object.
        response – the response model with which to create the final response.
        """
        request.state.session_id = session_id
        if not self._auth_manager.session_token_is_valid(session_token):
            raise SESSION_TOKEN_MISSING_OR_EXPIRED_ERROR

        try:
            user_id = self._auth_manager.extract_data_from_token(session_token)[USER_ID_KEY]
            request.state.therapist_id = user_id
            await self._auth_manager.refresh_session(
                user_id=user_id,
                session_id=session_id,
                response=response
            )
        except Exception as e:
            status_code = general_utilities.extract_status_code(
                e,
                fallback=status.HTTP_401_UNAUTHORIZED
            )
            dependency_container.inject_influx_client().log_error(
                endpoint_name=request.url.path,
                method=request.method,
                error_code=status_code,
                description=str(e),
                session_id=session_id
            )
            raise RuntimeError(e) from e

        try:
            user_ip_address = retrieve_ip_address(request)
            country_iso = await general_utilities.get_country_iso_code_from_ip(user_ip_address)

            stripe_client = dependency_container.inject_stripe_client()
            response = stripe_client.retrieve_product_catalog(country_iso=country_iso)
            return {"catalog": response}
        except Exception as e:
            status_code = general_utilities.extract_status_code(
                e,
                fallback=status.HTTP_417_EXPECTATION_FAILED
            )
            message = str(e)
            dependency_container.inject_influx_client().log_error(
                endpoint_name=request.url.path,
                method=request.method,
                error_code=status_code,
                description=message,
                session_id=session_id
            )
            raise HTTPException(
                detail="Subscription not found",
                status_code=status_code
            )

    async def _create_update_payment_method_session_internal(
        self,
        session_token: str,
        session_id: str,
        request: Request,
        response: Response,
        payload: UpdatePaymentMethodPayload
    ):
        """
        Generates a URL for updating a subscription's payment method with the incoming data.

        Arguments:
        session_token – the session_token cookie, if exists.
        session_id – the session_id cookie, if exists.
        request – the request object.
        response – the response model with which to create the final response.
        payload – the JSON payload containing the update data.
        """
        request.state.session_id = session_id
        if not self._auth_manager.session_token_is_valid(session_token):
            raise SESSION_TOKEN_MISSING_OR_EXPIRED_ERROR

        try:
            user_id = self._auth_manager.extract_data_from_token(session_token)[USER_ID_KEY]
            request.state.therapist_id = user_id
            await self._auth_manager.refresh_session(
                user_id=user_id,
                session_id=session_id,
                response=response
            )
        except Exception as e:
            status_code = general_utilities.extract_status_code(
                e,
                fallback=status.HTTP_401_UNAUTHORIZED
            )
            dependency_container.inject_influx_client().log_error(
                endpoint_name=request.url.path,
                method=request.method,
                error_code=status_code,
                description=str(e),
                session_id=session_id
            )
            raise RuntimeError(e) from e

        try:
            aws_db_client: AwsDbBaseClass = dependency_container.inject_aws_db_client()
            customer_data = await aws_db_client.select(
                user_id=user_id,
                request=request,
                fields=["*"],
                filters={
                    'therapist_id': user_id,
                },
                table_name=SUBSCRIPTION_STATUS_TABLE_NAME
            )
            assert (0 != len(customer_data)), "There isn't a subscription associated with the incoming therapist."
            customer_id = customer_data[0]['customer_id']

            stripe_client = dependency_container.inject_stripe_client()
            update_payment_method_url = stripe_client.generate_payment_method_update_session(
                customer_id=customer_id,
                success_url=payload.success_callback_url,
                cancel_url=payload.cancel_callback_url
            )
        except Exception as e:
            status_code = general_utilities.extract_status_code(
                e,
                fallback=status.HTTP_417_EXPECTATION_FAILED
            )
            message = str(e)
            dependency_container.inject_influx_client().log_error(
                endpoint_name=request.url.path,
                method=request.method,
                error_code=status_code,
                description=message,
                session_id=session_id
            )
            raise HTTPException(
                detail=message,
                status_code=status_code
            )

        return { "update_payment_method_url": update_payment_method_url }

    async def _retrieve_payment_history_internal(
        self,
        session_token: str,
        session_id: str,
        request: Request,
        response: Response,
        limit: int,
        starting_after: str | None
    ):
        """
        Retrieves the payment history for the current user (customer).

        Arguments:
        session_token – the session_token cookie, if exists.
        session_id – the session_id cookie, if exists.
        request – the request object.
        response – the response model with which to create the final response.
        limit – the limit for the batch size to be returned.
        starting_after – the id of the last payment that was retrieved (for pagination purposes).
        """
        request.state.session_id = session_id
        if not self._auth_manager.session_token_is_valid(session_token):
            raise SESSION_TOKEN_MISSING_OR_EXPIRED_ERROR

        try:
            user_id = self._auth_manager.extract_data_from_token(session_token)[USER_ID_KEY]
            request.state.therapist_id = user_id
            await self._auth_manager.refresh_session(
                user_id=user_id,
                session_id=session_id,
                response=response
            )
        except Exception as e:
            status_code = general_utilities.extract_status_code(
                e,
                fallback=status.HTTP_401_UNAUTHORIZED
            )
            dependency_container.inject_influx_client().log_error(
                endpoint_name=request.url.path,
                method=request.method,
                error_code=status_code,
                description=str(e),
                session_id=session_id
            )
            raise RuntimeError(e) from e

        try:
            aws_db_client: AwsDbBaseClass = dependency_container.inject_aws_db_client()
            customer_data = await aws_db_client.select(
                user_id=user_id,
                request=request,
                fields=["*"],
                filters={
                    'therapist_id': user_id,
                },
                table_name=SUBSCRIPTION_STATUS_TABLE_NAME
            )
            if (0 == len(customer_data)):
                return {"payments": []}

            customer_id = customer_data[0]['customer_id']

            stripe_client = dependency_container.inject_stripe_client()
            payment_intent_history = stripe_client.retrieve_payment_intent_history(
                customer_id=customer_id,
                limit=limit,
                starting_after=starting_after
            )

            successful_payments = []
            for intent in payment_intent_history["data"]:
                if intent["status"] != "succeeded":
                    continue

                # Format amount
                formatted_price_amount = subscription_utilities.format_currency_amount(
                    amount=float(intent["amount"]),
                    currency_code=intent["currency"]
                )

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
            status_code = general_utilities.extract_status_code(
                e,
                fallback=status.HTTP_417_EXPECTATION_FAILED
            )
            message = str(e)
            dependency_container.inject_influx_client().log_error(
                endpoint_name=request.url.path,
                method=request.method,
                error_code=status_code,
                description=message,
                session_id=session_id
            )
            raise HTTPException(
                detail=message,
                status_code=status_code
            )

        return {"payments": successful_payments}

    async def _capture_payment_event_internal(
        self,
        request: Request
    ):
        """
        Webhook for handling Stripe events.

        Arguments:
        therapist_id – the therapist id.
        request – the incoming request object.
        """
        stripe_client = dependency_container.inject_stripe_client()
        environment = os.environ.get("ENVIRONMENT")

        logging.info(f"Received webhook for environment: {environment}")

        try:
            webhook_secret = ''
            if environment == DEV_ENVIRONMENT:
                webhook_secret = os.getenv("STRIPE_WEBHOOK_SECRET_DEBUG")
            elif environment == STAGING_ENVIRONMENT:
                webhook_secret = os.getenv("STRIPE_WEBHOOK_SECRET_STAGING")
            elif environment == PROD_ENVIRONMENT:
                webhook_secret = os.getenv("STRIPE_WEBHOOK_SECRET_PROD")
            assert len(webhook_secret) > 0, "Empty webhook secret due to invalid environment value"
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=str(e)
            )

        try:
            payload = await request.body()
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_417_EXPECTATION_FAILED,
                detail=str(e)
            )

        try:
            sig_header = request.headers.get("stripe-signature")
            event = stripe_client.construct_webhook_event(payload=payload,
                                                          sig_header=sig_header,
                                                          webhook_secret=webhook_secret)
            logging.info("Successfully constructed Stripe event")

            # In deployed environments, block requests from localhost
            if environment in [STAGING_ENVIRONMENT, PROD_ENVIRONMENT] and request.client.host in ["localhost", "127.0.0.1"]:
                logging.info(f"Blocking localhost request for {environment}")
                raise HTTPException(
                    status_code=403,
                    detail="Webhooks from localhost are not allowed in staging."
                )
        except ValueError:
            # Invalid payload
            logging.error(f"ValueError encountered: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid payload"
            )
        except Exception as e:
            # Check for invalid signature
            logging.error(f"Exception encountered trying to construct the webhook event: {str(e)}")
            if stripe_client.is_signature_verification_error(e=e):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid signature"
                )
            else:
                raise HTTPException(
                    status_code=status.HTTP_417_EXPECTATION_FAILED,
                    detail=str(e)
                )

        try:
            await self._handle_stripe_event(
                event=event,
                request=request,
                stripe_client=stripe_client,
            )
        except Exception as e:
            logging.error(f"Exception encountered handling the Stripe event: {str(e)}")
            raise HTTPException(e)

        return {}

    # Private

    async def _handle_stripe_event(
        self,
        event,
        request: Request,
        stripe_client: StripeBaseClass,
    ):
        """
        Internal funnel for specific handlings of Stripe events.

        Arguments:
        event – the Stripe event.
        stripe_client – the Stripe client.
        """
        event_type: str = event["type"]

        if event_type == 'checkout.session.completed':
            checkout_session = event['data']['object']
            subscription_id = checkout_session.get('subscription', None)
            customer_id = checkout_session.get('customer', None)
            metadata = checkout_session.get('metadata', {})
            therapist_id = None if 'therapist_id' not in metadata else metadata['therapist_id']

            if subscription_id:
                # Update the subscription with metadata
                stripe_client.attach_subscription_metadata(
                    subscription_id=subscription_id,
                    metadata=metadata
                )

                # Attach product metadata to the underlying payment intent
                try:
                    subscription = stripe_client.retrieve_subscription(subscription_id)
                    latest_invoice = stripe_client.retrieve_invoice(subscription.get("latest_invoice", None))
                    payment_intent_id = latest_invoice.get("payment_intent", None)
                    if payment_intent_id is not None:
                        price_id = subscription["items"]["data"][0]["price"]["id"]

                        # Retrieve product metadata associated with the price id.
                        price = stripe_client.retrieve_price(price_id)
                        product_id = price.get("product", None)
                        product = stripe_client.retrieve_product(product_id)
                        stripe_client.attach_payment_intent_metadata(
                            payment_intent_id=payment_intent_id,
                            metadata=product.get("metadata", {})
                        )
                except Exception:
                    pass

        elif event_type == 'invoice.created':
            invoice = event['data']['object']
            subscription_id = invoice.get('subscription', None)
            invoice_metadata = invoice.get("metadata", {})

            # If the invoice has no metadata, and a subscription exists, let's retrieve
            # the subscription object to attach its metadata to the invoice.
            if len(invoice_metadata) == 0 and len(subscription_id or '') > 0:
                subscription = stripe_client.retrieve_subscription(subscription_id)
                invoice_metadata = subscription.get('metadata', {})
                stripe_client.attach_invoice_metadata(
                    invoice_id=invoice['id'],
                    metadata=invoice_metadata
                )

        elif event_type == 'invoice.updated':
            invoice = event['data']['object']
            subscription_id = invoice.get('subscription', None)
            invoice_metadata = invoice.get("metadata", {})

            # If the invoice has no metadata, and a subscription exists, let's retrieve
            # the subscription object to attach its metadata to the invoice.
            if len(invoice_metadata) == 0 and len(subscription_id or '') > 0:
                subscription = stripe_client.retrieve_subscription(subscription_id)
                invoice_metadata = subscription.get('metadata', {})
                stripe_client.attach_invoice_metadata(
                    invoice_id=invoice['id'],
                    metadata=invoice_metadata
                )

        elif event_type == 'invoice.payment_succeeded':
            # TODO: Send ChartWise receipt to user.
            invoice = event['data']['object']

            try:
                # Attach metadata containing the product ID to the payment intent
                payment_intent_id = invoice.get("payment_intent", None)
                assert payment_intent_id, "No ID found for associated payment intent."

                subscription_id = invoice.get("subscription", None)
                assert subscription_id, "No ID found for associated subscription."

                subscription = stripe_client.retrieve_subscription(subscription_id)
                price_id = subscription["items"]["data"][0]["price"]["id"]
                price = stripe_client.retrieve_price(price_id)
                product_id = price.get("product", {})
                product = stripe_client.retrieve_product(product_id)
                product_metadata = product.get("metadata", {})
                stripe_client.attach_payment_intent_metadata(
                    payment_intent_id=payment_intent_id,
                    metadata=product_metadata
                )
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
            await self._handle_subscription_upsert(
                subscription_upsert_event=event,
                request=request
            )
        elif event_type == 'customer.subscription.updated':
            # TODO: Handle Plan Upgrades/Downgrades emails when users change their subscription.
            await self._handle_subscription_upsert(
                subscription_upsert_event=event,
                request=request
            )
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
                secret_manager: AwsSecretManagerBaseClass = dependency_container.inject_aws_secret_manager_client()
                aws_db_client: AwsDbBaseClass = dependency_container.inject_aws_db_client()
                customer_data = await aws_db_client.select_with_stripe_connection(
                    fields=["*"],
                    filters={
                        'customer_id': customer_id,
                    },
                    table_name=SUBSCRIPTION_STATUS_TABLE_NAME,
                    secret_manager=secret_manager,
                    resend_client=dependency_container.inject_resend_client(),
                    request=request,
                )
                assert (0 != len(customer_data)), "No therapist data found for incoming customer ID."
                therapist_id = str(customer_data[0]['therapist_id'])
            except Exception:
                pass

            # Attach the payment method to the customer
            stripe_client.attach_customer_payment_method(
                customer_id=customer_id,
                payment_method_id=payment_method_id
            )

            # Update the default payment method for the subscription
            subscriptions = stripe_client.retrieve_customer_subscriptions(customer_id)
            for subscription in subscriptions:
                try:
                    stripe_client.update_subscription_payment_method(
                        subscription_id=subscription.id,
                        payment_method_id=payment_method_id
                    )
                except Exception as e:
                    if therapist_id is not None:
                        # Failed to update a subscription's payment method. Trigger internal alert, and fail silently.
                        internal_alert = PaymentsActivityAlert(
                            description=("(setup_intent.succeeded) This failure usually is related to not "
                                         "being able to update a subscription's payment method. "
                                         "Please take a look to get a better understanding of the customer's journey."),
                            exception=e,
                            environment=self._environment,
                            therapist_id=therapist_id,
                            subscription_id=subscription.get('id', None),
                            payment_method_id=payment_method_id,
                            customer_id=customer_id)
                        dependency_container.inject_resend_client().send_internal_alert(alert=internal_alert)

        else:
            print(f"[Stripe Event] Unhandled event type: '{event_type}'")

    async def _handle_subscription_upsert(
        self,
        request: Request,
        subscription_upsert_event: dict
    ):
        """
        Handles the upsert of a subscription, updating the subscription status in the database.

        Arguments:
        subscription_upsert_event – the Stripe event containing the subscription data.
        """
        subscription = subscription_upsert_event['data']['object']
        subscription_metadata = subscription.get('metadata', {})

        try:
            therapist_id = subscription_metadata.get('therapist_id', None)
            session_id = subscription_metadata.get('session_id', None)

            assert len(therapist_id or '') > 0, "Did not find a therapist ID in the subscription metadata."
        except Exception:
            return

        stripe_client = dependency_container.inject_stripe_client()
        aws_db_client: AwsDbBaseClass = dependency_container.inject_aws_db_client()

        try:
            secret_manager = dependency_container.inject_aws_secret_manager_client()
            resend_client = dependency_container.inject_resend_client()
            therapist_query_data = await aws_db_client.select_with_stripe_connection(
                resend_client=resend_client,
                fields=["*"],
                filters={ 'id': therapist_id },
                table_name="therapists",
                secret_manager=secret_manager,
                request=request,
            )
            is_new_customer = (0 == len(therapist_query_data))

            # Get customer data
            billing_interval = subscription['items']['data'][0]['plan']['interval']
            current_period_end = datetime.fromtimestamp(subscription["current_period_end"])
            current_billing_period_end_date = current_period_end.date()
            customer_id = subscription.get('customer', None)
            subscription_id = subscription.get('id', None)
            product_id = subscription['items']['data'][0]['price']['product']
            product_data = stripe_client.retrieve_product(product_id)
            stripe_product_name = product_data['metadata']['product_name']
            tier_name = subscription_utilities.map_stripe_product_name_to_chartwise_tier(stripe_product_name)
            is_trialing = subscription['status'] == self.TRIALING
            now_timestamp = datetime.now().date()

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
                trial_end_date_from_timestamp = datetime.fromtimestamp(subscription['trial_end'])
                payload["free_trial_end_date"] = trial_end_date_from_timestamp.date()

            if (subscription.get('status', None) in type(self).ACTIVE_SUBSCRIPTION_STATES):
                # Free trial is ongoing, or subscription is active.
                payload['is_active'] = True
                payload['free_trial_active'] = is_trialing
            else:
                # Subscription is not active. Restrict functionality
                payload['is_active'] = False
                payload['free_trial_active'] = False

            await aws_db_client.upsert_with_stripe_connection(
                request=request,
                conflict_columns=["therapist_id"],
                payload=payload,
                table_name=SUBSCRIPTION_STATUS_TABLE_NAME,
                resend_client=resend_client,
                secret_manager=secret_manager,
            )

            if is_new_customer:
                alert_description = (f"Customer has just entered an active subscription state for the first time. "
                                        "Consider reaching out directly for a more personal welcome note.")
                therapist_name = "".join([therapist_query_data[0]['first_name'],
                                          " ",
                                          therapist_query_data[0]['last_name']])
                alert = CustomerRelationsAlert(
                    description=alert_description,
                    session_id=session_id,
                    environment=self._environment,
                    therapist_id=therapist_id,
                    therapist_name=therapist_name,
                    therapist_email=therapist_query_data[0]['email']
                )
                dependency_container.inject_resend_client().send_customer_relations_alert(alert)
        except Exception as e:
            internal_alert = PaymentsActivityAlert(
                description="(customer.subscription.updated) Failure caught in subscription update.",
                session_id=session_id,
                environment=self._environment,
                therapist_id=therapist_id,
                exception=e,
                subscription_id=subscription_id,
                customer_id=customer_id
            )
            dependency_container.inject_resend_client().send_internal_alert(alert=internal_alert)
