from datetime import datetime

from fastapi import (APIRouter,
                     Cookie,
                     Form,
                     HTTPException,
                     Response,
                     status,)
from langcodes import Language
from typing import Annotated, Union

from ..internal import logging, model, security
from ..internal.utilities import datetime_handler
from ..managers.manager_factory import ManagerFactory

GREETINGS_ENDPOINT = "/v1/greetings"
SESSIONS_ENDPOINT = "/v1/sessions"
QUERIES_ENDPOINT = "/v1/queries"
PRESESSION_TRAY_ENDPOINT = "/v1/pre-session"

router = APIRouter()
environment = ""

"""
Stores a new session report.

Arguments:
body – the incoming request body.
response – the response model with which to create the final response.
authorization – the authorization cookie, if exists.
current_session_id – the session_id cookie, if exists.
"""
@router.post(SESSIONS_ENDPOINT, tags=["assistant"])
async def insert_new_session(body: model.SessionNotesInsert,
                             response: Response,
                             authorization: Annotated[Union[str, None], Cookie()] = None,
                             current_session_id: Annotated[Union[str, None], Cookie()] = None):
    if not security.access_token_is_valid(authorization):
        raise security.TOKEN_EXPIRED_ERROR

    try:
        current_entity: security.User = await security.get_current_auth_entity(authorization)
        session_refresh_data: model.SessionRefreshData = await security.refresh_session(user=current_entity,
                                                                                        response=response,
                                                                                        session_id=current_session_id)
        session_id = session_refresh_data._session_id
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))

    logging.log_api_request(session_id=session_id,
                            patient_id=body.patient_id,
                            therapist_id=body.therapist_id,
                            endpoint_name=SESSIONS_ENDPOINT,
                            method=logging.API_METHOD_POST,
                            auth_entity=current_entity.username)

    try:
        assert datetime_handler.is_valid_date(body.date), "Invalid date. The expected format is mm-dd-yyyy"

        auth_manager = ManagerFactory.create_auth_manager(environment)
        assistant_manager = ManagerFactory.create_assistant_manager(environment)
        assistant_manager.process_new_session_data(auth_manager=auth_manager, body=body)

        logging.log_api_response(session_id=session_id,
                                therapist_id=body.therapist_id,
                                patient_id=body.patient_id,
                                endpoint_name=SESSIONS_ENDPOINT,
                                http_status_code=status.HTTP_200_OK,
                                method=logging.API_METHOD_POST)

        return {}
    except Exception as e:
        description = str(e)
        status_code = status.HTTP_400_BAD_REQUEST if type(e) is not HTTPException else e.status_code
        logging.log_error(session_id=session_id,
                          therapist_id=body.therapist_id,
                          patient_id=body.patient_id,
                          endpoint_name=SESSIONS_ENDPOINT,
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
@router.put(SESSIONS_ENDPOINT, tags=["assistant"])
async def update_session(body: model.SessionNotesUpdate,
                         response: Response,
                         authorization: Annotated[Union[str, None], Cookie()] = None,
                         current_session_id: Annotated[Union[str, None], Cookie()] = None):
    if not security.access_token_is_valid(authorization):
        raise security.TOKEN_EXPIRED_ERROR

    try:
        current_entity: security.User = await security.get_current_auth_entity(authorization)
        session_refresh_data: model.SessionRefreshData = await security.refresh_session(user=current_entity,
                                                                                        response=response,
                                                                                        session_id=current_session_id)
        session_id = session_refresh_data._session_id
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))

    logging.log_api_request(session_id=session_id,
                            patient_id=body.patient_id,
                            therapist_id=body.therapist_id,
                            endpoint_name=SESSIONS_ENDPOINT,
                            method=logging.API_METHOD_PUT,
                            auth_entity=current_entity.username)

    try:
        auth_manager = ManagerFactory.create_auth_manager(environment)
        assistant_manager = ManagerFactory.create_assistant_manager(environment)
        assistant_manager.update_session(auth_manager=auth_manager, body=body)

        logging.log_api_response(session_id=session_id,
                                therapist_id=body.therapist_id,
                                patient_id=body.patient_id,
                                endpoint_name=SESSIONS_ENDPOINT,
                                http_status_code=status.HTTP_200_OK,
                                method=logging.API_METHOD_PUT)

        return {}
    except Exception as e:
        description = str(e)
        status_code = status.HTTP_400_BAD_REQUEST if type(e) is not HTTPException else e.status_code
        logging.log_error(session_id=session_id,
                          therapist_id=body.therapist_id,
                          patient_id=body.patient_id,
                          endpoint_name=SESSIONS_ENDPOINT,
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
@router.delete(SESSIONS_ENDPOINT, tags=["assistant"])
async def delete_session(body: model.SessionNotesDelete,
                         response: Response,
                         authorization: Annotated[Union[str, None], Cookie()] = None,
                         current_session_id: Annotated[Union[str, None], Cookie()] = None,):
    if not security.access_token_is_valid(authorization):
        raise security.TOKEN_EXPIRED_ERROR

    try:
        current_entity: security.User = await security.get_current_auth_entity(authorization)
        session_refresh_data: model.SessionRefreshData = await security.refresh_session(user=current_entity,
                                                                                        response=response,
                                                                                        session_id=current_session_id)
        session_id = session_refresh_data._session_id
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))

    logging.log_api_request(session_id=session_id,
                            patient_id=body.patient_id,
                            therapist_id=body.therapist_id,
                            endpoint_name=SESSIONS_ENDPOINT,
                            method=logging.API_METHOD_DELETE,
                            auth_entity=current_entity.username)

    try:
        auth_manager = ManagerFactory.create_auth_manager(environment)
        assistant_manager = ManagerFactory.create_assistant_manager(environment)
        assistant_manager.delete_session(auth_manager=auth_manager, body=body)

        logging.log_api_response(session_id=session_id,
                                therapist_id=body.therapist_id,
                                patient_id=body.patient_id,
                                endpoint_name=SESSIONS_ENDPOINT,
                                http_status_code=status.HTTP_200_OK,
                                method=logging.API_METHOD_DELETE)

        return {}
    except Exception as e:
        description = str(e)
        status_code = status.HTTP_400_BAD_REQUEST if type(e) is not HTTPException else e.status_code
        logging.log_error(session_id=session_id,
                          therapist_id=body.therapist_id,
                          patient_id=body.patient_id,
                          endpoint_name=SESSIONS_ENDPOINT,
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
authorization – The authorization cookie, if exists.
current_session_id – The session_id cookie, if exists.
"""
@router.post(QUERIES_ENDPOINT, tags=["assistant"])
async def execute_assistant_query(query: model.AssistantQuery,
                                  response: Response,
                                  authorization: Annotated[Union[str, None], Cookie()] = None,
                                  current_session_id: Annotated[Union[str, None], Cookie()] = None):
    if not security.access_token_is_valid(authorization):
        raise security.TOKEN_EXPIRED_ERROR

    try:
        current_entity: security.User = await security.get_current_auth_entity(authorization)
        session_refresh_data: model.SessionRefreshData = await security.refresh_session(user=current_entity,
                                                                                        response=response,
                                                                                        session_id=current_session_id)
        session_id = session_refresh_data._session_id
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))

    logging.log_api_request(session_id=session_id,
                            therapist_id=query.therapist_id,
                            patient_id=query.patient_id,
                            endpoint_name=QUERIES_ENDPOINT,
                            method=logging.API_METHOD_POST,
                            auth_entity=current_entity.username)

    try:
        assert Language.get(query.response_language_code).is_valid(), "Invalid response_language_code parameter"

        auth_manager = ManagerFactory.create_auth_manager(environment)
        assistant_manager = ManagerFactory.create_assistant_manager(environment)
        response = assistant_manager.query_session(auth_manager=auth_manager,
                                                   query=query,
                                                   session_id=session_id,
                                                   api_method=logging.API_METHOD_POST,
                                                   endpoint_name=QUERIES_ENDPOINT,
                                                   environment=environment)

        logging.log_api_response(session_id=session_id,
                        therapist_id=query.therapist_id,
                        patient_id=query.patient_id,
                        endpoint_name=QUERIES_ENDPOINT,
                        http_status_code=status.HTTP_200_OK,
                        method=logging.API_METHOD_POST)
        return response
    except Exception as e:
        description = str(e)
        status_code = status.HTTP_400_BAD_REQUEST if type(e) is not HTTPException else e.status_code
        logging.log_error(session_id=session_id,
                          patient_id=query.patient_id,
                          endpoint_name=QUERIES_ENDPOINT,
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
authorization – The authorization cookie, if exists.
current_session_id – The session_id cookie, if exists.
"""
@router.post(GREETINGS_ENDPOINT, tags=["assistant"])
async def fetch_greeting(response: Response,
                         body: model.Greeting,
                         authorization: Annotated[Union[str, None], Cookie()] = None,
                         current_session_id: Annotated[Union[str, None], Cookie()] = None):
    if not security.access_token_is_valid(authorization):
        raise security.TOKEN_EXPIRED_ERROR

    try:
        current_entity: security.User = await security.get_current_auth_entity(authorization)
        session_refresh_data: model.SessionRefreshData = await security.refresh_session(user=current_entity,
                                                                                        response=response,
                                                                                        session_id=current_session_id)
        session_id = session_refresh_data._session_id
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))

    logs_description = ''.join(['language_code:',
                                body.response_language_code,
                                ';tz_identifier:',
                                body.client_tz_identifier])
    logging.log_api_request(session_id=session_id,
                            method=logging.API_METHOD_POST,
                            therapist_id=body.therapist_id,
                            endpoint_name=GREETINGS_ENDPOINT,
                            auth_entity=current_entity.username,
                            description=logs_description)

    try:
        assert datetime_handler.is_valid_timezone_identifier(body.client_tz_identifier), "Invalid timezone identifier parameter"
        assert Language.get(body.response_language_code).is_valid(), "Invalid response_language_code parameter"

        auth_manager = ManagerFactory.create_auth_manager(environment)
        assistant_manager = ManagerFactory.create_assistant_manager(environment)
        result = assistant_manager.fetch_todays_greeting(body=body,
                                                         session_id=session_id,
                                                         endpoint_name=GREETINGS_ENDPOINT,
                                                         api_method=logging.API_METHOD_POST,
                                                         environment=environment,
                                                         auth_manager=auth_manager)

        logging.log_api_response(session_id=session_id,
                                endpoint_name=GREETINGS_ENDPOINT,
                                therapist_id=body.therapist_id,
                                http_status_code=status.HTTP_200_OK,
                                description=logs_description,
                                method=logging.API_METHOD_POST)

        return {"message": result}
    except Exception as e:
        description = str(e)
        status_code = status.HTTP_400_BAD_REQUEST if type(e) is not HTTPException else e.status_code
        logging.log_error(session_id=session_id,
                          endpoint_name=GREETINGS_ENDPOINT,
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
authorization – The authorization cookie, if exists.
current_session_id – The session_id cookie, if exists.
"""
@router.post(PRESESSION_TRAY_ENDPOINT, tags=["assistant"])
async def fetch_presession_tray(response: Response,
                                body: model.SessionHistorySummary,
                                authorization: Annotated[Union[str, None], Cookie()] = None,
                                current_session_id: Annotated[Union[str, None], Cookie()] = None):
    if not security.access_token_is_valid(authorization):
        raise security.TOKEN_EXPIRED_ERROR

    try:
        current_entity: security.User = await security.get_current_auth_entity(authorization)
        session_refresh_data: model.SessionRefreshData = await security.refresh_session(user=current_entity,
                                                                                        response=response,
                                                                                        session_id=current_session_id)
        session_id = session_refresh_data._session_id
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))

    logs_description = ''.join(['language_code:',
                                body.response_language_code])
    logging.log_api_request(session_id=session_id,
                            method=logging.API_METHOD_POST,
                            therapist_id=body.therapist_id,
                            patient_id=body.patient_id,
                            endpoint_name=PRESESSION_TRAY_ENDPOINT,
                            auth_entity=current_entity.username,
                            description=logs_description)

    try:
        assert Language.get(body.response_language_code).is_valid(), "Invalid response_language_code parameter"

        auth_manager = ManagerFactory.create_auth_manager(environment)
        assistant_manager = ManagerFactory.create_assistant_manager(environment)
        response = assistant_manager.create_patient_summary(body=body,
                                                            environment=environment,
                                                            session_id=session_id,
                                                            endpoint_name=PRESESSION_TRAY_ENDPOINT,
                                                            api_method=logging.API_METHOD_POST,
                                                            auth_manager=auth_manager)

        logging.log_api_response(session_id=session_id,
                                 endpoint_name=PRESESSION_TRAY_ENDPOINT,
                                 therapist_id=body.therapist_id,
                                 patient_id=body.patient_id,
                                 http_status_code=status.HTTP_200_OK,
                                 method=logging.API_METHOD_POST)

        return {"summary": response}
    except Exception as e:
        description = str(e)
        status_code = status.HTTP_400_BAD_REQUEST if type(e) is not HTTPException else e.status_code
        logging.log_error(session_id=session_id,
                          endpoint_name=GREETINGS_ENDPOINT,
                          error_code=status_code,
                          description=description,
                          method=logging.API_METHOD_POST)
        raise HTTPException(status_code=status_code,
                            detail=description)
