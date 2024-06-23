import json

from fastapi import (APIRouter,
                     Cookie,
                     Depends,
                     HTTPException,
                     Form,
                     Response,
                     status,)
from fastapi.security import OAuth2PasswordRequestForm
from supabase import Client
from typing import Annotated, Union

from ..internal import (library_clients,
                        logging,
                        model,
                        security,)

LOGOUT_ENDPOINT = "/logout"
SIGN_UP_ENDPOINT = "/sign-up"
TOKEN_ENDPOINT = "/token"

router = APIRouter()

"""
Returns an oauth token to be used for invoking the endpoints.

Arguments:
form_data  – the data required to validate the user.
response – The response object to be used for creating the final response.
session_id  – the id of the current user session.
"""
@router.post(TOKEN_ENDPOINT, tags=["security"])
async def login_for_access_token(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    response: Response,
    session_id: Annotated[Union[str, None], Cookie()] = None,
) -> security.Token:
    user = security.authenticate_user(security.users_db, form_data.username, form_data.password)
    session_refresh_data: model.SessionRefreshData = await security.refresh_session(user=user,
                                                                                     response=response,
                                                                                     session_id=session_id)
    new_session_id = session_refresh_data._session_id
    logging.log_api_response(session_id=new_session_id,
                             endpoint_name=TOKEN_ENDPOINT,
                             http_status_code=status.HTTP_200_OK,
                             method=logging.API_METHOD_POST,
                             description=f"Refreshing token from {session_id} to {new_session_id}")

    return session_refresh_data._auth_token

"""
Signs up a new user.

Arguments:
signup_data – the data to be used to sign up the user.
response – the response model to be used for creating the final response.
authorization – The authorization cookie, if exists.
current_session_id – The session_id cookie, if exists.
"""
@router.post(SIGN_UP_ENDPOINT, tags=["security"])
async def sign_up(signup_data: model.SignupData,
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
                            method=logging.API_METHOD_POST,
                            endpoint_name=SIGN_UP_ENDPOINT,
                            auth_entity=current_user.username)

    try:
        supabase_client: Client = library_clients.supabase_admin_instance()
        res = supabase_client.auth.sign_up({
            "email": signup_data.user_email,
            "password": signup_data.user_password,
        })

        json_response = json.loads(res.json())
        assert (json_response["user"]["role"] == 'authenticated'
            and json_response["session"]["access_token"]
            and json_response["session"]["refresh_token"]), "Something went wrong when signing up the user"

        user_id = json_response["user"]["id"]
        supabase_client.table('therapists').insert({
            "id": user_id,
            "first_name": signup_data.first_name,
            "middle_name": signup_data.middle_name,
            "last_name": signup_data.last_name,
            "birth_date": signup_data.birth_date,
            "login_mechanism": signup_data.signup_mechanism,
            "email": signup_data.user_email,
            "language_preference": signup_data.language_preference,
        }).execute()

        logging.log_api_response(therapist_id=user_id,
                                session_id=session_id,
                                endpoint_name=SIGN_UP_ENDPOINT,
                                http_status_code=status.HTTP_200_OK,
                                method=logging.API_METHOD_POST)

        return {
            "user_id": user_id,
            "access_token": json_response["session"]["access_token"],
            "refresh_token": json_response["session"]["refresh_token"]
        }
    except Exception as e:
        description = str(e)
        status_code = status.HTTP_400_BAD_REQUEST
        logging.log_error(session_id=session_id,
                          endpoint_name=SIGN_UP_ENDPOINT,
                          error_code=status_code,
                          description=description,
                          method=logging.API_METHOD_POST)
        raise HTTPException(status_code=status_code,
                            detail=description)

"""
Logs out the user.

Arguments:
response – the object to be used for constructing the final response.
therapist_id – The therapist id associated with the operation.
authorization – The authorization cookie, if exists.
current_session_id – The session_id cookie, if exists.
"""
@router.post(LOGOUT_ENDPOINT, tags=["security"])
async def logout(response: Response,
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

    logging.log_api_request(session_id=session_id,
                            therapist_id=therapist_id,
                            method=logging.API_METHOD_POST,
                            endpoint_name=LOGOUT_ENDPOINT,
                            auth_entity=current_user.username)

    response.delete_cookie("authorization")
    response.delete_cookie("session_id")

    logging.log_api_response(session_id=session_id,
                             therapist_id=therapist_id,
                             endpoint_name=LOGOUT_ENDPOINT,
                             http_status_code=status.HTTP_200_OK,
                             method=logging.API_METHOD_POST)

    return {}
