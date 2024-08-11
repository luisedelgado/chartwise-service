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

class SignupMechanism(Enum):
    UNDEFINED = "undefined"
    GOOGLE = "google"
    FACEBOOK = "facebook"
    INTERNAL = "internal"

class LoginData(BaseModel):
    datastore_access_token: Optional[str] = None
    datastore_refresh_token: Optional[str] = None
    user_id: str

class LogoutData(BaseModel):
    therapist_id: str

class TherapistInsertPayload(BaseModel):
    id: str
    email: str
    first_name: str
    middle_name: Optional[str] = None
    last_name: str
    birth_date: str
    signup_mechanism: SignupMechanism
    language_preference: str
    gender: Gender

class TherapistUpdatePayload(BaseModel):
    id: str
    email: Optional[str] = None
    first_name: Optional[str] = None
    middle_name: Optional[str] = None
    last_name: Optional[str] = None
    birth_date: Optional[str] = None
    language_preference: Optional[str] = None
    gender: Optional[Gender] = None

class SecurityRouter:

    ROUTER_TAG = "authentication"
    LOGOUT_ENDPOINT = "/v1/logout"
    TOKEN_ENDPOINT = "/token"
    THERAPISTS_ENDPOINT = "/v1/therapists"

    def __init__(self,
                 auth_manager: AuthManager,
                 assistant_manager: AssistantManager,
                 router_dependencies: router_dependencies.RouterDependencies):
        self._auth_manager = auth_manager
        self._assistant_manager = assistant_manager
        self._supabase_client_factory = router_dependencies.supabase_client_factory
        self._pinecone_client = router_dependencies.pinecone_client
        self.router = APIRouter()
        self._register_routes()

    """
    Registers the set of routes that the class' router can access.
    """
    def _register_routes(self):
        @self.router.post(self.TOKEN_ENDPOINT, tags=[self.ROUTER_TAG])
        async def login_for_access_token(body: LoginData,
                                         background_tasks: BackgroundTasks,
                                         response: Response,
                                         request: Request,
                                         session_id: Annotated[Union[str, None], Cookie()] = None) -> security.Token:
            return await self._login_for_access_token_internal(body=body,
                                                               background_tasks=background_tasks,
                                                               request=request,
                                                               response=response,
                                                               session_id=session_id)

        @self.router.post(self.LOGOUT_ENDPOINT, tags=[self.ROUTER_TAG])
        async def logout(response: Response,
                         request: Request,
                         background_tasks: BackgroundTasks,
                         logout_data: LogoutData,
                         authorization: Annotated[Union[str, None], Cookie()] = None,
                         session_id: Annotated[Union[str, None], Cookie()] = None):
            return await self._logout_internal(response=response,
                                               request=request,
                                               background_tasks=background_tasks,
                                               therapist_id=logout_data.therapist_id,
                                               authorization=authorization,
                                               session_id=session_id)

        @self.router.post(self.THERAPISTS_ENDPOINT, tags=[self.ROUTER_TAG])
        async def add_new_therapist(body: TherapistInsertPayload,
                                    response: Response,
                                    request: Request,
                                    background_tasks: BackgroundTasks,
                                    datastore_access_token: Annotated[Union[str, None], Cookie()] = None,
                                    datastore_refresh_token: Annotated[Union[str, None], Cookie()] = None,
                                    authorization: Annotated[Union[str, None], Cookie()] = None,
                                    session_id: Annotated[Union[str, None], Cookie()] = None):
            return await self._add_new_therapist_internal(body=body,
                                                          response=response,
                                                          request=request,
                                                          background_tasks=background_tasks,
                                                          datastore_access_token=datastore_access_token,
                                                          datastore_refresh_token=datastore_refresh_token,
                                                          authorization=authorization,
                                                          session_id=session_id)

        @self.router.put(self.THERAPISTS_ENDPOINT, tags=[self.ROUTER_TAG])
        async def update_therapist_data(response: Response,
                                        request: Request,
                                        background_tasks: BackgroundTasks,
                                        body: TherapistUpdatePayload,
                                        datastore_access_token: Annotated[Union[str, None], Cookie()] = None,
                                        datastore_refresh_token: Annotated[Union[str, None], Cookie()] = None,
                                        authorization: Annotated[Union[str, None], Cookie()] = None,
                                        session_id: Annotated[Union[str, None], Cookie()] = None):
            return await self._update_therapist_data_internal(response=response,
                                                              request=request,
                                                              background_tasks=background_tasks,
                                                              body=body,
                                                              datastore_access_token=datastore_access_token,
                                                              datastore_refresh_token=datastore_refresh_token,
                                                              authorization=authorization,
                                                              session_id=session_id)

        @self.router.delete(self.THERAPISTS_ENDPOINT, tags=[self.ROUTER_TAG])
        async def delete_all_therapist_data(response: Response,
                                            request: Request,
                                            background_tasks: BackgroundTasks,
                                            therapist_id: str = None,
                                            datastore_access_token: Annotated[Union[str, None], Cookie()] = None,
                                            datastore_refresh_token: Annotated[Union[str, None], Cookie()] = None,
                                            authorization: Annotated[Union[str, None], Cookie()] = None,
                                            session_id: Annotated[Union[str, None], Cookie()] = None):
            return await self._delete_all_therapist_data_internal(response=response,
                                                                  request=request,
                                                                  background_tasks=background_tasks,
                                                                  therapist_id=therapist_id,
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
    async def _login_for_access_token_internal(self,
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
    Logs out the user.

    Arguments:
    response – the object to be used for constructing the final response.
    request – the incoming request object.
    background_tasks – object for scheduling concurrent tasks.
    therapist_id – the therapist id associated with the operation.
    authorization – the authorization cookie, if exists.
    session_id – the session_id cookie, if exists.
    """
    async def _logout_internal(self,
                               response: Response,
                               request: Request,
                               background_tasks: BackgroundTasks,
                               therapist_id: str,
                               authorization: Annotated[Union[str, None], Cookie()],
                               session_id: Annotated[Union[str, None], Cookie()]):
        if not self._auth_manager.access_token_is_valid(authorization):
            raise security.AUTH_TOKEN_EXPIRED_ERROR

        try:
            await self._auth_manager.refresh_session(user_id=therapist_id,
                                                     request=request,
                                                     response=response,
                                                     supabase_client_factory=self._supabase_client_factory)
        except Exception as e:
            status_code = general_utilities.extract_status_code(e, fallback=status.HTTP_400_BAD_REQUEST)
            raise HTTPException(status_code=status_code, detail=str(e))

        logger = Logger(supabase_client_factory=self._supabase_client_factory)
        post_api_method = logger.API_METHOD_POST
        logger.log_api_request(background_tasks=background_tasks,
                               session_id=session_id,
                               therapist_id=therapist_id,
                               method=post_api_method,
                               endpoint_name=self.LOGOUT_ENDPOINT,)

        self._auth_manager.logout(response)

        logger.log_api_response(background_tasks=background_tasks,
                                session_id=session_id,
                                therapist_id=therapist_id,
                                endpoint_name=self.LOGOUT_ENDPOINT,
                                http_status_code=status.HTTP_200_OK,
                                method=post_api_method)

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
    async def _add_new_therapist_internal(self,
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
            await self._auth_manager.refresh_session(user_id=body.id,
                                                     request=request,
                                                     response=response,
                                                     supabase_client_factory=self._supabase_client_factory)
        except Exception as e:
            status_code = general_utilities.extract_status_code(e, fallback=status.HTTP_400_BAD_REQUEST)
            raise HTTPException(status_code=status_code, detail=str(e))

        logger = Logger(supabase_client_factory=self._supabase_client_factory)
        post_api_method = logger.API_METHOD_POST
        logger.log_api_request(background_tasks=background_tasks,
                               session_id=session_id,
                               method=post_api_method,
                               therapist_id=body.id,
                               endpoint_name=self.THERAPISTS_ENDPOINT)

        try:
            assert body.signup_mechanism != SignupMechanism.UNDEFINED, '''Invalid parameter 'undefined' for signup_mechanism.'''
            assert body.gender != Gender.UNDEFINED, '''Invalid parameter 'undefined' for gender.'''
            assert datetime_handler.is_valid_date(date_input=body.birth_date,
                                                  incoming_date_format=datetime_handler.DATE_FORMAT), "Invalid date format. Date should not be in the future, and the expected format is mm-dd-yyyy"
            assert Language.get(body.language_preference).is_valid(), "Invalid language_preference parameter"

            supabase_client = self._supabase_client_factory.supabase_user_client(refresh_token=datastore_refresh_token,
                                                                                 access_token=datastore_access_token)
            background_tasks.add_task(supabase_client.insert,
                                      {
                                        "id": body.id,
                                        "first_name": body.first_name,
                                        "middle_name": body.middle_name,
                                        "last_name": body.last_name,
                                        "gender": body.gender.value,
                                        "birth_date": body.birth_date,
                                        "login_mechanism": body.signup_mechanism.value,
                                        "email": body.email,
                                        "language_preference": body.language_preference,
                                      },
                                      "therapists")

            # Create index in vector DB in a background task
            background_tasks.add_task(self._pinecone_client.create_index, body.id)

            logger.log_api_response(background_tasks=background_tasks,
                                    therapist_id=body.id,
                                    session_id=session_id,
                                    endpoint_name=self.THERAPISTS_ENDPOINT,
                                    http_status_code=status.HTTP_200_OK,
                                    method=post_api_method)

            return {"therapist_id": body.id}
        except Exception as e:
            description = str(e)
            status_code = general_utilities.extract_status_code(e, fallback=status.HTTP_400_BAD_REQUEST)
            logger.log_error(background_tasks=background_tasks,
                             session_id=session_id,
                             endpoint_name=self.THERAPISTS_ENDPOINT,
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
    async def _update_therapist_data_internal(self,
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
            await self._auth_manager.refresh_session(user_id=body.id,
                                                     request=request,
                                                     response=response,
                                                     supabase_client_factory=self._supabase_client_factory)
        except Exception as e:
            status_code = general_utilities.extract_status_code(e, fallback=status.HTTP_400_BAD_REQUEST)
            raise HTTPException(status_code=status_code, detail=str(e))

        logger = Logger(supabase_client_factory=self._supabase_client_factory)
        put_api_method = logger.API_METHOD_PUT
        logger.log_api_request(background_tasks=background_tasks,
                               session_id=session_id,
                               therapist_id=body.id,
                               method=put_api_method,
                               endpoint_name=self.THERAPISTS_ENDPOINT)
        try:
            body = body.dict(exclude_unset=True)
            assert 'gender' not in body or body['gender'] != Gender.UNDEFINED, '''Invalid parameter 'undefined' for gender.'''
            assert 'birth_date' not in body or datetime_handler.is_valid_date(date_input=body['birth_date'],
                                                                              incoming_date_format=datetime_handler.DATE_FORMAT), "Invalid date format. Date should not be in the future, and the expected format is mm-dd-yyyy"
            assert 'language_preference' not in body or Language.get(body['language_preference']).is_valid(), "Invalid language_preference parameter"

            supabase_client = self._supabase_client_factory.supabase_user_client(access_token=datastore_access_token,
                                                                                 refresh_token=datastore_refresh_token)
            payload = {}
            for key, value in body.items():
                if key == 'id':
                    continue
                if isinstance(value, Enum):
                    value = value.value
                payload[key] = value

            supabase_client.update(table_name="therapists",
                                   payload=payload,
                                   filters={
                                       'id': body['id']
                                   })

            logger.log_api_response(background_tasks=background_tasks,
                                    therapist_id=body['id'],
                                    session_id=session_id,
                                    endpoint_name=self.THERAPISTS_ENDPOINT,
                                    http_status_code=status.HTTP_200_OK,
                                    method=put_api_method)
            return {}
        except Exception as e:
            description = str(e)
            status_code = general_utilities.extract_status_code(e, fallback=status.HTTP_400_BAD_REQUEST)
            logger.log_error(background_tasks=background_tasks,
                             session_id=session_id,
                             endpoint_name=self.THERAPISTS_ENDPOINT,
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
    therapist_id – the id associated with the therapist data to be deleted.
    datastore_access_token – the datastore access token.
    datastore_refresh_token – the datastore refresh token.
    authorization – the authorization cookie, if exists.
    session_id – the session_id cookie, if exists.
    """
    async def _delete_all_therapist_data_internal(self,
                                                  background_tasks: BackgroundTasks,
                                                  response: Response,
                                                  request: Request,
                                                  therapist_id: str,
                                                  datastore_access_token: Annotated[Union[str, None], Cookie()],
                                                  datastore_refresh_token: Annotated[Union[str, None], Cookie()],
                                                  authorization: Annotated[Union[str, None], Cookie()],
                                                  session_id: Annotated[Union[str, None], Cookie()]):
        if not self._auth_manager.access_token_is_valid(authorization):
            raise security.AUTH_TOKEN_EXPIRED_ERROR

        if datastore_access_token is None or datastore_refresh_token is None:
            raise security.DATASTORE_TOKENS_ERROR

        if len(therapist_id or '') == 0:
            raise HTTPException(detail="Invalid or empty therapist_id to be deleted", status_code=status.HTTP_400_BAD_REQUEST)

        try:
            await self._auth_manager.refresh_session(user_id=therapist_id,
                                                     response=response,
                                                     request=request,
                                                     supabase_client_factory=self._supabase_client_factory)
        except Exception as e:
            status_code = general_utilities.extract_status_code(e, fallback=status.HTTP_400_BAD_REQUEST)
            raise HTTPException(status_code=status_code, detail=str(e))

        logger = Logger(supabase_client_factory=self._supabase_client_factory)
        delete_api_method = logger.API_METHOD_DELETE
        logger.log_api_request(background_tasks=background_tasks,
                               session_id=session_id,
                               therapist_id=therapist_id,
                               method=delete_api_method,
                               endpoint_name=self.THERAPISTS_ENDPOINT)
        try:
            supabase_client = self._supabase_client_factory.supabase_user_client(access_token=datastore_access_token,
                                                                                 refresh_token=datastore_refresh_token)

            # Delete therapist and all their patients (through cascading)
            delete_response = supabase_client.delete(table_name="therapists",
                                                     filters={
                                                         'id': therapist_id
                                                     })
            assert len(delete_response.dict()['data']) > 0, "No therapist found with the incoming id"

            # Remove the active session and clear Auth data from client storage.
            supabase_client.sign_out()

            # Delete vectors associated with therapist's patients
            self._assistant_manager.delete_all_sessions_for_therapist(id=therapist_id,
                                                                      pinecone_client=self._pinecone_client)

            # Delete auth and session cookies
            self._auth_manager.logout(response)

            logger.log_account_deletion(background_tasks=background_tasks,
                                        therapist_id=therapist_id)
            logger.log_api_response(background_tasks=background_tasks,
                                    therapist_id=therapist_id,
                                    session_id=session_id,
                                    endpoint_name=self.THERAPISTS_ENDPOINT,
                                    http_status_code=status.HTTP_200_OK,
                                    method=delete_api_method)
            return {}
        except Exception as e:
            description = str(e)
            status_code = general_utilities.extract_status_code(e, fallback=status.HTTP_400_BAD_REQUEST)
            logger.log_error(background_tasks=background_tasks,
                             session_id=session_id,
                             endpoint_name=self.THERAPISTS_ENDPOINT,
                             error_code=status_code,
                             description=description,
                             method=delete_api_method)
            raise HTTPException(status_code=status_code,
                                detail=description)
