from datetime import datetime

from fastapi import (APIRouter,
                     Cookie,
                     Form,
                     HTTPException,
                     Response,
                     status,)
from langcodes import Language
from typing import Annotated, Union

from ..internal import library_clients, logging, model, security, utilities
from ..vectors import vector_query, vector_writer

GREETINGS_ENDPOINT = "/v1/greetings"
SESSIONS_ENDPOINT = "/v1/sessions"
QUERIES_ENDPOINT = "/v1/queries"

router = APIRouter()

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
        current_user: security.User = await security.get_current_user(authorization)
        session_refresh_data: model.SessionRefreshData = await security.refresh_session(user=current_user,
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
                            auth_entity=current_user.username)

    try:
        assert utilities.is_valid_date(body.date), "Invalid date. The expected format is mm-dd-yyyy"

        supabase_client = library_clients.supabase_user_instance(body.supabase_access_token,
                                                                 body.supabase_refresh_token)
        now_timestamp = datetime.now().strftime(utilities.DATE_TIME_FORMAT)
        supabase_client.table('session_reports').insert({
            "notes_text": body.text,
            "session_date": body.date,
            "patient_id": body.patient_id,
            "source": body.source,
            "last_updated": now_timestamp,
            "therapist_id": body.therapist_id}).execute()

        # Upload vector embeddings
        vector_writer.insert_session_vectors(index_id=body.therapist_id,
                                             namespace=body.patient_id,
                                             text=body.text,
                                             date=body.date)
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
        current_user: security.User = await security.get_current_user(authorization)
        session_refresh_data: model.SessionRefreshData = await security.refresh_session(user=current_user,
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
                            auth_entity=current_user.username)

    try:
        supabase_client = library_clients.supabase_user_instance(body.supabase_access_token,
                                                                 body.supabase_refresh_token)

        now_timestamp = datetime.now().strftime(utilities.DATE_TIME_FORMAT)
        update_result = supabase_client.table('session_reports').update({
            "notes_text": body.text,
            "last_updated": now_timestamp,
            "session_diarization": body.diarization,
        }).eq('id', body.session_notes_id).execute()

        session_date_raw = update_result.dict()['data'][0]['session_date']
        session_date_formatted = utilities.convert_to_internal_date_format(session_date_raw)

        # Upload vector embeddings
        vector_writer.update_session_vectors(index_id=body.therapist_id,
                                             namespace=body.patient_id,
                                             text=body.text,
                                             date=session_date_formatted)

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
        current_user: security.User = await security.get_current_user(authorization)
        session_refresh_data: model.SessionRefreshData = await security.refresh_session(user=current_user,
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
                            auth_entity=current_user.username)

    try:
        supabase_client = library_clients.supabase_user_instance(body.supabase_access_token,
                                                                 body.supabase_refresh_token)

        delete_result = supabase_client.table('session_reports').delete().eq('id', body.session_notes_id).execute()

        session_date_raw = delete_result.dict()['data'][0]['session_date']
        session_date_formatted = utilities.convert_to_internal_date_format(session_date_raw)

        # Delete vector embeddings
        vector_writer.delete_session_vectors(index_id=body.therapist_id,
                                             namespace=body.patient_id,
                                             date=session_date_formatted)

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
        current_user: security.User = await security.get_current_user(authorization)
        session_refresh_data: model.SessionRefreshData = await security.refresh_session(user=current_user,
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
                            auth_entity=current_user.username)

    try:
        assert Language.get(query.response_language_code).is_valid(), "Invalid response_language_code parameter"
        supabase_client = library_clients.supabase_user_instance(query.supabase_access_token,
                                                                 query.supabase_refresh_token)

        # Confirm that the incoming patient id is assigned to the incoming therapist id.
        patient_therapist_match = (0 != len(
            (supabase_client.from_('patients').select('*').eq('therapist_id', query.therapist_id).eq('id',
                                                                                                    query.patient_id).execute()
        ).data))

        assert patient_therapist_match, "There isn't a patient-therapist match with the incoming ids."
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

    try:
        # Go through with the query
        response: vector_query.QueryResult = vector_query.query_store(index_id=query.therapist_id,
                                                                      namespace=query.patient_id,
                                                                      input=query.text,
                                                                      response_language_code=query.response_language_code,
                                                                      session_id=session_id,
                                                                      endpoint_name=QUERIES_ENDPOINT,
                                                                      method=logging.API_METHOD_POST)

        assert response.status_code != status.HTTP_200_OK, "Something went wrong when executing the query"

        logging.log_api_response(session_id=session_id,
                                therapist_id=query.therapist_id,
                                patient_id=query.patient_id,
                                endpoint_name=QUERIES_ENDPOINT,
                                http_status_code=status.HTTP_200_OK,
                                method=logging.API_METHOD_POST)

        return {"response": response.response_token}
    except Exception as e:
        description = str(e)
        status_code = status.HTTP_400_BAD_REQUEST if type(e) is not HTTPException else e.status_code
        logging.log_error(session_id=session_id,
                        therapist_id=query.therapist_id,
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
addressing_name – the name to be used for addressing the user in the greeting.
response_language_code – the language code to be used for creating the greeting.
client_tz_identifier – the timezone identifier used to fetch the client's weekday.
therapist_id – the id of the therapist for which the greeting is being created.
authorization – The authorization cookie, if exists.
current_session_id – The session_id cookie, if exists.
"""
@router.post(GREETINGS_ENDPOINT, tags=["assistant"])
async def fetch_greeting(response: Response,
                         addressing_name: Annotated[str, Form()],
                         response_language_code: Annotated[str, Form()],
                         client_tz_identifier: Annotated[str, Form()],
                         therapist_id: Annotated[str, Form()],
                         authorization: Annotated[Union[str, None], Cookie()] = None,
                         current_session_id: Annotated[Union[str, None], Cookie()] = None):
    if not security.access_token_is_valid(authorization):
        raise security.TOKEN_EXPIRED_ERROR

    try:
        current_user: security.User = await security.get_current_user(authorization)
        session_refresh_data: model.SessionRefreshData = await security.refresh_session(user=current_user,
                                                                                         response=response,
                                                                                         session_id=current_session_id)
        session_id = session_refresh_data._session_id
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))

    logs_description = ''.join(['language_code:',
                                response_language_code,
                                ';tz_identifier:',
                                client_tz_identifier])
    logging.log_api_request(session_id=session_id,
                            method=logging.API_METHOD_POST,
                            therapist_id=therapist_id,
                            endpoint_name=GREETINGS_ENDPOINT,
                            auth_entity=current_user.username,
                            description=logs_description)

    try:
        assert utilities.is_valid_timezone_identifier(client_tz_identifier), "Invalid timezone identifier parameter"
        assert Language.get(response_language_code).is_valid(), "Invalid response_language_code parameter"

        result = vector_query.create_greeting(name=addressing_name,
                                              language_code=response_language_code,
                                              tz_identifier=client_tz_identifier,
                                              session_id=session_id,
                                              endpoint_name=GREETINGS_ENDPOINT,
                                              therapist_id=therapist_id,
                                              method=logging.API_METHOD_POST)
        assert result.status_code == status.HTTP_200_OK

        logging.log_api_response(session_id=session_id,
                                endpoint_name=GREETINGS_ENDPOINT,
                                therapist_id=therapist_id,
                                http_status_code=status.HTTP_200_OK,
                                description=logs_description,
                                method=logging.API_METHOD_POST)

        return {"message": result.response_token}
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
