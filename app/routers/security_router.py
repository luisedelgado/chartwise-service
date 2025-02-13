import os, uuid

from datetime import datetime
from enum import Enum
from fastapi import (APIRouter,
                     BackgroundTasks,
                     Body,
                     Cookie,
                     Header,
                     HTTPException,
                     Request,
                     Response,
                     status,)
from langcodes import Language
from typing import Annotated, Optional, Union
from pydantic import BaseModel

from ..internal import security
from ..internal.internal_alert import CustomerRelationsAlert
from ..dependencies.dependency_container import dependency_container, SupabaseBaseClass
from ..internal.schemas import Gender
from ..internal.utilities import datetime_handler, general_utilities
from ..internal.utilities.subscription_utilities import reached_subscription_tier_usage_limit
from ..managers.assistant_manager import AssistantManager
from ..managers.auth_manager import AuthManager
from ..managers.email_manager import EmailManager

class SignInRequest(BaseModel):
    email: str

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

    ROUTER_TAG = "authentication"
    LOGOUT_ENDPOINT = "/v1/logout"
    ACCOUNT_ENDPOINT = "/v1/account"
    SIGNIN_ENDPOINT = "/v1/signin"
    SESSION_REFRESH_ENDPOINT = "/v1/session-refresh"
    SIGNUP_ENDPOINT = "/v1/signup"

    def __init__(self):
        self._auth_manager = AuthManager()
        self._assistant_manager = AssistantManager()
        self._email_manager = EmailManager()
        self.router = APIRouter()
        self._register_routes()

    """
    Registers the set of routes that the class' router can access.
    """
    def _register_routes(self):
        @self.router.post(self.SIGNIN_ENDPOINT, tags=[self.ROUTER_TAG])
        async def signin(signin_data: SignInRequest,
                         response: Response,
                         request: Request,
                         store_access_token: Annotated[str | None, Header()] = None,
                         store_refresh_token: Annotated[str | None, Header()] = None,
                         session_id: Annotated[Union[str, None], Cookie()] = None):
            return await self._signin_internal(email=signin_data.email,
                                               store_access_token=store_access_token,
                                               store_refresh_token=store_refresh_token,
                                               request=request,
                                               response=response,
                                               session_id=session_id)

        @self.router.put(self.SESSION_REFRESH_ENDPOINT, tags=[self.ROUTER_TAG])
        async def refresh_auth_token(request: Request,
                                     response: Response,
                                     store_access_token: Annotated[str | None, Header()] = None,
                                     store_refresh_token: Annotated[str | None, Header()] = None,
                                     authorization: Annotated[Union[str, None], Cookie()] = None,
                                     session_id: Annotated[Union[str, None], Cookie()] = None):
            return await self._refresh_auth_token_internal(authorization=authorization,
                                                           request=request,
                                                           response=response,
                                                           store_access_token=store_access_token,
                                                           store_refresh_token=store_refresh_token,
                                                           session_id=session_id)

        @self.router.post(self.LOGOUT_ENDPOINT, tags=[self.ROUTER_TAG])
        async def logout(request: Request,
                         response: Response,
                         background_tasks: BackgroundTasks,
                         store_access_token: Annotated[str | None, Header()] = None,
                         store_refresh_token: Annotated[str | None, Header()] = None,
                         session_id: Annotated[Union[str, None], Cookie()] = None):
            return await self._logout_internal(request=request,
                                               response=response,
                                               store_access_token=store_access_token,
                                               store_refresh_token=store_refresh_token,
                                               background_tasks=background_tasks,
                                               session_id=session_id)

        @self.router.post(self.SIGNUP_ENDPOINT, tags=[self.ROUTER_TAG])
        async def signup(body: SignupPayload,
                         request: Request,
                         response: Response,
                         store_access_token: Annotated[str | None, Header()] = None,
                         store_refresh_token: Annotated[str | None, Header()] = None,
                         session_id: Annotated[Union[str, None], Cookie()] = None):
            return await self._signup_internal(body=body,
                                               request=request,
                                               response=response,
                                               store_access_token=store_access_token,
                                               store_refresh_token=store_refresh_token,
                                               session_id=session_id)

        @self.router.put(self.ACCOUNT_ENDPOINT, tags=[self.ROUTER_TAG])
        async def update_account_data(request: Request,
                                      response: Response,
                                      body: TherapistUpdatePayload,
                                      store_access_token: Annotated[str | None, Header()] = None,
                                      store_refresh_token: Annotated[str | None, Header()] = None,
                                      authorization: Annotated[Union[str, None], Cookie()] = None,
                                      session_id: Annotated[Union[str, None], Cookie()] = None):
            return await self._update_account_data_internal(request=request,
                                                            response=response,
                                                            body=body,
                                                            store_access_token=store_access_token,
                                                            store_refresh_token=store_refresh_token,
                                                            authorization=authorization,
                                                            session_id=session_id)

        @self.router.delete(self.ACCOUNT_ENDPOINT, tags=[self.ROUTER_TAG])
        async def delete_all_account_data(request: Request,
                                          response: Response,
                                          background_tasks: BackgroundTasks,
                                          store_access_token: Annotated[str | None, Header()] = None,
                                          store_refresh_token: Annotated[str | None, Header()] = None,
                                          authorization: Annotated[Union[str, None], Cookie()] = None,
                                          session_id: Annotated[Union[str, None], Cookie()] = None):
            return await self._delete_all_account_data_internal(request=request,
                                                                response=response,
                                                                background_tasks=background_tasks,
                                                                store_access_token=store_access_token,
                                                                store_refresh_token=store_refresh_token,
                                                                authorization=authorization,
                                                                session_id=session_id)

    """
    Returns an oauth token to be used for invoking the endpoints.

    Arguments:
    email – the email to be used against the authentication process.
    request – the request object.
    response – the response object to be used for creating the final response.
    store_access_token – the store access token.
    store_refresh_token – the store refresh token.
    session_id – the id of the current user session.
    """
    async def _signin_internal(self,
                               email: Annotated[str, Body()],
                               request: Request,
                               response: Response,
                               store_access_token: Annotated[str | None, Header()],
                               store_refresh_token: Annotated[str | None, Header()],
                               session_id: Annotated[Union[str, None], Cookie()]):
        request.state.session_id = session_id
        if store_access_token is None or store_refresh_token is None:
            raise security.STORE_TOKENS_ERROR

        try:
            supabase_client: SupabaseBaseClass = dependency_container.inject_supabase_client_factory().supabase_user_client(access_token=store_access_token,
                                                                                                                            refresh_token=store_refresh_token)
            user_details = supabase_client.get_user().dict()
            token_email = user_details['user']['email']

            assert token_email == email, "Email received does not match the store tokens."

            user_id = user_details['user']['id']
            request.state.therapist_id = user_id
            assert len(user_id or '') > 0, "Failed to authenticate the user. Check the tokens you are sending."

            if session_id is None:
                session_id = uuid.uuid1()
                request.state.session_id = session_id
                response.set_cookie(key="session_id",
                                    value=session_id,
                                    domain=self._auth_manager.APP_COOKIE_DOMAIN,
                                    httponly=True,
                                    secure=True,
                                    samesite="none")

            auth_token = await self._auth_manager.refresh_session(user_id=user_id,
                                                                  response=response)
            customer_data = supabase_client.select(fields="*",
                                                   filters={
                                                       'therapist_id': user_id,
                                                   },
                                                   table_name="subscription_status")
            customer_data_dict = customer_data.dict()

            # Check if this user is already a customer, and has subscription history
            if len(customer_data_dict['data']) == 0:
                is_subscription_active = False
                is_free_trial_active = False
                tier = None
                reached_tier_usage_limit = None
            else:
                is_subscription_active = customer_data_dict['data'][0]['is_active']
                tier = customer_data_dict['data'][0]['current_tier']

                # Determine if free trial is still active
                free_trial_end_date = customer_data_dict['data'][0]['free_trial_end_date']

                if free_trial_end_date is not None:
                    free_trial_end_date_formatted = datetime.strptime(free_trial_end_date, datetime_handler.DATE_FORMAT_YYYY_MM_DD).date()
                    is_free_trial_active = datetime.now().date() < free_trial_end_date_formatted
                else:
                    is_free_trial_active = False

                reached_tier_usage_limit = reached_subscription_tier_usage_limit(tier=tier,
                                                                                 therapist_id=user_id,
                                                                                 supabase_client=supabase_client,
                                                                                 is_free_trial_active=is_free_trial_active)

            await dependency_container.inject_openai_client().clear_chat_history()

            signin_data = {
                "subscription_status" : {
                    "is_free_trial_active": is_free_trial_active,
                    "is_subscription_active": is_subscription_active,
                    "tier": tier,
                    "reached_tier_usage_limit": reached_tier_usage_limit
                }
            }
            signin_data["token"] = auth_token.model_dump()

            return signin_data
        except Exception as e:
            status_code = status.HTTP_401_UNAUTHORIZED
            description = str(e)
            dependency_container.inject_influx_client().log_error(endpoint_name=request.url.path,
                                                                  session_id=session_id,
                                                                  method=request.method,
                                                                  error_code=status_code,
                                                                  description=description)
            raise HTTPException(detail=description, status_code=status_code)

    """
    Refreshes an oauth token to be used for invoking the endpoints.

    Arguments:
    authorization – the authorization cookie, if exists.
    request – the request object.
    response – the response object to be used for creating the final response.
    store_access_token – the store access token.
    store_refresh_token – the store refresh token.
    session_id – the id of the current user session.
    """
    async def _refresh_auth_token_internal(self,
                                           authorization: Annotated[Union[str, None], Cookie()],
                                           request: Request,
                                           response: Response,
                                           store_access_token: Annotated[str | None, Header()],
                                           store_refresh_token: Annotated[str | None, Header()],
                                           session_id: Annotated[Union[str, None], Cookie()]):
        request.state.session_id = session_id
        try:
            if not self._auth_manager.access_token_is_valid(authorization):
                raise security.AUTH_TOKEN_EXPIRED_ERROR

            supabase_client = dependency_container.inject_supabase_client_factory().supabase_user_client(access_token=store_access_token,
                                                                                                         refresh_token=store_refresh_token)

            user_id = supabase_client.get_current_user_id()
            request.state.therapist_id = user_id

            token = await self._auth_manager.refresh_session(user_id=user_id, response=response)

            # Fetch customer data
            customer_data = supabase_client.select(fields="*",
                                                   filters={
                                                       'therapist_id': user_id,
                                                   },
                                                   table_name="subscription_status")
            customer_data_dict = customer_data.dict()

            # Check if this user is already a customer, and has subscription history
            if len(customer_data_dict['data']) == 0:
                is_subscription_active = False
                is_free_trial_active = False
                tier = None
                reached_tier_usage_limit = None
            else:
                is_subscription_active = customer_data_dict['data'][0]['is_active']
                tier = customer_data_dict['data'][0]['current_tier']

                # Determine if free trial is still active
                free_trial_end_date = customer_data_dict['data'][0]['free_trial_end_date']

                if free_trial_end_date is not None:
                    free_trial_end_date_formatted = datetime.strptime(free_trial_end_date, datetime_handler.DATE_FORMAT_YYYY_MM_DD).date()
                    is_free_trial_active = datetime.now().date() < free_trial_end_date_formatted
                else:
                    is_free_trial_active = False

                reached_tier_usage_limit = reached_subscription_tier_usage_limit(tier=tier,
                                                                                 therapist_id=user_id,
                                                                                 supabase_client=supabase_client,
                                                                                 is_free_trial_active=is_free_trial_active)

            token_refresh_data = {
                "subscription_status" : {
                    "is_free_trial_active": is_free_trial_active,
                    "is_subscription_active": is_subscription_active,
                    "tier": tier,
                    "reached_tier_usage_limit": reached_tier_usage_limit
                }
            }
            token_refresh_data["token"] = token.model_dump()

            return token_refresh_data
        except Exception as e:
            description = str(e)
            status_code = general_utilities.extract_status_code(e, fallback=status.HTTP_401_UNAUTHORIZED)
            dependency_container.inject_influx_client().log_error(endpoint_name=request.url.path,
                                                                  session_id=session_id,
                                                                  method=request.method,
                                                                  error_code=status_code,
                                                                  description=description)
            raise HTTPException(status_code=status_code,
                                detail=description)

    """
    Logs out the user.

    Arguments:
    request – the request object.
    response – the object to be used for constructing the final response.
    background_tasks – object for scheduling concurrent tasks.
    store_access_token – the store access token.
    store_refresh_token – the store refresh token.
    session_id – the session_id cookie, if exists.
    """
    async def _logout_internal(self,
                               request: Request,
                               response: Response,
                               background_tasks: BackgroundTasks,
                               store_access_token: Annotated[str | None, Header()],
                               store_refresh_token: Annotated[str | None, Header()],
                               session_id: Annotated[Union[str, None], Cookie()]):
        request.state.session_id = session_id
        user_id = None
        try:
            supabase_client = dependency_container.inject_supabase_client_factory().supabase_user_client(access_token=store_access_token,
                                                                                                         refresh_token=store_refresh_token)
            user_id = supabase_client.get_current_user_id()
        except Exception:
            pass

        request.state.therapist_id = user_id
        self._auth_manager.logout(response)
        background_tasks.add_task(dependency_container.inject_openai_client().clear_chat_history)
        return {}

    """
    Signs up a new therapist user.

    Arguments:
    body – the body associated with the request.
    password – the password associated with the new account.
    request – the request object.
    response – the response object to be used for creating the final response.
    store_access_token – the store access token.
    store_refresh_token – the store refresh token.
    authorization – the authorization cookie, if exists.
    session_id – the session_id cookie, if exists.
    """
    async def _signup_internal(self,
                               body: SignupPayload,
                               request: Request,
                               response: Response,
                               store_access_token: Annotated[str | None, Header()],
                               store_refresh_token: Annotated[str | None, Header()],
                               session_id: Annotated[Union[str, None], Cookie()]):
        request.state.session_id = session_id
        if store_access_token is None or store_refresh_token is None:
            raise security.STORE_TOKENS_ERROR

        try:
            # This endpoint is allowed to be invoked in a user's zero journey when creating an account.
            # The flow is to first add the user to the auth table, and then this codepath adds them to the therapists' table.
            # Because of this, the client may not have an auth cookie yet, so if it isn't present, we'll attempt authentication.
            authorization_data = await self._signin_internal(email=body.email,
                                                             store_access_token=store_access_token,
                                                             store_refresh_token=store_refresh_token,
                                                             request=request,
                                                             response=response,
                                                             session_id=session_id)
        except Exception as e:
            status_code = general_utilities.extract_status_code(e, fallback=status.HTTP_401_UNAUTHORIZED)
            dependency_container.inject_influx_client().log_error(endpoint_name=request.url.path,
                                                                  session_id=session_id,
                                                                  method=request.method,
                                                                  error_code=status_code,
                                                                  description=str(e))
            raise security.STORE_TOKENS_ERROR

        try:
            supabase_client = dependency_container.inject_supabase_client_factory().supabase_user_client(access_token=store_access_token,
                                                                                                         refresh_token=store_refresh_token)
            user_id = supabase_client.get_current_user_id()
            request.state.therapist_id = user_id
            await self._auth_manager.refresh_session(user_id=user_id,
                                                     response=response)
        except Exception as e:
            status_code = general_utilities.extract_status_code(e, fallback=status.HTTP_401_UNAUTHORIZED)
            dependency_container.inject_influx_client().log_error(endpoint_name=request.url.path,
                                                                  session_id=session_id,
                                                                  method=request.method,
                                                                  error_code=status_code,
                                                                  description=str(e))
            raise security.STORE_TOKENS_ERROR

        try:
            body = body.model_dump(exclude_unset=True)

            assert 'gender' not in body or body['gender'] != Gender.UNDEFINED, '''Invalid parameter 'undefined' for gender.'''
            assert 'birth_date' not in body or datetime_handler.is_valid_date(date_input=body['birth_date'],
                                                                              incoming_date_format=datetime_handler.DATE_FORMAT), "Invalid date format. Date should not be in the future, and the expected format is mm-dd-yyyy"
            assert Language.get(body['language_preference']).is_valid(), "Invalid language_preference parameter"

            payload = {
                'id': user_id
            }
            for key, value in body.items():
                if isinstance(value, Enum):
                    value = value.value
                payload[key] = value

            supabase_client.insert(payload=payload, table_name="therapists")

            alert_description = (f"New customer has just signed up for ChartWise.")
            therapist_name = "".join([payload['first_name'],
                                      " ",
                                      payload['last_name']])
            alert = CustomerRelationsAlert(description=alert_description,
                                           session_id=session_id,
                                           environment=os.environ.get('ENVIRONMENT'),
                                           therapist_id=user_id,
                                           therapist_email=payload['email'],
                                           therapist_name=therapist_name)
            await self._email_manager.send_customer_relations_alert(alert)

            response_payload = {
                "therapist_id": user_id
            }
            response_payload.update(authorization_data)
            return response_payload
        except Exception as e:
            description = str(e)
            status_code = general_utilities.extract_status_code(e, fallback=status.HTTP_400_BAD_REQUEST)
            dependency_container.inject_influx_client().log_error(endpoint_name=request.url.path,
                                                                  session_id=session_id,
                                                                  method=request.method,
                                                                  error_code=status_code,
                                                                  description=description)
            raise HTTPException(status_code=status_code,
                                detail=description)

    """
    Updates data associated with a therapist.

    Arguments:
    background_tasks – object for scheduling concurrent tasks.
    request – the request object.
    response – the object to be used for constructing the final response.
    body – the body associated with the request.
    store_access_token – the store access token.
    store_refresh_token – the store refresh token.
    authorization – the authorization cookie, if exists.
    session_id – the session_id cookie, if exists.
    """
    async def _update_account_data_internal(self,
                                            request: Request,
                                            response: Response,
                                            body: TherapistUpdatePayload,
                                            store_access_token: Annotated[str | None, Header()],
                                            store_refresh_token: Annotated[str | None, Header()],
                                            authorization: Annotated[Union[str, None], Cookie()],
                                            session_id: Annotated[Union[str, None], Cookie()]):
        request.state.session_id = session_id
        if not self._auth_manager.access_token_is_valid(authorization):
            raise security.AUTH_TOKEN_EXPIRED_ERROR

        if store_access_token is None or store_refresh_token is None:
            raise security.STORE_TOKENS_ERROR

        try:
            supabase_client = dependency_container.inject_supabase_client_factory().supabase_user_client(access_token=store_access_token,
                                                                                                         refresh_token=store_refresh_token)
            user_id = supabase_client.get_current_user_id()
            request.state.therapist_id = user_id
            await self._auth_manager.refresh_session(user_id=user_id,
                                                     response=response)
        except Exception as e:
            status_code = general_utilities.extract_status_code(e, fallback=status.HTTP_401_UNAUTHORIZED)
            dependency_container.inject_influx_client().log_error(endpoint_name=request.url.path,
                                                                  session_id=session_id,
                                                                  method=request.method,
                                                                  error_code=status_code,
                                                                  description=str(e))
            raise security.STORE_TOKENS_ERROR

        try:
            body = body.model_dump(exclude_unset=True)
            assert 'gender' not in body or body['gender'] != Gender.UNDEFINED, '''Invalid parameter 'undefined' for gender.'''
            assert 'birth_date' not in body or datetime_handler.is_valid_date(date_input=body['birth_date'],
                                                                              incoming_date_format=datetime_handler.DATE_FORMAT), "Invalid date format. Date should not be in the future, and the expected format is mm-dd-yyyy"
            assert 'language_preference' not in body or Language.get(body['language_preference']).is_valid(), "Invalid language_preference parameter"

            payload = {}
            for key, value in body.items():
                if isinstance(value, Enum):
                    value = value.value
                payload[key] = value

            update_response = supabase_client.update(table_name="therapists",
                                                     payload=payload,
                                                     filters={
                                                         'id': user_id
                                                     })
            assert (0 != len((update_response).data)), "Update operation could not be completed."
            return {}
        except Exception as e:
            description = str(e)
            status_code = general_utilities.extract_status_code(e, fallback=status.HTTP_400_BAD_REQUEST)
            dependency_container.inject_influx_client().log_error(endpoint_name=request.url.path,
                                                                  session_id=session_id,
                                                                  method=request.method,
                                                                  error_code=status_code,
                                                                  description=description)
            raise HTTPException(status_code=status_code,
                                detail=description)

    """
    Deletes all data associated with a therapist.

    Arguments:
    background_tasks – object for scheduling concurrent tasks.
    request – the request object.
    response – the object to be used for constructing the final response.
    store_access_token – the store access token.
    store_refresh_token – the store refresh token.
    authorization – the authorization cookie, if exists.
    session_id – the session_id cookie, if exists.
    """
    async def _delete_all_account_data_internal(self,
                                                background_tasks: BackgroundTasks,
                                                request: Request,
                                                response: Response,
                                                store_access_token: Annotated[str | None, Header()],
                                                store_refresh_token: Annotated[str | None, Header()],
                                                authorization: Annotated[Union[str, None], Cookie()],
                                                session_id: Annotated[Union[str, None], Cookie()]):
        request.state.session_id = session_id
        if not self._auth_manager.access_token_is_valid(authorization):
            raise security.AUTH_TOKEN_EXPIRED_ERROR

        if store_access_token is None or store_refresh_token is None:
            raise security.STORE_TOKENS_ERROR

        try:
            supabase_client = dependency_container.inject_supabase_client_factory().supabase_user_client(access_token=store_access_token,
                                                                                                         refresh_token=store_refresh_token)
            user_id = supabase_client.get_current_user_id()
            request.state.therapist_id = user_id
            await self._auth_manager.refresh_session(user_id=user_id,
                                                     response=response)
        except Exception as e:
            status_code = general_utilities.extract_status_code(e, fallback=status.HTTP_401_UNAUTHORIZED)
            dependency_container.inject_influx_client().log_error(endpoint_name=request.url.path,
                                                                  session_id=session_id,
                                                                  method=request.method,
                                                                  error_code=status_code,
                                                                  description=str(e))
            raise security.STORE_TOKENS_ERROR

        try:
            # Cancel Stripe subscription
            customer_data = supabase_client.select(fields="*",
                                                   filters={
                                                       'therapist_id': user_id,
                                                   },
                                                   table_name="subscription_status")
            customer_data_dict = customer_data.dict()
            if len(customer_data_dict['data']) > 0:
                subscription_id = customer_data.dict()['data'][0]['subscription_id']

                stripe_client = dependency_container.inject_stripe_client()
                stripe_client.delete_customer_subscription_immediately(subscription_id=subscription_id)

            # Delete data from all patients
            patients_response = supabase_client.select(fields="id",
                                                       filters={
                                                           "therapist_id": user_id
                                                       },
                                                       table_name="patients")
            patients_response_data = patients_response.dict()
            assert 'data' in patients_response_data, "Failed to retrieve therapist data for patients"
            patient_ids = patients_response_data['data']

            # Delete vectors associated with therapist's patients
            self._assistant_manager.delete_all_sessions_for_therapist(user_id=user_id,
                                                                      patient_ids=patient_ids)

            # Delete therapist and all their patients (through cascading)
            delete_response = supabase_client.delete(table_name="therapists",
                                                     filters={
                                                         'id': user_id
                                                     })
            delete_response_dict = delete_response.dict()['data']
            assert len(delete_response_dict) > 0, "No therapist found with the incoming id"

            therapist_email = delete_response_dict[0]['email']
            alert_description = (f"Customer with therapist ID <i>{user_id}</i>, and email {therapist_email} "
                                 "has canceled their subscription, and deleted all their account data.")
            therapist_name = "".join([delete_response_dict[0]['first_name'],
                                      " ",
                                      delete_response_dict[0]['last_name']])
            alert = CustomerRelationsAlert(description=alert_description,
                                           environment=os.environ.get('ENVIRONMENT'),
                                           session_id=session_id,
                                           therapist_id=user_id,
                                           therapist_email=therapist_email,
                                           therapist_name=therapist_name)
            await self._email_manager.send_customer_relations_alert(alert)

            # Remove the active session and clear Auth data from client storage.
            supabase_client.sign_out()

            # Delete auth and session cookies
            self._auth_manager.logout(response)

            # Delete user from Supabase's Auth schema
            dependency_container.inject_supabase_client_factory().supabase_admin_client().delete_user(user_id)
            return {}
        except Exception as e:
            description = str(e)
            status_code = general_utilities.extract_status_code(e, fallback=status.HTTP_400_BAD_REQUEST)
            dependency_container.inject_influx_client().log_error(endpoint_name=request.url.path,
                                                                  session_id=session_id,
                                                                  method=request.method,
                                                                  error_code=status_code,
                                                                  description=description)
            raise HTTPException(status_code=status_code,
                                detail=description)
