import os, uuid

from datetime import date, datetime
from enum import Enum
from fastapi import (APIRouter,
                     BackgroundTasks,
                     Cookie,
                     HTTPException,
                     Request,
                     Response,
                     Security,
                     status,)
from langcodes import Language
from typing import Annotated, Optional, Union
from pydantic import BaseModel

from ..dependencies.dependency_container import dependency_container, AwsDbBaseClass
from ..internal.internal_alert import CustomerRelationsAlert
from ..internal.security.cognito_auth import verify_cognito_token
from ..internal.security.security_schema import SESSION_TOKEN_MISSING_OR_EXPIRED_ERROR
from ..internal.schemas import (
    Gender,
    DATE_COLUMNS,
    ENCRYPTED_PATIENTS_TABLE_NAME,
    SUBSCRIPTION_STATUS_TABLE_NAME,
    THERAPISTS_TABLE_NAME,
    USER_ID_KEY,
)
from ..internal.utilities import datetime_handler, general_utilities
from ..internal.utilities.subscription_utilities import reached_subscription_tier_usage_limit
from ..managers.assistant_manager import AssistantManager
from ..managers.auth_manager import AuthManager
from ..managers.email_manager import EmailManager

class SignupPayload(BaseModel):
    email: str
    first_name: str
    last_name: str
    birth_date: Optional[str] = None
    language_preference: str
    gender: Optional[Gender] = None

class TherapistUpdatePayload(BaseModel):
    email: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    birth_date: Optional[str] = None
    language_preference: Optional[str] = None
    gender: Optional[Gender] = None

class SecurityRouter:

    AUTHENTICATION_ROUTER_TAG = "authentication"
    THERAPISTS_ROUTER_TAG = "therapists"
    LOGOUT_ENDPOINT = "/v1/logout"
    THERAPISTS_ENDPOINT = "/v1/therapists"
    SIGNIN_ENDPOINT = "/v1/signin"
    SESSION_REFRESH_ENDPOINT = "/v1/session-refresh"

    def __init__(self):
        self._auth_manager = AuthManager()
        self._assistant_manager = AssistantManager()
        self._email_manager = EmailManager()
        self.router = APIRouter()
        self._register_routes()

    def _register_routes(self):
        """
        Registers the set of routes that the class' router can access.
        """
        @self.router.post(self.SIGNIN_ENDPOINT, tags=[self.AUTHENTICATION_ROUTER_TAG])
        async def signin(response: Response,
                         request: Request,
                         user_info: dict = Security(verify_cognito_token),
                         session_id: Annotated[Union[str, None], Cookie()] = None):
            return await self._signin_internal(
                user_info=user_info,
                request=request,
                response=response,
                session_id=session_id
            )

        @self.router.put(self.SESSION_REFRESH_ENDPOINT, tags=[self.AUTHENTICATION_ROUTER_TAG])
        async def refresh_auth_token(request: Request,
                                     response: Response,
                                     _: dict = Security(verify_cognito_token),
                                     session_token: Annotated[Union[str, None], Cookie()] = None,
                                     session_id: Annotated[Union[str, None], Cookie()] = None):
            return await self._refresh_auth_token_internal(
                session_token=session_token,
                request=request,
                response=response,
                session_id=session_id
            )

        @self.router.post(self.LOGOUT_ENDPOINT, tags=[self.AUTHENTICATION_ROUTER_TAG])
        async def logout(request: Request,
                         response: Response,
                         background_tasks: BackgroundTasks,
                         _: dict = Security(verify_cognito_token),
                         session_id: Annotated[Union[str, None], Cookie()] = None):
            return await self._logout_internal(
                request=request,
                response=response,
                background_tasks=background_tasks,
                session_id=session_id
            )

        @self.router.post(self.THERAPISTS_ENDPOINT, tags=[self.THERAPISTS_ROUTER_TAG])
        async def add_therapist(body: SignupPayload,
                                request: Request,
                                response: Response,
                                _: dict = Security(verify_cognito_token),
                                session_token: Annotated[Union[str, None], Cookie()] = None,
                                session_id: Annotated[Union[str, None], Cookie()] = None):
            return await self._add_therapist_internal(
                session_token=session_token,
                body=body,
                request=request,
                response=response,
                session_id=session_id
            )

        @self.router.put(self.THERAPISTS_ENDPOINT, tags=[self.THERAPISTS_ROUTER_TAG])
        async def update_therapist(request: Request,
                                   response: Response,
                                   body: TherapistUpdatePayload,
                                   _: dict = Security(verify_cognito_token),
                                   session_token: Annotated[Union[str, None], Cookie()] = None,
                                   session_id: Annotated[Union[str, None], Cookie()] = None):
            return await self._update_therapist_internal(
                request=request,
                response=response,
                body=body,
                session_token=session_token,
                session_id=session_id
            )

        @self.router.delete(self.THERAPISTS_ENDPOINT, tags=[self.THERAPISTS_ROUTER_TAG])
        async def delete_therapist(request: Request,
                                   response: Response,
                                   _: dict = Security(verify_cognito_token),
                                   session_token: Annotated[Union[str, None], Cookie()] = None,
                                   session_id: Annotated[Union[str, None], Cookie()] = None):
            return await self._delete_therapist_internal(
                request=request,
                response=response,
                session_token=session_token,
                session_id=session_id
            )

    async def _signin_internal(self,
                               user_info: dict,
                               request: Request,
                               response: Response,
                               session_id: Annotated[Union[str, None], Cookie()]):
        """
        Returns an oauth token to be used for invoking the endpoints.

        Arguments:
        user_info – the user information obtained from the authentication token.
        request – the request object.
        response – the response object to be used for creating the final response.
        session_id – the id of the current user session.
        """
        request.state.session_id = session_id
        user_id = user_info.get("sub", "")
        request.state.therapist_id = user_id

        try:
            assert len(user_id or '') > 0, "Failed to authenticate the user. Check the tokens you are sending."

            if session_id is None:
                session_id = uuid.uuid1()
                request.state.session_id = session_id
                response.set_cookie(
                    key=AuthManager.SESSION_ID_KEY,
                    value=session_id,
                    domain=self._auth_manager.APP_COOKIE_DOMAIN,
                    httponly=True,
                    secure=True,
                    samesite="none"
                )

            auth_token = await self._auth_manager.refresh_session(
                user_id=user_id,
                response=response
            )
            await dependency_container.inject_openai_client().clear_chat_history()

            response_payload = {
                "token": auth_token.model_dump()
            }
            subscription_data = await self.subscription_data(
                user_id=user_id,
                request=request,
            )
            response_payload.update(subscription_data)
            return response_payload
        except Exception as e:
            description = str(e)
            status_code = status.HTTP_401_UNAUTHORIZED
            dependency_container.inject_influx_client().log_error(
                endpoint_name=request.url.path,
                session_id=session_id,
                method=request.method,
                error_code=status_code,
                description=description
            )
            raise HTTPException(
                detail=description,
                status_code=status_code
            )

    async def _refresh_auth_token_internal(self,
                                           request: Request,
                                           response: Response,
                                           session_token: Annotated[Union[str, None], Cookie()],
                                           session_id: Annotated[Union[str, None], Cookie()]):
        """
        Refreshes an oauth token to be used for invoking the endpoints.

        Arguments:
        request – the request object.
        response – the response object to be used for creating the final response.
        session_token – the session token cookie, if exists.
        session_id – the id of the current user session.
        """
        request.state.session_id = session_id
        try:
            if not self._auth_manager.session_token_is_valid(session_token):
                raise SESSION_TOKEN_MISSING_OR_EXPIRED_ERROR

            user_id = self._auth_manager.extract_data_from_token(session_token)[USER_ID_KEY]
            request.state.therapist_id = user_id

            token = await self._auth_manager.refresh_session(user_id=user_id, response=response)

            subscription_data = await self.subscription_data(
                user_id=user_id,
                request=request,
            )
            subscription_data["token"] = token.model_dump()
            return subscription_data
        except Exception as e:
            description = str(e)
            status_code = general_utilities.extract_status_code(e, fallback=status.HTTP_401_UNAUTHORIZED)
            dependency_container.inject_influx_client().log_error(
                endpoint_name=request.url.path,
                session_id=session_id,
                method=request.method,
                error_code=status_code,
                description=description
            )
            raise HTTPException(
                status_code=status_code,
                detail=description
            )

    async def _logout_internal(self,
                               request: Request,
                               response: Response,
                               background_tasks: BackgroundTasks,
                               session_id: Annotated[Union[str, None], Cookie()]):
        """
        Logs out the user.

        Arguments:
        request – the request object.
        response – the object to be used for constructing the final response.
        background_tasks – object for scheduling concurrent tasks.
        session_id – the session_id cookie, if exists.
        """
        request.state.session_id = session_id
        self._auth_manager.logout(response)
        background_tasks.add_task(dependency_container.inject_openai_client().clear_chat_history)
        return {}

    async def _add_therapist_internal(self,
                                      body: SignupPayload,
                                      request: Request,
                                      response: Response,
                                      session_token: Annotated[Union[str, None], Cookie()],
                                      session_id: Annotated[Union[str, None], Cookie()]):
        """
        Adds a new therapist.

        Arguments:
        body – the body associated with the request.
        request – the request object.
        response – the response object to be used for creating the final response.
        session_token – the session token cookie, if exists.
        session_id – the session_id cookie, if exists.
        """
        request.state.session_id = session_id

        if not self._auth_manager.session_token_is_valid(session_token):
            raise SESSION_TOKEN_MISSING_OR_EXPIRED_ERROR

        try:
            user_id = self._auth_manager.extract_data_from_token(session_token)[USER_ID_KEY]
            request.state.therapist_id = user_id
            auth_token = await self._auth_manager.refresh_session(
                user_id=user_id,
                response=response
            )
        except Exception as e:
            status_code = general_utilities.extract_status_code(e, fallback=status.HTTP_401_UNAUTHORIZED)
            dependency_container.inject_influx_client().log_error(
                endpoint_name=request.url.path,
                session_id=session_id,
                method=request.method,
                error_code=status_code,
                description=str(e)
            )
            raise Exception(e)

        try:
            body = body.model_dump(exclude_unset=True)

            assert 'gender' not in body or body['gender'] != Gender.UNDEFINED, '''Invalid parameter 'undefined' for gender.'''
            assert 'birth_date' not in body or datetime_handler.is_valid_date(
                date_input=body['birth_date'],
                incoming_date_format=datetime_handler.DATE_FORMAT
            ), "Invalid date format. Date should not be in the future, and the expected format is mm-dd-yyyy"
            assert Language.get(body['language_preference']).is_valid(), "Invalid language_preference parameter"

            payload = {
                'id': user_id,
                'is_active_account': True
            }
            for key, value in body.items():
                if isinstance(value, Enum):
                    value = value.value
                elif key in DATE_COLUMNS:
                    value = datetime.strptime(
                        value,
                        datetime_handler.DATE_FORMAT
                    ).date()
                payload[key] = value

            aws_db_client: AwsDbBaseClass = dependency_container.inject_aws_db_client()
            await aws_db_client.insert(
                user_id=user_id,
                request=request,
                payload=payload,
                table_name=THERAPISTS_TABLE_NAME
            )

            alert_description = (f"New customer has just signed up for ChartWise.")
            therapist_name = "".join(
                [payload['first_name'],
                 " ",
                 payload['last_name']]
            )
            alert = CustomerRelationsAlert(
                description=alert_description,
                session_id=session_id,
                environment=os.environ.get('ENVIRONMENT'),
                therapist_id=user_id,
                therapist_email=payload['email'],
                therapist_name=therapist_name
            )
            await self._email_manager.send_customer_relations_alert(alert)

            response_payload = {
                "therapist_id": user_id,
                "token": auth_token.model_dump()
            }
            subscription_data = await self.subscription_data(
                user_id=user_id,
                request=request,
            )
            response_payload.update(subscription_data)
            return response_payload
        except Exception as e:
            description = str(e)
            status_code = general_utilities.extract_status_code(e, fallback=status.HTTP_400_BAD_REQUEST)
            dependency_container.inject_influx_client().log_error(
                endpoint_name=request.url.path,
                session_id=session_id,
                method=request.method,
                error_code=status_code,
                description=description
            )
            raise HTTPException(
                status_code=status_code,
                detail=description
            )

    async def _update_therapist_internal(self,
                                         request: Request,
                                         response: Response,
                                         body: TherapistUpdatePayload,
                                         session_token: Annotated[Union[str, None], Cookie()],
                                         session_id: Annotated[Union[str, None], Cookie()]):
        """
        Updates data associated with a therapist.

        Arguments:
        request – the request object.
        response – the object to be used for constructing the final response.
        body – the body associated with the request.
        session_token – the session token cookie, if exists.
        session_id – the session_id cookie, if exists.
        """
        request.state.session_id = session_id
        if not self._auth_manager.session_token_is_valid(session_token):
            raise SESSION_TOKEN_MISSING_OR_EXPIRED_ERROR

        try:
            user_id = self._auth_manager.extract_data_from_token(session_token)[USER_ID_KEY]
            request.state.therapist_id = user_id
            await self._auth_manager.refresh_session(
                user_id=user_id,
                response=response
            )
        except Exception as e:
            status_code = general_utilities.extract_status_code(e, fallback=status.HTTP_401_UNAUTHORIZED)
            dependency_container.inject_influx_client().log_error(
                endpoint_name=request.url.path,
                session_id=session_id,
                method=request.method,
                error_code=status_code,
                description=str(e)
            )
            raise Exception(e)

        try:
            body = body.model_dump(exclude_unset=True)
            assert 'gender' not in body or body['gender'] != Gender.UNDEFINED, '''Invalid parameter 'undefined' for gender.'''
            assert 'birth_date' not in body or datetime_handler.is_valid_date(
                date_input=body['birth_date'],
                incoming_date_format=datetime_handler.DATE_FORMAT
            ), "Invalid date format. Date should not be in the future, and the expected format is mm-dd-yyyy"
            assert 'language_preference' not in body or Language.get(body['language_preference']).is_valid(), "Invalid language_preference parameter"

            payload = {}
            for key, value in body.items():
                if isinstance(value, Enum):
                    value = value.value
                elif key in DATE_COLUMNS:
                    value = datetime.strptime(
                        value,
                        datetime_handler.DATE_FORMAT
                    ).date()
                payload[key] = value

            aws_db_client: AwsDbBaseClass = dependency_container.inject_aws_db_client()
            update_response = await aws_db_client.update(
                user_id=user_id,
                request=request,
                table_name="therapists",
                payload=payload,
                filters={
                    'id': user_id
                }
            )
            assert (0 != len(update_response)), "Update operation could not be completed."
            return {}
        except Exception as e:
            description = str(e)
            status_code = general_utilities.extract_status_code(e, fallback=status.HTTP_400_BAD_REQUEST)
            dependency_container.inject_influx_client().log_error(
                endpoint_name=request.url.path,
                session_id=session_id,
                method=request.method,
                error_code=status_code,
                description=description
            )
            raise HTTPException(
                status_code=status_code,
                detail=description
            )

    async def _delete_therapist_internal(self,
                                         request: Request,
                                         response: Response,
                                         session_token: Annotated[Union[str, None], Cookie()],
                                         session_id: Annotated[Union[str, None], Cookie()]):
        """
        Deletes all data associated with a therapist.

        Arguments:
        request – the request object.
        response – the object to be used for constructing the final response.
        session_token – the session_token cookie, if exists.
        session_id – the session_id cookie, if exists.
        """
        request.state.session_id = session_id
        if not self._auth_manager.session_token_is_valid(session_token):
            raise SESSION_TOKEN_MISSING_OR_EXPIRED_ERROR

        try:
            user_id = self._auth_manager.extract_data_from_token(session_token)[USER_ID_KEY]
            request.state.therapist_id = user_id
            await self._auth_manager.refresh_session(
                user_id=user_id,
                response=response
            )
        except Exception as e:
            status_code = general_utilities.extract_status_code(e, fallback=status.HTTP_401_UNAUTHORIZED)
            dependency_container.inject_influx_client().log_error(
                endpoint_name=request.url.path,
                session_id=session_id,
                method=request.method,
                error_code=status_code,
                description=str(e)
            )
            raise Exception(e)

        try:
            # Cancel Stripe subscription
            aws_db_client: AwsDbBaseClass = dependency_container.inject_aws_db_client()
            customer_data_dict = await aws_db_client.select(
                user_id=user_id,
                request=request,
                fields=["subscription_id"],
                filters={
                    'therapist_id': user_id,
                },
                table_name=SUBSCRIPTION_STATUS_TABLE_NAME
            )

            if len(customer_data_dict) > 0:
                subscription_id = customer_data_dict['subscription_id']

                stripe_client = dependency_container.inject_stripe_client()
                stripe_client.delete_customer_subscription_immediately(subscription_id=subscription_id)

                await aws_db_client.update(
                    user_id=user_id,
                    request=request,
                    payload={
                        'is_active': False,
                        'free_trial_active': False
                    },
                    filters={
                        'therapist_id': user_id,
                    },
                    table_name=SUBSCRIPTION_STATUS_TABLE_NAME
                )

            # Delete patient data associated with therapist.
            delete_patients_operation = await aws_db_client.delete(
                user_id=user_id,
                request=request,
                table_name=ENCRYPTED_PATIENTS_TABLE_NAME,
                filters={
                    "therapist_id": user_id
                }
            )
            patient_ids = [item['id'] for item in delete_patients_operation]

            # Delete vectors associated with the deleted patient ids.
            self._assistant_manager.delete_all_sessions_for_therapist(
                user_id=user_id,
                patient_ids=patient_ids
            )

            # Set therapist user as an inactive account.
            disable_account_response_dict = await aws_db_client.update(
                user_id=user_id,
                request=request,
                table_name="therapists",
                filters={
                    'id': user_id
                },
                payload={
                    'is_active_account': False
                }
            )
            assert len(disable_account_response_dict) > 0, "No therapist found with the incoming id"

            therapist_email = disable_account_response_dict['email']
            alert_description = (f"Customer with therapist ID <i>{user_id}</i>, and email {therapist_email} "
                                 "has canceled their subscription, and deleted all their account data.")
            therapist_name = "".join([disable_account_response_dict['first_name'],
                                      " ",
                                      disable_account_response_dict['last_name']])
            alert = CustomerRelationsAlert(
                description=alert_description,
                environment=os.environ.get('ENVIRONMENT'),
                session_id=session_id,
                therapist_id=user_id,
                therapist_email=therapist_email,
                therapist_name=therapist_name
            )
            await self._email_manager.send_customer_relations_alert(alert)

            # Remove the active session and clear Auth data from client storage.
            await aws_db_client.sign_out()

            # Delete auth and session cookies
            self._auth_manager.logout(response)

            # Delete user from our DB's Auth schema
            await aws_db_client.delete_user(
                request=request,
                user_id=user_id,
            )
            return {}
        except Exception as e:
            description = str(e)
            status_code = general_utilities.extract_status_code(e, fallback=status.HTTP_400_BAD_REQUEST)
            dependency_container.inject_influx_client().log_error(
                endpoint_name=request.url.path,
                session_id=session_id,
                method=request.method,
                error_code=status_code,
                description=description
            )
            raise HTTPException(
                status_code=status_code,
                detail=description
            )

    async def subscription_data(self,
                                user_id: str,
                                request: Request):
        """
        Returns a JSON object representing the subscription status of the user.
        Arguments:
        user_id – the id of the user.
        request – the upstream request object.
        """
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

            # Check if this user is already a customer, and has subscription history
            if len(customer_data) == 0:
                is_subscription_active = False
                is_free_trial_active = False
                tier = None
                reached_tier_usage_limit = None
            else:
                is_subscription_active = customer_data[0]['is_active']
                tier = customer_data[0]['current_tier']

                # Determine if free trial is still active
                free_trial_end_date: date = customer_data[0]['free_trial_end_date']

                if free_trial_end_date is not None:
                    is_free_trial_active = (datetime.now().date() < free_trial_end_date)
                else:
                    is_free_trial_active = False

                reached_tier_usage_limit = await reached_subscription_tier_usage_limit(
                    tier=tier,
                    therapist_id=user_id,
                    aws_db_client=aws_db_client,
                    is_free_trial_active=is_free_trial_active
                )
            return {
                "subscription_status" : {
                    "is_free_trial_active": is_free_trial_active,
                    "is_subscription_active": is_subscription_active,
                    "tier": tier,
                    "reached_tier_usage_limit": reached_tier_usage_limit
                }
            }
        except Exception as e:
            return {
                "subscription_status": None
            }
