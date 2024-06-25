import os

from fastapi import (APIRouter,
                     Cookie,
                     File,
                     Form,
                     HTTPException,
                     Response,
                     status,
                     UploadFile)
from typing import Annotated, Union

from ..internal import logging, model, security
from ..managers.manager_factory import ManagerFactory

IMAGE_UPLOAD_ENDPOINT = "/v1/image-uploads"
TEXT_EXTRACTION_ENDPOINT = "/v1/textractions"

router = APIRouter()
environment = ...

"""
Returns a document_id value associated with the file that was uploaded.

Arguments:
response – the response model with which to create the final response.
therapist_id – the id of the therapist associated with the session notes.
patient_id – the id of the patient associated with the session notes.
image – the image to be uploaded.
authorization – The authorization cookie, if exists.
current_session_id – The session_id cookie, if exists.
"""
@router.post(IMAGE_UPLOAD_ENDPOINT, tags=["image-files"])
async def upload_session_notes_image(response: Response,
                                     patient_id: Annotated[str, Form()],
                                     therapist_id: Annotated[str, Form()],
                                     image: UploadFile = File(...),
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
                            patient_id=patient_id,
                            therapist_id=therapist_id,
                            endpoint_name=IMAGE_UPLOAD_ENDPOINT,
                            auth_entity=current_user.username)

    try:
        image_processing_manager = ManagerFactory.create_image_processing_manager(environment)
        auth_manager = ManagerFactory.create_auth_manager(environment)
        document_id = await image_processing_manager.upload_image_for_textraction(auth_manager=auth_manager,
                                                                                  image=image)

        logging.log_api_response(session_id=session_id,
                                therapist_id=therapist_id,
                                patient_id=patient_id,
                                endpoint_name=IMAGE_UPLOAD_ENDPOINT,
                                http_status_code=status.HTTP_200_OK,
                                method=logging.API_METHOD_POST)

        return {"document_id": document_id}
    except Exception as e:
        description = str(e)
        status_code = status.HTTP_409_CONFLICT if type(e) is not HTTPException else e.status_code
        logging.log_error(session_id=session_id,
                          endpoint_name=IMAGE_UPLOAD_ENDPOINT,
                          error_code=status_code,
                          description=description,
                          method=logging.API_METHOD_POST)
        raise HTTPException(status_code=status_code, detail=description)

"""
Returns the text extracted from the incoming document_id.

Arguments:
response – the response model to be used for crafting the final response.
therapist_id – the therapist_id for the operation.
patient_id – the patient_id for the operation.
document_id – the id of the document to be textracted.
authorization – The authorization cookie, if exists.
current_session_id – The session_id cookie, if exists.
"""
@router.post(TEXT_EXTRACTION_ENDPOINT, tags=["image-files"])
async def extract_text(response: Response,
                       therapist_id: Annotated[str, Form()],
                       patient_id: Annotated[str, Form()],
                       document_id: str = None,
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
                            method=logging.API_METHOD_GET,
                            therapist_id=therapist_id,
                            patient_id=patient_id,
                            endpoint_name=TEXT_EXTRACTION_ENDPOINT,
                            auth_entity=current_user.username)

    try:
        assert len(document_id) > 0, "Didn't receive a valid document id."
        image_processing_manager = ManagerFactory.create_image_processing_manager(environment)
        full_text = image_processing_manager.extract_text(document_id)

        logging.log_api_response(session_id=session_id,
                                therapist_id=therapist_id,
                                patient_id=patient_id,
                                endpoint_name=TEXT_EXTRACTION_ENDPOINT,
                                http_status_code=status.HTTP_200_OK,
                                method=logging.API_METHOD_GET)

        return {"extraction": full_text}
    except Exception as e:
        description = str(e)
        status_code = status.HTTP_409_CONFLICT if type(e) is not HTTPException else e.status_code
        logging.log_error(session_id=session_id,
                          therapist_id=therapist_id,
                          patient_id=patient_id,
                          endpoint_name=TEXT_EXTRACTION_ENDPOINT,
                          error_code=status_code,
                          description=description,
                          method=logging.API_METHOD_GET)
        raise HTTPException(status_code=status_code, detail=description)
