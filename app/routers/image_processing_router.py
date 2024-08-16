from fastapi import (APIRouter,
                     BackgroundTasks,
                     Cookie,
                     File,
                     Form,
                     HTTPException,
                     Request,
                     Response,
                     status,
                     UploadFile)
from typing import Annotated, Union

from ..dependencies.api.templates import SessionNotesTemplate
from ..internal import security
from ..internal.logging import Logger
from ..internal.router_dependencies import RouterDependencies
from ..internal.utilities import general_utilities
from ..managers.assistant_manager import AssistantManager
from ..managers.auth_manager import AuthManager
from ..managers.image_processing_manager import ImageProcessingManager

class ImageProcessingRouter:

    IMAGE_UPLOAD_ENDPOINT = "/v1/image-uploads"
    TEXT_EXTRACTION_ENDPOINT = "/v1/textractions"
    ROUTER_TAG = "image-files"

    def __init__(self,
                 assistant_manager: AssistantManager,
                 auth_manager: AuthManager,
                 image_processing_manager: ImageProcessingManager,
                 router_dependencies: RouterDependencies):
        self._assistant_manager = assistant_manager
        self._auth_manager = auth_manager
        self._image_processing_manager = image_processing_manager
        self._supabase_client_factory = router_dependencies.supabase_client_factory
        self._openai_client = router_dependencies.openai_client
        self._docupanda_client = router_dependencies.docupanda_client
        self.router = APIRouter()
        self._register_routes()

    """
    Registers the set of routes that the class' router can access.
    """
    def _register_routes(self):
        @self.router.post(self.IMAGE_UPLOAD_ENDPOINT, tags=[self.ROUTER_TAG])
        async def upload_session_notes_image(response: Response,
                                             request: Request,
                                             background_tasks: BackgroundTasks,
                                             patient_id: Annotated[str, Form()],
                                             image: UploadFile = File(...),
                                             datastore_access_token: Annotated[Union[str, None], Cookie()] = None,
                                             datastore_refresh_token: Annotated[Union[str, None], Cookie()] = None,
                                             authorization: Annotated[Union[str, None], Cookie()] = None,
                                             session_id: Annotated[Union[str, None], Cookie()] = None):
            return await self._upload_session_notes_image_internal(response=response,
                                                                   request=request,
                                                                   background_tasks=background_tasks,
                                                                   patient_id=patient_id,
                                                                   image=image,
                                                                   datastore_access_token=datastore_access_token,
                                                                   datastore_refresh_token=datastore_refresh_token,
                                                                   authorization=authorization,
                                                                   session_id=session_id)

        @self.router.get(self.TEXT_EXTRACTION_ENDPOINT, tags=[self.ROUTER_TAG])
        async def extract_text(response: Response,
                               request: Request,
                               background_tasks: BackgroundTasks,
                               document_id: str = None,
                               datastore_access_token: Annotated[Union[str, None], Cookie()] = None,
                               datastore_refresh_token: Annotated[Union[str, None], Cookie()] = None,
                               template: SessionNotesTemplate = SessionNotesTemplate.FREE_FORM,
                               authorization: Annotated[Union[str, None], Cookie()] = None,
                               session_id: Annotated[Union[str, None], Cookie()] = None):
            return await self._extract_text_internal(response=response,
                                                     request=request,
                                                     background_tasks=background_tasks,
                                                     document_id=document_id,
                                                     datastore_access_token=datastore_access_token,
                                                     datastore_refresh_token=datastore_refresh_token,
                                                     template=template,
                                                     authorization=authorization,
                                                     session_id=session_id)

    """
    Returns a document_id value associated with the file that was uploaded.

    Arguments:
    response – the response model with which to create the final response.
    request – the incoming request object.
    background_tasks – object for scheduling concurrent tasks.
    patient_id – the id of the patient associated with the session notes.
    image – the image to be uploaded.
    authorization – the authorization cookie, if exists.
    datastore_access_token – the datastore access token.
    datastore_refresh_token – the datastore refresh token.
    session_id – the session_id cookie, if exists.
    """
    async def _upload_session_notes_image_internal(self,
                                                   response: Response,
                                                   request: Request,
                                                   background_tasks: BackgroundTasks,
                                                   patient_id: Annotated[str, Form()],
                                                   image: UploadFile,
                                                   authorization: Annotated[Union[str, None], Cookie()],
                                                   datastore_access_token: Annotated[Union[str, None], Cookie()],
                                                   datastore_refresh_token: Annotated[Union[str, None], Cookie()],
                                                   session_id: Annotated[Union[str, None], Cookie()]):
        if not self._auth_manager.access_token_is_valid(authorization):
            raise security.AUTH_TOKEN_EXPIRED_ERROR

        try:
            supabase_client = self._supabase_client_factory.supabase_user_client(access_token=datastore_access_token,
                                                                                 refresh_token=datastore_refresh_token)
            therapist_id = supabase_client.get_current_user_id()
            await self._auth_manager.refresh_session(user_id=therapist_id,
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
                               patient_id=patient_id,
                               therapist_id=therapist_id,
                               endpoint_name=self.IMAGE_UPLOAD_ENDPOINT)

        try:
            assert len(therapist_id or '') > 0, "Invalid therapist_id payload value"
            assert len(patient_id or '') > 0, "Invalid patient_id payload value"

            patient_query = supabase_client.select(fields="*",
                                                   filters={
                                                       'therapist_id': therapist_id,
                                                       'id': patient_id
                                                   },
                                                   table_name="patients")
            assert (0 != len((patient_query).data)), "There isn't a patient-therapist match with the incoming ids."

            document_id = await self._image_processing_manager.upload_image_for_textraction(auth_manager=self._auth_manager,
                                                                                            image=image,
                                                                                            docupanda_client=self._docupanda_client)

            logs_description = f"document_id={document_id}"
            logger.log_api_response(background_tasks=background_tasks,
                                    session_id=session_id,
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
            logger.log_error(background_tasks=background_tasks,
                             session_id=session_id,
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
    background_tasks – object for scheduling concurrent tasks.
    document_id – the id of the document to be textracted.
    template – the template to be used for returning the output.
    datastore_access_token – the datastore access token.
    datastore_refresh_token – the datastore refresh token.
    authorization – the authorization cookie, if exists.
    session_id – the session_id cookie, if exists.
    """
    async def _extract_text_internal(self,
                                     request: Request,
                                     response: Response,
                                     background_tasks: BackgroundTasks,
                                     document_id: str,
                                     template: SessionNotesTemplate,
                                     datastore_access_token: Annotated[Union[str, None], Cookie()],
                                     datastore_refresh_token: Annotated[Union[str, None], Cookie()],
                                     authorization: Annotated[Union[str, None], Cookie()],
                                     session_id: Annotated[Union[str, None], Cookie()]):
        if not self._auth_manager.access_token_is_valid(authorization):
            raise security.AUTH_TOKEN_EXPIRED_ERROR

        try:
            supabase_client = self._supabase_client_factory.supabase_user_client(access_token=datastore_access_token,
                                                                                 refresh_token=datastore_refresh_token)
            therapist_id = supabase_client.get_current_user_id()
            await self._auth_manager.refresh_session(user_id=therapist_id,
                                                     request=request,
                                                     response=response,
                                                     supabase_client_factory=self._supabase_client_factory)
        except Exception as e:
            status_code = general_utilities.extract_status_code(e, fallback=status.HTTP_401_UNAUTHORIZED)
            raise HTTPException(status_code=status_code, detail=str(e))

        logger = Logger(supabase_client_factory=self._supabase_client_factory)
        get_api_method = logger.API_METHOD_GET
        logger.log_api_request(background_tasks=background_tasks,
                               session_id=session_id,
                               method=get_api_method,
                               therapist_id=therapist_id,
                               endpoint_name=self.TEXT_EXTRACTION_ENDPOINT)

        try:
            assert len(document_id or '') > 0, "Didn't receive a valid document id."

            textraction = self._image_processing_manager.extract_text(document_id=document_id,
                                                                      docupanda_client=self._docupanda_client)

            if template == SessionNotesTemplate.FREE_FORM:
                logger.log_api_response(background_tasks=background_tasks,
                                        session_id=session_id,
                                        therapist_id=therapist_id,
                                        endpoint_name=self.TEXT_EXTRACTION_ENDPOINT,
                                        http_status_code=status.HTTP_200_OK,
                                        method=get_api_method)
                return {"textraction": textraction}

            assert template == SessionNotesTemplate.SOAP, f"Unexpected template: {template}"
            soap_textraction = await self._assistant_manager.adapt_session_notes_to_soap(auth_manager=self._auth_manager,
                                                                                         openai_client=self._openai_client,
                                                                                         therapist_id=therapist_id,
                                                                                         session_id=session_id,
                                                                                         session_notes_text=textraction)

            logger.log_api_response(background_tasks=background_tasks,
                                    session_id=session_id,
                                    therapist_id=therapist_id,
                                    endpoint_name=self.TEXT_EXTRACTION_ENDPOINT,
                                    http_status_code=status.HTTP_200_OK,
                                    method=get_api_method)

            return {"soap_textraction": soap_textraction}
        except Exception as e:
            description = str(e)
            status_code = general_utilities.extract_status_code(e, fallback=status.HTTP_400_BAD_REQUEST)
            logger.log_error(background_tasks=background_tasks,
                             session_id=session_id,
                             therapist_id=therapist_id,
                             endpoint_name=self.TEXT_EXTRACTION_ENDPOINT,
                             error_code=status_code,
                             description=description,
                             method=get_api_method)
            raise HTTPException(status_code=status_code, detail=description)
