from fastapi import (APIRouter,
                     Cookie,
                     File,
                     Form,
                     HTTPException,
                     Request,
                     Response,
                     status,
                     UploadFile)
from typing import Annotated, Union

from ..api.assistant_base_class import AssistantManagerBaseClass
from ..api.auth_base_class import AuthManagerBaseClass
from ..api.image_processing_base_class import ImageProcessingManagerBaseClass
from ..internal import security
from ..internal.logging import Logger
from ..internal.model import SessionNotesTemplate
from ..internal.utilities import general_utilities

class ImageProcessingRouter:

    IMAGE_UPLOAD_ENDPOINT = "/v1/image-uploads"
    TEXT_EXTRACTION_ENDPOINT = "/v1/textractions"
    ROUTER_TAG = "image-files"

    def __init__(self,
                 assistant_manager: AssistantManagerBaseClass,
                 auth_manager: AuthManagerBaseClass,
                 image_processing_manager: ImageProcessingManagerBaseClass):
        self._assistant_manager = assistant_manager
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
                                             request: Request,
                                             patient_id: Annotated[str, Form()],
                                             therapist_id: Annotated[str, Form()],
                                             image: UploadFile = File(...),
                                             authorization: Annotated[Union[str, None], Cookie()] = None,
                                             session_id: Annotated[Union[str, None], Cookie()] = None):
            return await self._upload_session_notes_image_internal(response=response,
                                                                   request=request,
                                                                   patient_id=patient_id,
                                                                   therapist_id=therapist_id,
                                                                   image=image,
                                                                   authorization=authorization,
                                                                   session_id=session_id)

        @self.router.get(self.TEXT_EXTRACTION_ENDPOINT, tags=[self.ROUTER_TAG])
        async def extract_text(response: Response,
                               request: Request,
                               therapist_id: str = None,
                               patient_id: str = None,
                               document_id: str = None,
                               template: SessionNotesTemplate = SessionNotesTemplate.FREE_FORM,
                               authorization: Annotated[Union[str, None], Cookie()] = None,
                               session_id: Annotated[Union[str, None], Cookie()] = None):
            return await self._extract_text_internal(response=response,
                                                     request=request,
                                                     therapist_id=therapist_id,
                                                     patient_id=patient_id,
                                                     document_id=document_id,
                                                     template=template,
                                                     authorization=authorization,
                                                     session_id=session_id)

    """
    Returns a document_id value associated with the file that was uploaded.

    Arguments:
    response – the response model with which to create the final response.
    request – the incoming request object.
    therapist_id – the id of the therapist associated with the session notes.
    patient_id – the id of the patient associated with the session notes.
    image – the image to be uploaded.
    authorization – the authorization cookie, if exists.
    session_id – the session_id cookie, if exists.
    """
    async def _upload_session_notes_image_internal(self,
                                                   response: Response,
                                                   request: Request,
                                                   patient_id: Annotated[str, Form()],
                                                   therapist_id: Annotated[str, Form()],
                                                   image: UploadFile,
                                                   authorization: Annotated[Union[str, None], Cookie()],
                                                   session_id: Annotated[Union[str, None], Cookie()]):
        if not self._auth_manager.access_token_is_valid(authorization):
            raise security.AUTH_TOKEN_EXPIRED_ERROR

        try:
            await self._auth_manager.refresh_session(user_id=therapist_id,
                                                     request=request,
                                                     response=response)
        except Exception as e:
            status_code = general_utilities.extract_status_code(e, fallback=status.HTTP_400_BAD_REQUEST)
            raise HTTPException(status_code=status_code, detail=str(e))

        logger = Logger(auth_manager=self._auth_manager)
        post_api_method = logger.API_METHOD_POST
        logger.log_api_request(session_id=session_id,
                               method=post_api_method,
                               patient_id=patient_id,
                               therapist_id=therapist_id,
                               endpoint_name=self.IMAGE_UPLOAD_ENDPOINT)

        try:
            assert len(therapist_id or '') > 0, "Invalid therapist_id payload value"
            assert len(patient_id or '') > 0, "Invalid patient_id payload value"

            document_id = await self._image_processing_manager.upload_image_for_textraction(auth_manager=self._auth_manager,
                                                                                            image=image)

            logs_description = f"document_id={document_id}"
            logger.log_api_response(session_id=session_id,
                                    therapist_id=therapist_id,
                                    patient_id=patient_id,
                                    endpoint_name=self.IMAGE_UPLOAD_ENDPOINT,
                                    http_status_code=status.HTTP_200_OK,
                                    method=post_api_method,
                                    description=logs_description)

            return {"document_id": document_id}
        except Exception as e:
            description = str(e)
            status_code = general_utilities.extract_status_code(e, fallback=status.HTTP_417_EXPECTATION_FAILED)
            logger.log_error(session_id=session_id,
                             endpoint_name=self.IMAGE_UPLOAD_ENDPOINT,
                             error_code=status_code,
                             description=description,
                             method=post_api_method)
            raise HTTPException(status_code=status_code, detail=description)

    """
    Returns the text extracted from the incoming document_id.

    Arguments:
    request – the incoming request object.
    response – the response model to be used for crafting the final response.
    therapist_id – the therapist_id for the operation.
    patient_id – the patient_id for the operation.
    document_id – the id of the document to be textracted.
    template – the template to be used for returning the output.
    authorization – the authorization cookie, if exists.
    session_id – the session_id cookie, if exists.
    """
    async def _extract_text_internal(self,
                                     request: Request,
                                     response: Response,
                                     therapist_id: str,
                                     patient_id: str,
                                     document_id: str,
                                     template: SessionNotesTemplate,
                                     authorization: Annotated[Union[str, None], Cookie()],
                                     session_id: Annotated[Union[str, None], Cookie()]):
        if not self._auth_manager.access_token_is_valid(authorization):
            raise security.AUTH_TOKEN_EXPIRED_ERROR

        try:
            await self._auth_manager.refresh_session(user_id=therapist_id,
                                                     request=request,
                                                     response=response)
        except Exception as e:
            status_code = general_utilities.extract_status_code(e, fallback=status.HTTP_400_BAD_REQUEST)
            raise HTTPException(status_code=status_code, detail=str(e))

        logger = Logger(auth_manager=self._auth_manager)
        get_api_method = logger.API_METHOD_GET
        logger.log_api_request(session_id=session_id,
                               method=get_api_method,
                               therapist_id=therapist_id,
                               patient_id=patient_id,
                               endpoint_name=self.TEXT_EXTRACTION_ENDPOINT)

        try:
            assert len(therapist_id or '') > 0, "Missing therapist_id param."
            assert len(patient_id or '') > 0, "Missing patient_id param."
            assert len(document_id or '') > 0, "Didn't receive a valid document id."

            textraction = self._image_processing_manager.extract_text(document_id)

            if template == SessionNotesTemplate.FREE_FORM:
                logger.log_api_response(session_id=session_id,
                                        therapist_id=therapist_id,
                                        patient_id=patient_id,
                                        endpoint_name=self.TEXT_EXTRACTION_ENDPOINT,
                                        http_status_code=status.HTTP_200_OK,
                                        method=get_api_method)
                return {"textraction": textraction}

            assert template == SessionNotesTemplate.SOAP, f"Unexpected template: {template}"
            soap_textraction = await self._assistant_manager.adapt_session_notes_to_soap(auth_manager=self._auth_manager,
                                                                                         therapist_id=therapist_id,
                                                                                         session_id=session_id,
                                                                                         session_notes_text=textraction)

            logger.log_api_response(session_id=session_id,
                                    therapist_id=therapist_id,
                                    patient_id=patient_id,
                                    endpoint_name=self.TEXT_EXTRACTION_ENDPOINT,
                                    http_status_code=status.HTTP_200_OK,
                                    method=get_api_method)

            return {"soap_textraction": soap_textraction}
        except Exception as e:
            description = str(e)
            status_code = general_utilities.extract_status_code(e, fallback=status.HTTP_400_BAD_REQUEST)
            logger.log_error(session_id=session_id,
                             therapist_id=therapist_id,
                             patient_id=patient_id,
                             endpoint_name=self.TEXT_EXTRACTION_ENDPOINT,
                             error_code=status_code,
                             description=description,
                             method=get_api_method)
            raise HTTPException(status_code=status_code, detail=description)
