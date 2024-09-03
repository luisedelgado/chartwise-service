import uuid

from enum import Enum
from fastapi import (APIRouter,
                     BackgroundTasks,
                     Cookie,
                     HTTPException,
                     Request,
                     Response,
                     status,)
from langcodes import Language
from typing import Annotated, Optional, Union
from pydantic import BaseModel

from ..internal import router_dependencies, security
from ..internal.logging import Logger
from ..internal.schemas import Gender
from ..internal.utilities import datetime_handler, general_utilities
from ..managers.assistant_manager import AssistantManager
from ..managers.auth_manager import AuthManager

class LoginMechanism(Enum):
    UNDEFINED = "undefined"
    GOOGLE = "google"
    FACEBOOK = "facebook"
    INTERNAL = "internal"

class LoginData(BaseModel):
    datastore_access_token: str
    datastore_refresh_token: str
    user_id: str

class RefreshAuthData(BaseModel):
    user_id: str

class TherapistInsertPayload(BaseModel):
    email: str
    first_name: str
    last_name: str
    birth_date: Optional[str] = None
    login_mechanism: LoginMechanism
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
    TOKEN_ENDPOINT = "/token"
    ACCOUNT_ENDPOINT = "/v1/account"

    def __init__(self,
                 auth_manager: AuthManager,
                 assistant_manager: AssistantManager,
                 router_dependencies: router_dependencies.RouterDependencies):
        self._auth_manager = auth_manager
        self._assistant_manager = assistant_manager
        self._supabase_client_factory = router_dependencies.supabase_client_factory
        self._pinecone_client = router_dependencies.pinecone_client
        self._openai_client = router_dependencies.openai_client
        self.router = APIRouter()
        self._register_routes()

    """
    Registers the set of routes that the class' router can access.
    """
    def _register_routes(self):
        @self.router.post(self.TOKEN_ENDPOINT, tags=[self.ROUTER_TAG])
        async def request_new_access_token(body: LoginData,
                                           background_tasks: BackgroundTasks,
                                           response: Response,
                                           request: Request,
                                           session_id: Annotated[Union[str, None], Cookie()] = None) -> security.Token:
            return await self._request_new_access_token_internal(body=body,
                                                                 background_tasks=background_tasks,
                                                                 request=request,
                                                                 response=response,
                                                                 session_id=session_id)

        @self.router.put(self.TOKEN_ENDPOINT, tags=[self.ROUTER_TAG])
        async def refresh_access_token(refresh_data: RefreshAuthData,
                                       background_tasks: BackgroundTasks,
                                       response: Response,
                                       request: Request,
                                       authorization: Annotated[Union[str, None], Cookie()] = None,
                                       session_id: Annotated[Union[str, None], Cookie()] = None) -> security.Token:
            return await self._refresh_authorization_token_internal(user_id=refresh_data.user_id,
                                                                    background_tasks=background_tasks,
                                                                    request=request,
                                                                    response=response,
                                                                    authorization=authorization,
                                                                    session_id=session_id)

        @self.router.post(self.LOGOUT_ENDPOINT, tags=[self.ROUTER_TAG])
        async def logout(response: Response,
                         background_tasks: BackgroundTasks,
                         datastore_access_token: Annotated[Union[str, None], Cookie()] = None,
                         datastore_refresh_token: Annotated[Union[str, None], Cookie()] = None,
                         session_id: Annotated[Union[str, None], Cookie()] = None):
            return await self._logout_internal(response=response,
                                               datastore_access_token=datastore_access_token,
                                               datastore_refresh_token=datastore_refresh_token,
                                               background_tasks=background_tasks,
                                               session_id=session_id)

        @self.router.post(self.ACCOUNT_ENDPOINT, tags=[self.ROUTER_TAG])
        async def add_new_account(body: TherapistInsertPayload,
                                  response: Response,
                                  request: Request,
                                  background_tasks: BackgroundTasks,
                                  datastore_access_token: Annotated[Union[str, None], Cookie()] = None,
                                  datastore_refresh_token: Annotated[Union[str, None], Cookie()] = None,
                                  authorization: Annotated[Union[str, None], Cookie()] = None,
                                  session_id: Annotated[Union[str, None], Cookie()] = None):
            return await self._add_new_account_internal(body=body,
                                                        response=response,
                                                        request=request,
                                                        background_tasks=background_tasks,
                                                        datastore_access_token=datastore_access_token,
                                                        datastore_refresh_token=datastore_refresh_token,
                                                        authorization=authorization,
                                                        session_id=session_id)

        @self.router.put(self.ACCOUNT_ENDPOINT, tags=[self.ROUTER_TAG])
        async def update_account_data(response: Response,
                                      request: Request,
                                      background_tasks: BackgroundTasks,
                                      body: TherapistUpdatePayload,
                                      datastore_access_token: Annotated[Union[str, None], Cookie()] = None,
                                      datastore_refresh_token: Annotated[Union[str, None], Cookie()] = None,
                                      authorization: Annotated[Union[str, None], Cookie()] = None,
                                      session_id: Annotated[Union[str, None], Cookie()] = None):
            return await self._update_account_data_internal(response=response,
                                                            request=request,
                                                            background_tasks=background_tasks,
                                                            body=body,
                                                            datastore_access_token=datastore_access_token,
                                                            datastore_refresh_token=datastore_refresh_token,
                                                            authorization=authorization,
                                                            session_id=session_id)

        @self.router.delete(self.ACCOUNT_ENDPOINT, tags=[self.ROUTER_TAG])
        async def delete_all_account_data(response: Response,
                                          request: Request,
                                          background_tasks: BackgroundTasks,
                                          datastore_access_token: Annotated[Union[str, None], Cookie()] = None,
                                          datastore_refresh_token: Annotated[Union[str, None], Cookie()] = None,
                                          authorization: Annotated[Union[str, None], Cookie()] = None,
                                          session_id: Annotated[Union[str, None], Cookie()] = None):
            return await self._delete_all_account_data_internal(response=response,
                                                                request=request,
                                                                background_tasks=background_tasks,
                                                                datastore_access_token=datastore_access_token,
                                                                datastore_refresh_token=datastore_refresh_token,
                                                                authorization=authorization,
                                                                session_id=session_id)

    """
    Returns an oauth token to be used for invoking the endpoints.

    Arguments:
    body – the body associated with the request.
    background_tasks – object for scheduling concurrent tasks.
    request – the incoming request object.
    response – the response object to be used for creating the final response.
    session_id – the id of the current user session.
    """
    async def _request_new_access_token_internal(self,
                                                 body: LoginData,
                                                 background_tasks: BackgroundTasks,
                                                 request: Request,
                                                 response: Response,
                                                 session_id: Annotated[Union[str, None], Cookie()]) -> security.Token:
        try:
            if session_id is None:
                session_id = uuid.uuid1()
                response.set_cookie(key="session_id",
                                    value=session_id,
                                    domain=self._auth_manager.APP_COOKIE_DOMAIN,
                                    httponly=True,
                                    secure=True,
                                    samesite="none")

            logger = Logger(supabase_client_factory=self._supabase_client_factory)
            post_api_method = logger.API_METHOD_POST
            logger.log_api_request(background_tasks=background_tasks,
                                   session_id=session_id,
                                   method=post_api_method,
                                   endpoint_name=self.TOKEN_ENDPOINT,
                                   therapist_id=body.user_id)

            supabase_client = self._supabase_client_factory.supabase_user_client(access_token=body.datastore_access_token,
                                                                                 refresh_token=body.datastore_refresh_token)
            authenticated_successfully = self._auth_manager.authenticate_datastore_user(user_id=body.user_id,
                                                                                        supabase_client=supabase_client)
            assert authenticated_successfully, "Failed to authenticate the user. Check the tokens you are sending."

            await self._openai_client.clear_chat_history()
            auth_token = await self._auth_manager.refresh_session(user_id=body.user_id,
                                                                  request=request,
                                                                  response=response,
                                                                  supabase_client_factory=self._supabase_client_factory,
                                                                  datastore_access_token=body.datastore_access_token,
                                                                  datastore_refresh_token=body.datastore_refresh_token)
            logger.log_api_response(background_tasks=background_tasks,
                                    session_id=session_id,
                                    endpoint_name=self.TOKEN_ENDPOINT,
                                    http_status_code=status.HTTP_200_OK,
                                    therapist_id=body.user_id,
                                    method=post_api_method)
            return auth_token
        except Exception as e:
            status_code = general_utilities.extract_status_code(e, fallback=status.HTTP_401_UNAUTHORIZED)
            raise HTTPException(detail=str(e), status_code=status_code)

    """
    Refreshes an existing authorization token that may or may have not expired.

    Arguments:
    user_id – the current user's id.
    background_tasks – object for scheduling concurrent tasks.
    request – the incoming request object.
    response – the response object to be used for creating the final response.
    authorization – the current authorization token to be updated.
    session_id – the id of the current user session.
    """
    async def _refresh_authorization_token_internal(self,
                                                    user_id: str,
                                                    background_tasks: BackgroundTasks,
                                                    request: Request,
                                                    response: Response,
                                                    authorization: Annotated[Union[str, None], Cookie()],
                                                    session_id: Annotated[Union[str, None], Cookie()]) -> security.Token:
        try:
            assert len(authorization or '') > 0, "There isn't an existing authorization token to be refreshed."
            assert len(user_id or '') > 0, "user_id param is missing"
        except Exception as e:
            raise HTTPException(detail=str(e),
                                status_code=status.HTTP_400_BAD_REQUEST)

        try:
            logger = Logger(supabase_client_factory=self._supabase_client_factory)
            put_api_method = logger.API_METHOD_PUT
            logger.log_api_request(background_tasks=background_tasks,
                                   session_id=session_id,
                                   method=put_api_method,
                                   endpoint_name=self.TOKEN_ENDPOINT,
                                   therapist_id=user_id)

            auth_token = await self._auth_manager.refresh_session(user_id=user_id,
                                                                  request=request,
                                                                  response=response,
                                                                  supabase_client_factory=self._supabase_client_factory)
            logger.log_api_response(background_tasks=background_tasks,
                                    session_id=session_id,
                                    endpoint_name=self.TOKEN_ENDPOINT,
                                    http_status_code=status.HTTP_200_OK,
                                    therapist_id=user_id,
                                    method=put_api_method)
            return auth_token
        except Exception as e:
            status_code = general_utilities.extract_status_code(e, fallback=status.HTTP_401_UNAUTHORIZED)
            raise HTTPException(detail=str(e), status_code=status_code)

    """
    Logs out the user.

    Arguments:
    response – the object to be used for constructing the final response.
    background_tasks – object for scheduling concurrent tasks.
    datastore_access_token – the datastore access token.
    datastore_refresh_token – the datastore refresh token.
    session_id – the session_id cookie, if exists.
    """
    async def _logout_internal(self,
                               response: Response,
                               background_tasks: BackgroundTasks,
                               datastore_access_token: Annotated[Union[str, None], Cookie()],
                               datastore_refresh_token: Annotated[Union[str, None], Cookie()],
                               session_id: Annotated[Union[str, None], Cookie()]):
        user_id = None
        try:
            supabase_client = self._supabase_client_factory.supabase_user_client(refresh_token=datastore_refresh_token,
                                                                                 access_token=datastore_access_token)
            user_id = supabase_client.get_current_user_id()
        except Exception:
            pass

        self._auth_manager.logout(response)
        background_tasks.add_task(self._openai_client.clear_chat_history)

        if user_id is not None:
            background_tasks.add_task(self._schedule_logout_activity_logging,
                                      background_tasks,
                                      user_id,
                                      session_id)
        return {}

    """
    Signs up a new therapist user.

    Arguments:
    body – the body associated with the request.
    background_tasks – object for scheduling concurrent tasks.
    request – the incoming request object.
    response – the response model to be used for creating the final response.
    datastore_access_token – the datastore access token.
    datastore_refresh_token – the datastore refresh token.
    authorization – the authorization cookie, if exists.
    session_id – the session_id cookie, if exists.
    """
    async def _add_new_account_internal(self,
                                        body: TherapistInsertPayload,
                                        background_tasks: BackgroundTasks,
                                        request: Request,
                                        response: Response,
                                        datastore_access_token: Annotated[Union[str, None], Cookie()],
                                        datastore_refresh_token: Annotated[Union[str, None], Cookie()],
                                        authorization: Annotated[Union[str, None], Cookie()],
                                        session_id: Annotated[Union[str, None], Cookie()]):
        if not self._auth_manager.access_token_is_valid(authorization):
            raise security.AUTH_TOKEN_EXPIRED_ERROR

        if datastore_access_token is None or datastore_refresh_token is None:
            raise security.DATASTORE_TOKENS_ERROR

        try:
            supabase_client = self._supabase_client_factory.supabase_user_client(refresh_token=datastore_refresh_token,
                                                                                 access_token=datastore_access_token)
            user_id = supabase_client.get_current_user_id()
            await self._auth_manager.refresh_session(user_id=user_id,
                                                     request=request,
                                                     response=response,
                                                     supabase_client_factory=self._supabase_client_factory)
        except Exception as e:
            status_code = general_utilities.extract_status_code(e, fallback=status.HTTP_401_UNAUTHORIZED)
            raise HTTPException(status_code=status_code, detail=str(e))

        logger = Logger(supabase_client_factory=self._supabase_client_factory)
        post_api_method = logger.API_METHOD_POST
        logger.log_api_request(background_tasks=background_tasks,
                               session_id=session_id,
                               method=post_api_method,
                               therapist_id=user_id,
                               endpoint_name=self.ACCOUNT_ENDPOINT)

        try:
            body = body.dict(exclude_unset=True)

            assert body['login_mechanism'] != LoginMechanism.UNDEFINED, '''Invalid parameter 'undefined' for login_mechanism.'''
            assert 'gender' not in body or body['gender'] != Gender.UNDEFINED, '''Invalid parameter 'undefined' for gender.'''
            assert 'birth_date' not in body or datetime_handler.is_valid_date(date_input=body['birth_date'],
                                                                              incoming_date_format=datetime_handler.DATE_FORMAT), "Invalid date format. Date should not be in the future, and the expected format is mm-dd-yyyy"
            assert Language.get(body['language_preference']).is_valid(), "Invalid language_preference parameter"

            payload = {}
            for key, value in body.items():
                if isinstance(value, Enum):
                    value = value.value
                payload[key] = value

            supabase_client.insert(payload=payload, table_name="therapists")

            logger.log_api_response(background_tasks=background_tasks,
                                    therapist_id=user_id,
                                    session_id=session_id,
                                    endpoint_name=self.ACCOUNT_ENDPOINT,
                                    http_status_code=status.HTTP_200_OK,
                                    method=post_api_method)

            return {"therapist_id": user_id}
        except Exception as e:
            description = str(e)
            status_code = general_utilities.extract_status_code(e, fallback=status.HTTP_400_BAD_REQUEST)
            logger.log_error(background_tasks=background_tasks,
                             session_id=session_id,
                             endpoint_name=self.ACCOUNT_ENDPOINT,
                             error_code=status_code,
                             description=description,
                             method=post_api_method)
            raise HTTPException(status_code=status_code,
                                detail=description)

    """
    Updates data associated with a therapist.

    Arguments:
    background_tasks – object for scheduling concurrent tasks.
    response – the object to be used for constructing the final response.
    request – the incoming request object.
    body – the body associated with the request.
    datastore_access_token – the datastore access token.
    datastore_refresh_token – the datastore refresh token.
    authorization – the authorization cookie, if exists.
    session_id – the session_id cookie, if exists.
    """
    async def _update_account_data_internal(self,
                                            background_tasks: BackgroundTasks,
                                            response: Response,
                                            request: Request,
                                            body: TherapistUpdatePayload,
                                            datastore_access_token: Annotated[Union[str, None], Cookie()],
                                            datastore_refresh_token: Annotated[Union[str, None], Cookie()],
                                            authorization: Annotated[Union[str, None], Cookie()],
                                            session_id: Annotated[Union[str, None], Cookie()]):
        if not self._auth_manager.access_token_is_valid(authorization):
            raise security.AUTH_TOKEN_EXPIRED_ERROR

        if datastore_access_token is None or datastore_refresh_token is None:
            raise security.DATASTORE_TOKENS_ERROR

        try:
            supabase_client = self._supabase_client_factory.supabase_user_client(access_token=datastore_access_token,
                                                                                 refresh_token=datastore_refresh_token)
            user_id = supabase_client.get_current_user_id()
            await self._auth_manager.refresh_session(user_id=user_id,
                                                     request=request,
                                                     response=response,
                                                     supabase_client_factory=self._supabase_client_factory)
        except Exception as e:
            status_code = general_utilities.extract_status_code(e, fallback=status.HTTP_401_UNAUTHORIZED)
            raise HTTPException(status_code=status_code, detail=str(e))

        logger = Logger(supabase_client_factory=self._supabase_client_factory)
        put_api_method = logger.API_METHOD_PUT
        logger.log_api_request(background_tasks=background_tasks,
                               session_id=session_id,
                               therapist_id=user_id,
                               method=put_api_method,
                               endpoint_name=self.ACCOUNT_ENDPOINT)
        try:
            body = body.dict(exclude_unset=True)
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

            logger.log_api_response(background_tasks=background_tasks,
                                    therapist_id=user_id,
                                    session_id=session_id,
                                    endpoint_name=self.ACCOUNT_ENDPOINT,
                                    http_status_code=status.HTTP_200_OK,
                                    method=put_api_method)
            return {}
        except Exception as e:
            description = str(e)
            status_code = general_utilities.extract_status_code(e, fallback=status.HTTP_400_BAD_REQUEST)
            logger.log_error(background_tasks=background_tasks,
                             session_id=session_id,
                             endpoint_name=self.ACCOUNT_ENDPOINT,
                             error_code=status_code,
                             description=description,
                             method=put_api_method)
            raise HTTPException(status_code=status_code,
                                detail=description)

    """
    Deletes all data associated with a therapist.

    Arguments:
    background_tasks – object for scheduling concurrent tasks.
    response – the object to be used for constructing the final response.
    request – the incoming request object.
    datastore_access_token – the datastore access token.
    datastore_refresh_token – the datastore refresh token.
    authorization – the authorization cookie, if exists.
    session_id – the session_id cookie, if exists.
    """
    async def _delete_all_account_data_internal(self,
                                                background_tasks: BackgroundTasks,
                                                response: Response,
                                                request: Request,
                                                datastore_access_token: Annotated[Union[str, None], Cookie()],
                                                datastore_refresh_token: Annotated[Union[str, None], Cookie()],
                                                authorization: Annotated[Union[str, None], Cookie()],
                                                session_id: Annotated[Union[str, None], Cookie()]):
        if not self._auth_manager.access_token_is_valid(authorization):
            raise security.AUTH_TOKEN_EXPIRED_ERROR

        if datastore_access_token is None or datastore_refresh_token is None:
            raise security.DATASTORE_TOKENS_ERROR

        try:
            supabase_client = self._supabase_client_factory.supabase_user_client(access_token=datastore_access_token,
                                                                                 refresh_token=datastore_refresh_token)
            user_id = supabase_client.get_current_user_id()
            await self._auth_manager.refresh_session(user_id=user_id,
                                                     response=response,
                                                     request=request,
                                                     supabase_client_factory=self._supabase_client_factory)
        except Exception as e:
            status_code = general_utilities.extract_status_code(e, fallback=status.HTTP_401_UNAUTHORIZED)
            raise HTTPException(status_code=status_code, detail=str(e))

        logger = Logger(supabase_client_factory=self._supabase_client_factory)
        delete_api_method = logger.API_METHOD_DELETE
        logger.log_api_request(background_tasks=background_tasks,
                               session_id=session_id,
                               therapist_id=user_id,
                               method=delete_api_method,
                               endpoint_name=self.ACCOUNT_ENDPOINT)
        try:
            patients_response = supabase_client.select(fields="id",
                                                       filters={
                                                           "therapist_id": user_id
                                                       },
                                                       table_name="patients")
            patients_response_data = patients_response.dict()
            assert 'data' in patients_response_data, "Failed to retrieve therapist data for patients"
            patient_ids = patients_response_data['data']

            # Delete therapist and all their patients (through cascading)
            delete_response = supabase_client.delete(table_name="therapists",
                                                     filters={
                                                         'id': user_id
                                                     })
            assert len(delete_response.dict()['data']) > 0, "No therapist found with the incoming id"

            # Remove the active session and clear Auth data from client storage.
            supabase_client.sign_out()

            # Delete vectors associated with therapist's patients
            self._assistant_manager.delete_all_sessions_for_therapist(user_id=user_id,
                                                                      patient_ids=patient_ids,
                                                                      pinecone_client=self._pinecone_client)

            # Delete auth and session cookies
            self._auth_manager.logout(response)

            logger.log_account_deletion(background_tasks=background_tasks,
                                        therapist_id=user_id)
            logger.log_api_response(background_tasks=background_tasks,
                                    therapist_id=user_id,
                                    session_id=session_id,
                                    endpoint_name=self.ACCOUNT_ENDPOINT,
                                    http_status_code=status.HTTP_200_OK,
                                    method=delete_api_method)
            return {}
        except Exception as e:
            description = str(e)
            status_code = general_utilities.extract_status_code(e, fallback=status.HTTP_400_BAD_REQUEST)
            logger.log_error(background_tasks=background_tasks,
                             session_id=session_id,
                             endpoint_name=self.ACCOUNT_ENDPOINT,
                             error_code=status_code,
                             description=description,
                             method=delete_api_method)
            raise HTTPException(status_code=status_code,
                                detail=description)

    async def _schedule_logout_activity_logging(self,
                                                background_tasks: BackgroundTasks,
                                                user_id: str,
                                                session_id: Annotated[Union[str, None], Cookie()]):
        try:
            logger = Logger(supabase_client_factory=self._supabase_client_factory)
            post_api_method = logger.API_METHOD_POST
            logger.log_api_request(background_tasks=background_tasks,
                                session_id=session_id,
                                therapist_id=user_id,
                                method=post_api_method,
                                endpoint_name=self.LOGOUT_ENDPOINT)
            logger.log_api_response(background_tasks=background_tasks,
                                    session_id=session_id,
                                    therapist_id=user_id,
                                    endpoint_name=self.LOGOUT_ENDPOINT,
                                    http_status_code=status.HTTP_200_OK,
                                    method=post_api_method)
        except Exception:
            #Fail silently since there's no need to throw
            pass
