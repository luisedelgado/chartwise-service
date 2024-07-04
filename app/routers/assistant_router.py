from fastapi import (APIRouter,
                     Cookie,
                     HTTPException,
                     Response,
                     status,)
from supabase import Client
from typing import Annotated, Union

from ..api.assistant_base_class import AssistantManagerBaseClass
from ..api.auth_base_class import AuthManagerBaseClass
from ..internal import logging, model, security
from ..internal.utilities import datetime_handler, general_utilities

class AssistantRouter:

    SESSIONS_ENDPOINT = "/v1/sessions"
    QUERIES_ENDPOINT = "/v1/queries"
    GREETINGS_ENDPOINT = "/v1/greetings"
    PRESESSION_TRAY_ENDPOINT = "/v1/pre-session"
    QUESTION_SUGGESTIONS_ENDPOINT = "/v1/question-suggestions"
    PATIENTS_ENDPOINT = "/patients"
    ROUTER_TAG = "assistant"

    def __init__(self,
                 environment: str,
                 auth_manager: AuthManagerBaseClass,
                 assistant_manager: AssistantManagerBaseClass):
        self._environment = environment
        self._auth_manager = auth_manager
        self._assistant_manager = assistant_manager
        self.router = APIRouter()
        self._register_routes()

    """
    Registers the set of routes that the class' router can access.
    """
    def _register_routes(self):
        @self.router.post(self.SESSIONS_ENDPOINT, tags=[self.ROUTER_TAG])
        async def insert_new_session(body: model.SessionNotesInsert,
                                     response: Response,
                                     authorization: Annotated[Union[str, None], Cookie()] = None,
                                     current_session_id: Annotated[Union[str, None], Cookie()] = None):
            return await self._insert_new_session_internal(body=body,
                                                           response=response,
                                                           authorization=authorization,
                                                           current_session_id=current_session_id)

        @self.router.put(self.SESSIONS_ENDPOINT, tags=[self.ROUTER_TAG])
        async def update_session(body: model.SessionNotesUpdate,
                                 response: Response,
                                 authorization: Annotated[Union[str, None], Cookie()] = None,
                                 current_session_id: Annotated[Union[str, None], Cookie()] = None):
            return await self._update_session_internal(body=body,
                                                       response=response,
                                                       authorization=authorization,
                                                       current_session_id=current_session_id)

        @self.router.delete(self.SESSIONS_ENDPOINT, tags=[self.ROUTER_TAG])
        async def delete_session(body: model.SessionNotesDelete,
                                 response: Response,
                                 authorization: Annotated[Union[str, None], Cookie()] = None,
                                 current_session_id: Annotated[Union[str, None], Cookie()] = None):
            return await self._delete_session_internal(body=body,
                                                       response=response,
                                                       authorization=authorization,
                                                       current_session_id=current_session_id)

        @self.router.post(self.QUERIES_ENDPOINT, tags=[self.ROUTER_TAG])
        async def execute_assistant_query(query: model.AssistantQuery,
                                          response: Response,
                                          authorization: Annotated[Union[str, None], Cookie()] = None,
                                          current_session_id: Annotated[Union[str, None], Cookie()] = None):
            return await self._execute_assistant_query_internal(query=query,
                                                                response=response,
                                                                authorization=authorization,
                                                                current_session_id=current_session_id)

        @self.router.post(self.GREETINGS_ENDPOINT, tags=[self.ROUTER_TAG])
        async def fetch_greeting(response: Response,
                                 body: model.Greeting,
                                 authorization: Annotated[Union[str, None], Cookie()] = None,
                                 current_session_id: Annotated[Union[str, None], Cookie()] = None):
            return await self._fetch_greeting_internal(response=response,
                                                       body=body,
                                                       authorization=authorization,
                                                       current_session_id=current_session_id)

        @self.router.post(self.PRESESSION_TRAY_ENDPOINT, tags=[self.ROUTER_TAG])
        async def fetch_presession_tray(response: Response,
                                        body: model.SessionHistorySummary,
                                        authorization: Annotated[Union[str, None], Cookie()] = None,
                                        current_session_id: Annotated[Union[str, None], Cookie()] = None):
            return await self._fetch_presession_tray_internal(response=response,
                                                              body=body,
                                                              authorization=authorization,
                                                              current_session_id=current_session_id)

        @self.router.post(self.QUESTION_SUGGESTIONS_ENDPOINT, tags=[self.ROUTER_TAG])
        async def fetch_question_suggestions(response: Response,
                                             body: model.QuestionSuggestionsParams,
                                             authorization: Annotated[Union[str, None], Cookie()] = None,
                                             current_session_id: Annotated[Union[str, None], Cookie()] = None):
            return await self._fetch_question_suggestions_internal(response=response,
                                                                   body=body,
                                                                   authorization=authorization,
                                                                   current_session_id=current_session_id)

        @self.router.post(self.PATIENTS_ENDPOINT, tags=[self.ROUTER_TAG])
        async def add_patient(response: Response,
                              body: model.PatientInsertPayload,
                              authorization: Annotated[Union[str, None], Cookie()] = None,
                              current_session_id: Annotated[Union[str, None], Cookie()] = None):
            return await self._add_patient_internal(response=response,
                                                    body=body,
                                                    authorization=authorization,
                                                    current_session_id=current_session_id)

        @self.router.put(self.PATIENTS_ENDPOINT, tags=[self.ROUTER_TAG])
        async def update_patient(response: Response,
                              body: model.PatientUpdatePayload,
                              authorization: Annotated[Union[str, None], Cookie()] = None,
                              current_session_id: Annotated[Union[str, None], Cookie()] = None):
            return await self._update_patient_internal(response=response,
                                                       body=body,
                                                       authorization=authorization,
                                                       current_session_id=current_session_id)

        @self.router.delete(self.PATIENTS_ENDPOINT, tags=[self.ROUTER_TAG])
        async def delete_patient(response: Response,
                                 body: model.PatientDeletePayload,
                                 authorization: Annotated[Union[str, None], Cookie()] = None,
                                 current_session_id: Annotated[Union[str, None], Cookie()] = None):
            return await self._delete_patient_internal(response=response,
                                                       body=body,
                                                       authorization=authorization,
                                                       current_session_id=current_session_id)

    """
    Stores a new session report.

    Arguments:
    body – the incoming request body.
    response – the response model with which to create the final response.
    authorization – the authorization cookie, if exists.
    current_session_id – the session_id cookie, if exists.
    """
    async def _insert_new_session_internal(self,
                                           body: model.SessionNotesInsert,
                                           response: Response,
                                           authorization: Annotated[Union[str, None], Cookie()],
                                           current_session_id: Annotated[Union[str, None], Cookie()]):
        if not self._auth_manager.access_token_is_valid(authorization):
            raise security.TOKEN_EXPIRED_ERROR

        try:
            current_entity: security.User = await self._auth_manager.get_current_auth_entity(authorization)
            session_refresh_data: model.SessionRefreshData = await self._auth_manager.refresh_session(user=current_entity,
                                                                                                      response=response,
                                                                                                      session_id=current_session_id)
            session_id = session_refresh_data._session_id
        except Exception as e:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))

        logging.log_api_request(session_id=session_id,
                                patient_id=body.patient_id,
                                therapist_id=body.therapist_id,
                                endpoint_name=self.SESSIONS_ENDPOINT,
                                method=logging.API_METHOD_POST,
                                auth_entity=current_entity.username)

        try:
            assert datetime_handler.is_valid_date(body.date), "Invalid date. The expected format is mm-dd-yyyy"

            self._assistant_manager.process_new_session_data(auth_manager=self._auth_manager, body=body)

            logging.log_api_response(session_id=session_id,
                                    therapist_id=body.therapist_id,
                                    patient_id=body.patient_id,
                                    endpoint_name=self.SESSIONS_ENDPOINT,
                                    http_status_code=status.HTTP_200_OK,
                                    method=logging.API_METHOD_POST)

            return {}
        except Exception as e:
            description = str(e)
            status_code = status.HTTP_400_BAD_REQUEST if type(e) is not HTTPException else e.status_code
            logging.log_error(session_id=session_id,
                            therapist_id=body.therapist_id,
                            patient_id=body.patient_id,
                            endpoint_name=self.SESSIONS_ENDPOINT,
                            error_code=status_code,
                            description=description,
                            method=logging.API_METHOD_POST)
            raise HTTPException(status_code=status_code,
                                detail=description)

    """
    Updates a session report.

    Arguments:
    body – the incoming request body.
    response – the response model with which to create the final response.
    authorization – the authorization cookie, if exists.
    current_session_id – the session_id cookie, if exists.
    """
    async def _update_session_internal(self,
                                       body: model.SessionNotesUpdate,
                                       response: Response,
                                       authorization: Annotated[Union[str, None], Cookie()],
                                       current_session_id: Annotated[Union[str, None], Cookie()]):
        if not self._auth_manager.access_token_is_valid(authorization):
            raise security.TOKEN_EXPIRED_ERROR

        try:
            current_entity: security.User = await self._auth_manager.get_current_auth_entity(authorization)
            session_refresh_data: model.SessionRefreshData = await self._auth_manager.refresh_session(user=current_entity,
                                                                                                      response=response,
                                                                                                      session_id=current_session_id)
            session_id = session_refresh_data._session_id
        except Exception as e:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))

        logging.log_api_request(session_id=session_id,
                                patient_id=body.patient_id,
                                therapist_id=body.therapist_id,
                                endpoint_name=self.SESSIONS_ENDPOINT,
                                method=logging.API_METHOD_PUT,
                                auth_entity=current_entity.username)

        try:
            self._assistant_manager.update_session(auth_manager=self._auth_manager, body=body)

            logging.log_api_response(session_id=session_id,
                                    therapist_id=body.therapist_id,
                                    patient_id=body.patient_id,
                                    endpoint_name=self.SESSIONS_ENDPOINT,
                                    http_status_code=status.HTTP_200_OK,
                                    method=logging.API_METHOD_PUT)

            return {}
        except Exception as e:
            description = str(e)
            status_code = status.HTTP_400_BAD_REQUEST if type(e) is not HTTPException else e.status_code
            logging.log_error(session_id=session_id,
                            therapist_id=body.therapist_id,
                            patient_id=body.patient_id,
                            endpoint_name=self.SESSIONS_ENDPOINT,
                            error_code=status_code,
                            description=description,
                            method=logging.API_METHOD_PUT)
            raise HTTPException(status_code=status_code,
                                detail=description)

    """
    Deletes a session report.

    Arguments:
    body – the incoming request body.
    response – the response model with which to create the final response.
    authorization – the authorization cookie, if exists.
    current_session_id – the session_id cookie, if exists.
    """
    async def _delete_session_internal(self,
                                       body: model.SessionNotesDelete,
                                       response: Response,
                                       authorization: Annotated[Union[str, None], Cookie()],
                                       current_session_id: Annotated[Union[str, None], Cookie()]):
        if not self._auth_manager.access_token_is_valid(authorization):
            raise security.TOKEN_EXPIRED_ERROR

        try:
            current_entity: security.User = await self._auth_manager.get_current_auth_entity(authorization)
            session_refresh_data: model.SessionRefreshData = await self._auth_manager.refresh_session(user=current_entity,
                                                                                                      response=response,
                                                                                                      session_id=current_session_id)
            session_id = session_refresh_data._session_id
        except Exception as e:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))

        logging.log_api_request(session_id=session_id,
                                patient_id=body.patient_id,
                                therapist_id=body.therapist_id,
                                endpoint_name=self.SESSIONS_ENDPOINT,
                                method=logging.API_METHOD_DELETE,
                                auth_entity=current_entity.username)

        try:
            self._assistant_manager.delete_session(auth_manager=self._auth_manager, body=body)

            logging.log_api_response(session_id=session_id,
                                    therapist_id=body.therapist_id,
                                    patient_id=body.patient_id,
                                    endpoint_name=self.SESSIONS_ENDPOINT,
                                    http_status_code=status.HTTP_200_OK,
                                    method=logging.API_METHOD_DELETE)

            return {}
        except Exception as e:
            description = str(e)
            status_code = status.HTTP_400_BAD_REQUEST if type(e) is not HTTPException else e.status_code
            logging.log_error(session_id=session_id,
                            therapist_id=body.therapist_id,
                            patient_id=body.patient_id,
                            endpoint_name=self.SESSIONS_ENDPOINT,
                            error_code=status_code,
                            description=description,
                            method=logging.API_METHOD_DELETE)
            raise HTTPException(status_code=status_code,
                                detail=description)

    """
    Executes a query to our assistant system.
    Returns the query response.

    Arguments:
    query – the query that will be executed.
    response – the response model with which to create the final response.
    authorization – the authorization cookie, if exists.
    current_session_id – the session_id cookie, if exists.
    """
    async def _execute_assistant_query_internal(self,
                                                query: model.AssistantQuery,
                                                response: Response,
                                                authorization: Annotated[Union[str, None], Cookie()],
                                                current_session_id: Annotated[Union[str, None], Cookie()]):
        if not self._auth_manager.access_token_is_valid(authorization):
            raise security.TOKEN_EXPIRED_ERROR

        try:
            current_entity: security.User = await self._auth_manager.get_current_auth_entity(authorization)
            session_refresh_data: model.SessionRefreshData = await self._auth_manager.refresh_session(user=current_entity,
                                                                                                      response=response,
                                                                                                      session_id=current_session_id)
            session_id = session_refresh_data._session_id
        except Exception as e:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))

        logging.log_api_request(session_id=session_id,
                                therapist_id=query.therapist_id,
                                patient_id=query.patient_id,
                                endpoint_name=self.QUERIES_ENDPOINT,
                                method=logging.API_METHOD_POST,
                                auth_entity=current_entity.username)

        try:
            response = self._assistant_manager.query_session(auth_manager=self._auth_manager,
                                                             query=query,
                                                             session_id=session_id,
                                                             api_method=logging.API_METHOD_POST,
                                                             endpoint_name=self.QUERIES_ENDPOINT,
                                                             environment=self._environment,
                                                             auth_entity=current_entity.username)

            logging.log_api_response(session_id=session_id,
                            therapist_id=query.therapist_id,
                            patient_id=query.patient_id,
                            endpoint_name=self.QUERIES_ENDPOINT,
                            http_status_code=status.HTTP_200_OK,
                            method=logging.API_METHOD_POST)
            return response
        except Exception as e:
            description = str(e)
            status_code = status.HTTP_400_BAD_REQUEST if type(e) is not HTTPException else e.status_code
            logging.log_error(session_id=session_id,
                            patient_id=query.patient_id,
                            endpoint_name=self.QUERIES_ENDPOINT,
                            error_code=status_code,
                            description=description,
                            method=logging.API_METHOD_POST)
            raise HTTPException(status_code=status_code,
                                detail=description)

    """
    Returns a new greeting to the user.

    Arguments:
    response – the response model used for the final response that will be returned.
    body – the json body associated with the request.
    authorization – the authorization cookie, if exists.
    current_session_id – the session_id cookie, if exists.
    """
    async def _fetch_greeting_internal(self,
                                       response: Response,
                                       body: model.Greeting,
                                       authorization: Annotated[Union[str, None], Cookie()],
                                       current_session_id: Annotated[Union[str, None], Cookie()]):
        if not self._auth_manager.access_token_is_valid(authorization):
            raise security.TOKEN_EXPIRED_ERROR

        try:
            current_entity: security.User = await self._auth_manager.get_current_auth_entity(authorization)
            session_refresh_data: model.SessionRefreshData = await self._auth_manager.refresh_session(user=current_entity,
                                                                                                      response=response,
                                                                                                      session_id=current_session_id)
            session_id = session_refresh_data._session_id
        except Exception as e:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))

        logs_description = ''.join(['tz_identifier:', body.client_tz_identifier])
        logging.log_api_request(session_id=session_id,
                                method=logging.API_METHOD_POST,
                                therapist_id=body.therapist_id,
                                endpoint_name=self.GREETINGS_ENDPOINT,
                                auth_entity=current_entity.username,
                                description=logs_description)

        try:
            assert general_utilities.is_valid_timezone_identifier(body.client_tz_identifier), "Invalid timezone identifier parameter"

            result = self._assistant_manager.fetch_todays_greeting(body=body,
                                                                   session_id=session_id,
                                                                   endpoint_name=self.GREETINGS_ENDPOINT,
                                                                   api_method=logging.API_METHOD_POST,
                                                                   environment=self._environment,
                                                                   auth_manager=self._auth_manager,
                                                                   auth_entity=current_entity.username)

            logging.log_api_response(session_id=session_id,
                                    endpoint_name=self.GREETINGS_ENDPOINT,
                                    therapist_id=body.therapist_id,
                                    http_status_code=status.HTTP_200_OK,
                                    description=logs_description,
                                    method=logging.API_METHOD_POST)

            return {"message": result}
        except Exception as e:
            description = str(e)
            status_code = status.HTTP_400_BAD_REQUEST if type(e) is not HTTPException else e.status_code
            logging.log_error(session_id=session_id,
                            endpoint_name=self.GREETINGS_ENDPOINT,
                            error_code=status_code,
                            description=description,
                            method=logging.API_METHOD_POST)
            raise HTTPException(status_code=status_code,
                                detail=description)

    """
    Returns a pre-session tray.

    Arguments:
    response – the response model used for the final response that will be returned.
    body – the json body associated with the request.
    authorization – the authorization cookie, if exists.
    current_session_id – the session_id cookie, if exists.
    """
    async def _fetch_presession_tray_internal(self,
                                              response: Response,
                                              body: model.SessionHistorySummary,
                                              authorization: Annotated[Union[str, None], Cookie()],
                                              current_session_id: Annotated[Union[str, None], Cookie()]):
        if not self._auth_manager.access_token_is_valid(authorization):
            raise security.TOKEN_EXPIRED_ERROR

        try:
            current_entity: security.User = await self._auth_manager.get_current_auth_entity(authorization)
            session_refresh_data: model.SessionRefreshData = await self._auth_manager.refresh_session(user=current_entity,
                                                                                                      response=response,
                                                                                                      session_id=current_session_id)
            session_id = session_refresh_data._session_id
        except Exception as e:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))

        logging.log_api_request(session_id=session_id,
                                method=logging.API_METHOD_POST,
                                therapist_id=body.therapist_id,
                                patient_id=body.patient_id,
                                endpoint_name=self.PRESESSION_TRAY_ENDPOINT,
                                auth_entity=current_entity.username)

        try:
            response = self._assistant_manager.create_patient_summary(body=body,
                                                                      environment=self._environment,
                                                                      session_id=session_id,
                                                                      endpoint_name=self.PRESESSION_TRAY_ENDPOINT,
                                                                      api_method=logging.API_METHOD_POST,
                                                                      auth_manager=self._auth_manager,
                                                                      auth_entity=current_entity.username)

            logging.log_api_response(session_id=session_id,
                                     endpoint_name=self.PRESESSION_TRAY_ENDPOINT,
                                     therapist_id=body.therapist_id,
                                     patient_id=body.patient_id,
                                     http_status_code=status.HTTP_200_OK,
                                     method=logging.API_METHOD_POST)

            return {"summary": response}
        except Exception as e:
            description = str(e)
            status_code = status.HTTP_400_BAD_REQUEST if type(e) is not HTTPException else e.status_code
            logging.log_error(session_id=session_id,
                            endpoint_name=self.PRESESSION_TRAY_ENDPOINT,
                            error_code=status_code,
                            description=description,
                            method=logging.API_METHOD_POST)
            raise HTTPException(status_code=status_code,
                                detail=description)

    async def _fetch_question_suggestions_internal(self,
                                                   response: Response,
                                                   body: model.QuestionSuggestionsParams,
                                                   authorization: Annotated[Union[str, None], Cookie()],
                                                   current_session_id: Annotated[Union[str, None], Cookie()]):
        if not self._auth_manager.access_token_is_valid(authorization):
            raise security.TOKEN_EXPIRED_ERROR

        try:
            current_entity: security.User = await self._auth_manager.get_current_auth_entity(authorization)
            session_refresh_data: model.SessionRefreshData = await self._auth_manager.refresh_session(user=current_entity,
                                                                                                      response=response,
                                                                                                      session_id=current_session_id)
            session_id = session_refresh_data._session_id
        except Exception as e:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))

        logging.log_api_request(session_id=session_id,
                                method=logging.API_METHOD_POST,
                                therapist_id=body.therapist_id,
                                patient_id=body.patient_id,
                                endpoint_name=self.QUESTION_SUGGESTIONS_ENDPOINT,
                                auth_entity=current_entity.username)

        try:
            json_questions = self._assistant_manager.fetch_question_suggestions(body=body,
                                                                                auth_manager=self._auth_manager,
                                                                                environment=self._environment,
                                                                                session_id=session_id,
                                                                                endpoint_name=self.QUESTION_SUGGESTIONS_ENDPOINT,
                                                                                api_method=logging.API_METHOD_POST,
                                                                                auth_entity=current_entity.username)

            logging.log_api_response(session_id=session_id,
                                     endpoint_name=self.QUESTION_SUGGESTIONS_ENDPOINT,
                                     therapist_id=body.therapist_id,
                                     patient_id=body.patient_id,
                                     http_status_code=status.HTTP_200_OK,
                                     method=logging.API_METHOD_POST)

            return json_questions
        except Exception as e:
            description = str(e)
            status_code = status.HTTP_400_BAD_REQUEST if type(e) is not HTTPException else e.status_code
            logging.log_error(session_id=session_id,
                            endpoint_name=self.QUESTION_SUGGESTIONS_ENDPOINT,
                            error_code=status_code,
                            description=description,
                            method=logging.API_METHOD_POST)
            raise HTTPException(status_code=status_code,
                                detail=description)

    """
    Adds a patient.

    Arguments:
    response – the object to be used for constructing the final response.
    body – the body associated with the request.
    authorization – the authorization cookie, if exists.
    current_session_id – the session_id cookie, if exists.
    """
    async def _add_patient_internal(self,
                                    response: Response,
                                    body: model.PatientInsertPayload,
                                    authorization: Annotated[Union[str, None], Cookie()],
                                    current_session_id: Annotated[Union[str, None], Cookie()]):
        if not self._auth_manager.access_token_is_valid(authorization):
            raise security.TOKEN_EXPIRED_ERROR

        try:
            current_entity: security.User = await self._auth_manager.get_current_auth_entity(authorization)
            session_refresh_data: model.SessionRefreshData = await self._auth_manager.refresh_session(user=current_entity,
                                                                                                      response=response,
                                                                                                      session_id=current_session_id)
            session_id = session_refresh_data._session_id
        except Exception as e:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))

        logging.log_api_request(session_id=session_id,
                                method=logging.API_METHOD_POST,
                                endpoint_name=self.PATIENTS_ENDPOINT,
                                therapist_id=body.therapist_id,
                                auth_entity=current_entity.username)

        try:
            assert datetime_handler.is_valid_date(body.birth_date), "Invalid date. The expected format is mm-dd-yyyy"

            gender_to_lower = body.gender.lower()
            assert general_utilities.is_valid_gender_value(gender_to_lower), "Invalid format for 'gender' param. Expected values are: ['male', 'female', 'other', 'rather_not_say']"

            datastore_client: Client = self._auth_manager.datastore_user_instance(body.datastore_access_token,
                                                                                  body.datastore_refresh_token)
            datastore_client.table('patients').insert({
                "first_name": body.first_name,
                "middle_name": body.middle_name,
                "last_name": body.last_name,
                "birth_date": body.birth_date,
                "email": body.email,
                "gender": gender_to_lower,
                "phone_number": body.phone_number,
                "consentment_channel": body.consentment_channel,
            }).execute()

            logging.log_api_response(session_id=session_id,
                                     method=logging.API_METHOD_POST,
                                     endpoint_name=self.PATIENTS_ENDPOINT,
                                     therapist_id=body.therapist_id,
                                     auth_entity=current_entity.username,
                                     http_status_code=status.HTTP_200_OK)

            return {}
        except Exception as e:
            description = str(e)
            status_code = status.HTTP_417_EXPECTATION_FAILED
            logging.log_error(session_id=session_id,
                              endpoint_name=self.PATIENTS_ENDPOINT,
                              error_code=status_code,
                              therapist_id=body.therapist_id,
                              description=description,
                              method=logging.API_METHOD_POST)
            raise HTTPException(status_code=status_code,
                                detail=description)

    """
    Updates a patient.

    Arguments:
    response – the object to be used for constructing the final response.
    body – the body associated with the request.
    authorization – the authorization cookie, if exists.
    current_session_id – the session_id cookie, if exists.
    """
    async def _update_patient_internal(self,
                                       response: Response,
                                       body: model.PatientUpdatePayload,
                                       authorization: Annotated[Union[str, None], Cookie()],
                                       current_session_id: Annotated[Union[str, None], Cookie()]):
        if not self._auth_manager.access_token_is_valid(authorization):
            raise security.TOKEN_EXPIRED_ERROR

        try:
            current_entity: security.User = await self._auth_manager.get_current_auth_entity(authorization)
            session_refresh_data: model.SessionRefreshData = await self._auth_manager.refresh_session(user=current_entity,
                                                                                                      response=response,
                                                                                                      session_id=current_session_id)
            session_id = session_refresh_data._session_id
        except Exception as e:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))

        logging.log_api_request(session_id=session_id,
                                method=logging.API_METHOD_PUT,
                                endpoint_name=self.PATIENTS_ENDPOINT,
                                therapist_id=body.therapist_id,
                                auth_entity=current_entity.username,
                                patient_id=body.id)

        try:
            assert datetime_handler.is_valid_date(body.birth_date), "Invalid date. The expected format is mm-dd-yyyy"

            gender_to_lower = body.gender.lower()
            assert general_utilities.is_valid_gender_value(gender_to_lower), "Invalid format for 'gender' param. Expected values are: ['male', 'female', 'other', 'rather_not_say']"

            datastore_client: Client = self._auth_manager.datastore_user_instance(body.datastore_access_token,
                                                                                  body.datastore_refresh_token)
            datastore_client.table('patients').update({
                "first_name": body.first_name,
                "middle_name": body.middle_name,
                "last_name": body.last_name,
                "birth_date": body.birth_date,
                "email": body.email,
                "gender": gender_to_lower,
                "phone_number": body.phone_number,
                "consentment_channel": body.consentment_channel,
            }).eq('id', body.id).execute()

            logging.log_api_response(session_id=session_id,
                                     method=logging.API_METHOD_PUT,
                                     endpoint_name=self.PATIENTS_ENDPOINT,
                                     therapist_id=body.therapist_id,
                                     patient_id=body.id,
                                     auth_entity=current_entity.username,
                                     http_status_code=status.HTTP_200_OK)
            return {}
        except Exception as e:
            description = str(e)
            status_code = status.HTTP_400_BAD_REQUEST
            logging.log_error(session_id=session_id,
                              endpoint_name=self.PATIENTS_ENDPOINT,
                              error_code=status_code,
                              therapist_id=body.therapist_id,
                              patient_id=body.id,
                              description=description,
                              method=logging.API_METHOD_PUT)
            raise HTTPException(status_code=status_code,
                                detail=description)

    """
    Deletes a patient.

    Arguments:
    response – the object to be used for constructing the final response.
    body – the body associated with the request.
    authorization – the authorization cookie, if exists.
    current_session_id – the session_id cookie, if exists.
    """
    async def _delete_patient_internal(self,
                                       response: Response,
                                       body: model.PatientDeletePayload,
                                       authorization: Annotated[Union[str, None], Cookie()],
                                       current_session_id: Annotated[Union[str, None], Cookie()]):
        if not self._auth_manager.access_token_is_valid(authorization):
            raise security.TOKEN_EXPIRED_ERROR

        try:
            current_entity: security.User = await self._auth_manager.get_current_auth_entity(authorization)
            session_refresh_data: model.SessionRefreshData = await self._auth_manager.refresh_session(user=current_entity,
                                                                                                      response=response,
                                                                                                      session_id=current_session_id)
            session_id = session_refresh_data._session_id
        except Exception as e:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))

        logging.log_api_request(session_id=session_id,
                                method=logging.API_METHOD_DELETE,
                                endpoint_name=self.PATIENTS_ENDPOINT,
                                therapist_id=body.therapist_id,
                                patient_id=body.id,
                                auth_entity=current_entity.username)

        try:
            datastore_client: Client = self._auth_manager.datastore_user_instance(body.datastore_access_token,
                                                                                  body.datastore_refresh_token)
            datastore_client.table('patients').delete().eq('id', body.id).execute()
            self._assistant_manager.delete_all_sessions_for_patient(auth_manager=self._auth_manager,
                                                                    body=body)

            logging.log_api_response(session_id=session_id,
                                     method=logging.API_METHOD_DELETE,
                                     endpoint_name=self.PATIENTS_ENDPOINT,
                                     therapist_id=body.therapist_id,
                                     patient_id=body.id,
                                     auth_entity=current_entity.username,
                                     http_status_code=status.HTTP_200_OK)
            return {}
        except Exception as e:
            description = str(e)
            status_code = status.HTTP_400_BAD_REQUEST
            logging.log_error(session_id=session_id,
                              endpoint_name=self.PATIENTS_ENDPOINT,
                              error_code=status_code,
                              therapist_id=body.therapist_id,
                              patient_id=body.id,
                              description=description,
                              method=logging.API_METHOD_DELETE)
            raise HTTPException(status_code=status_code,
                                detail=description)
