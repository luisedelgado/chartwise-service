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

from ..api.auth_base_class import AuthManagerBaseClass
from ..api.image_processing_base_class import ImageProcessingManagerBaseClass
from ..internal import logging, model, security

class ImageProcessingRouter:

    IMAGE_UPLOAD_ENDPOINT = "/v1/image-uploads"
    TEXT_EXTRACTION_ENDPOINT = "/v1/textractions"
    ROUTER_TAG = "image-files"

    def __init__(self,
                auth_manager: AuthManagerBaseClass,
                image_processing_manager: ImageProcessingManagerBaseClass):
        self._auth_manager = auth_manager
        self._image_processing_manager = image_processing_manager
        self.router = APIRouter()
        self._register_routes()

    """
    Registers the set of routes that the class' router can access.
    """
    def _register_routes(self):
        @self.router.post(self.IMAGE_UPLOAD_ENDPOINT, tags=[self.ROUTER_TAG])
        async def upload_session_notes_image(response: Response,
                                             patient_id: Annotated[str, Form()],
                                             therapist_id: Annotated[str, Form()],
                                             image: UploadFile = File(...),
                                             authorization: Annotated[Union[str, None], Cookie()] = None,
                                             current_session_id: Annotated[Union[str, None], Cookie()] = None):
            return await self._upload_session_notes_image_internal(response=response,
                                                                   patient_id=patient_id,
                                                                   therapist_id=therapist_id,
                                                                   image=image,
                                                                   authorization=authorization,
                                                                   current_session_id=current_session_id)

        @self.router.post(self.TEXT_EXTRACTION_ENDPOINT, tags=[self.ROUTER_TAG])
        async def extract_text(response: Response,
                               body: model.TextractionData,
                               authorization: Annotated[Union[str, None], Cookie()] = None,
                               current_session_id: Annotated[Union[str, None], Cookie()] = None):
            return await self._extract_text_internal(response=response,
                                                     body=body,
                                                     authorization=authorization,
                                                     current_session_id=current_session_id)

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
    async def _upload_session_notes_image_internal(self,
                                                   response: Response,
                                                   patient_id: Annotated[str, Form()],
                                                   therapist_id: Annotated[str, Form()],
                                                   image: UploadFile = File(...),
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
                                method=logging.API_METHOD_POST,
                                patient_id=patient_id,
                                therapist_id=therapist_id,
                                endpoint_name=self.IMAGE_UPLOAD_ENDPOINT,
                                auth_entity=current_entity.username)

        try:
            document_id = await self._image_processing_manager.upload_image_for_textraction(auth_manager=self._auth_manager,
                                                                                            image=image)

            logging.log_api_response(session_id=session_id,
                                    therapist_id=therapist_id,
                                    patient_id=patient_id,
                                    endpoint_name=self.IMAGE_UPLOAD_ENDPOINT,
                                    http_status_code=status.HTTP_200_OK,
                                    method=logging.API_METHOD_POST)

            return {"document_id": document_id}
        except Exception as e:
            description = str(e)
            status_code = status.HTTP_409_CONFLICT if type(e) is not HTTPException else e.status_code
            logging.log_error(session_id=session_id,
                            endpoint_name=self.IMAGE_UPLOAD_ENDPOINT,
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
    async def _extract_text_internal(self,
                                     response: Response,
                                     body: model.TextractionData,
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
                                method=logging.API_METHOD_GET,
                                therapist_id=body.therapist_id,
                                patient_id=body.patient_id,
                                endpoint_name=self.TEXT_EXTRACTION_ENDPOINT,
                                auth_entity=current_entity.username)

        try:
            assert len(body.document_id) > 0, "Didn't receive a valid document id."
            full_text = self._image_processing_manager.extract_text(body.document_id)

            logging.log_api_response(session_id=session_id,
                                    therapist_id=body.therapist_id,
                                    patient_id=body.patient_id,
                                    endpoint_name=self.TEXT_EXTRACTION_ENDPOINT,
                                    http_status_code=status.HTTP_200_OK,
                                    method=logging.API_METHOD_GET)

            return {"extraction": full_text}
        except Exception as e:
            description = str(e)
            status_code = status.HTTP_409_CONFLICT if type(e) is not HTTPException else e.status_code
            logging.log_error(session_id=session_id,
                            therapist_id=body.therapist_id,
                            patient_id=body.patient_id,
                            endpoint_name=self.TEXT_EXTRACTION_ENDPOINT,
                            error_code=status_code,
                            description=description,
                            method=logging.API_METHOD_GET)
            raise HTTPException(status_code=status_code, detail=description)
