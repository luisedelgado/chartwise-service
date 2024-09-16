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
from ..dependencies.api.supabase_base_class import SupabaseBaseClass
from ..internal import security
from ..internal.logging import Logger
from ..internal.router_dependencies import DependencyContainer
from ..internal.utilities import datetime_handler, general_utilities
from ..managers.assistant_manager import AssistantManager
from ..managers.auth_manager import AuthManager
from ..managers.image_processing_manager import ImageProcessingManager

class ImageProcessingRouter:

    TEXT_EXTRACTION_ENDPOINT = "/v1/textractions"
    ROUTER_TAG = "image-files"

    def __init__(self,
                 environment: str,
                 assistant_manager: AssistantManager,
                 auth_manager: AuthManager,
                 image_processing_manager: ImageProcessingManager,
                 router_dependencies: DependencyContainer):
        self._environment = environment
        self._assistant_manager = assistant_manager
        self._auth_manager = auth_manager
        self._image_processing_manager = image_processing_manager
        self._supabase_client_factory = router_dependencies.supabase_client_factory
        self._openai_client = router_dependencies.openai_client
        self._docupanda_client = router_dependencies.docupanda_client
        self._pinecone_client = router_dependencies.pinecone_client
        self.router = APIRouter()
        self._register_routes()

    """
    Registers the set of routes that the class' router can access.
    """
    def _register_routes(self):
        @self.router.post(self.TEXT_EXTRACTION_ENDPOINT, tags=[self.ROUTER_TAG])
        async def extract_text(response: Response,
                               request: Request,
                               background_tasks: BackgroundTasks,
                               patient_id: Annotated[str, Form()],
                               session_date: Annotated[str, Form()],
                               template: Annotated[SessionNotesTemplate, Form()],
                               client_timezone_identifier: Annotated[str, Form()],
                               image: UploadFile = File(...),
                               datastore_access_token: Annotated[Union[str, None], Cookie()] = None,
                               datastore_refresh_token: Annotated[Union[str, None], Cookie()] = None,
                               authorization: Annotated[Union[str, None], Cookie()] = None,
                               session_id: Annotated[Union[str, None], Cookie()] = None):
            return await self._extract_text_internal(response=response,
                                                     request=request,
                                                     background_tasks=background_tasks,
                                                     image=image,
                                                     template=template,
                                                     patient_id=patient_id,
                                                     session_date=session_date,
                                                     client_timezone_identifier=client_timezone_identifier,
                                                     datastore_access_token=datastore_access_token,
                                                     datastore_refresh_token=datastore_refresh_token,
                                                     authorization=authorization,
                                                     session_id=session_id)

    """
    Performs the textraction on the incoming image file.

    Arguments:
    response – the response model with which to create the final response.
    request – the incoming request object.
    background_tasks – object for scheduling concurrent tasks.
    image – the image to be uploaded.
    template – the template to be used for returning the output.
    patient_id – the patient id.
    session_date – the associated session date.
    client_timezone_identifier – the client timezone id.
    authorization – the authorization cookie, if exists.
    datastore_access_token – the datastore access token.
    datastore_refresh_token – the datastore refresh token.
    session_id – the session_id cookie, if exists.
    """
    async def _extract_text_internal(self,
                                     response: Response,
                                     request: Request,
                                     background_tasks: BackgroundTasks,
                                     image: UploadFile,
                                     template: SessionNotesTemplate,
                                     patient_id: str,
                                     session_date: str,
                                     client_timezone_identifier: str,
                                     authorization: Annotated[Union[str, None], Cookie()],
                                     datastore_access_token: Annotated[Union[str, None], Cookie()],
                                     datastore_refresh_token: Annotated[Union[str, None], Cookie()],
                                     session_id: Annotated[Union[str, None], Cookie()]):
        if not self._auth_manager.access_token_is_valid(authorization):
            raise security.AUTH_TOKEN_EXPIRED_ERROR

        if datastore_access_token is None or datastore_refresh_token is None:
            raise security.DATASTORE_TOKENS_ERROR

        logger = Logger(supabase_client_factory=self._supabase_client_factory)
        post_api_method = logger.API_METHOD_POST
        description = "".join([
            "template=\"",
            f"{template.value or ''}\";",
            "session_date=\"",
            f"{session_date or ''}\";",
            "client_timezone=\"",
            f"{client_timezone_identifier or ''}\""
        ])
        logger.log_api_request(background_tasks=background_tasks,
                               session_id=session_id,
                               method=post_api_method,
                               description=description,
                               patient_id=patient_id,
                               endpoint_name=self.TEXT_EXTRACTION_ENDPOINT)

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
            description = str(e)
            logger.log_error(background_tasks=background_tasks,
                             session_id=session_id,
                             endpoint_name=self.TEXT_EXTRACTION_ENDPOINT,
                             error_code=status_code,
                             description=description,
                             patient_id=patient_id,
                             method=post_api_method)
            raise HTTPException(status_code=status_code, detail=description)

        try:
            assert len(patient_id or '') > 0, "Didn't receive a valid document id."
            assert general_utilities.is_valid_timezone_identifier(client_timezone_identifier), "Invalid timezone identifier parameter"
            assert datetime_handler.is_valid_date(date_input=session_date,
                                                  incoming_date_format=datetime_handler.DATE_FORMAT,
                                                  tz_identifier=client_timezone_identifier), "Invalid date format. Date should not be in the future, and the expected format is mm-dd-yyyy"
        except Exception as e:
            status_code = general_utilities.extract_status_code(e, fallback=status.HTTP_400_BAD_REQUEST)
            description = str(e)
            logger.log_error(background_tasks=background_tasks,
                             session_id=session_id,
                             endpoint_name=self.TEXT_EXTRACTION_ENDPOINT,
                             error_code=status_code,
                             description=description,
                             method=post_api_method)
            raise HTTPException(status_code=status_code, detail=description)

        try:
            job_id, session_report_id = await self._image_processing_manager.upload_image_for_textraction(patient_id=patient_id,
                                                                                                          therapist_id=therapist_id,
                                                                                                          session_date=session_date,
                                                                                                          supabase_client=supabase_client,
                                                                                                          auth_manager=self._auth_manager,
                                                                                                          image=image,
                                                                                                          template=template,
                                                                                                          docupanda_client=self._docupanda_client)
            background_tasks.add_task(self._process_textraction,
                                      job_id,
                                      therapist_id,
                                      session_id,
                                      logger,
                                      background_tasks,
                                      supabase_client)

            logger.log_api_response(background_tasks=background_tasks,
                                    session_id=session_id,
                                    therapist_id=therapist_id,
                                    endpoint_name=self.TEXT_EXTRACTION_ENDPOINT,
                                    http_status_code=status.HTTP_200_OK,
                                    method=post_api_method)

            return {
                "session_report_id": session_report_id
            }
        except Exception as e:
            description = str(e)
            status_code = general_utilities.extract_status_code(e, fallback=status.HTTP_417_EXPECTATION_FAILED)
            logger.log_error(background_tasks=background_tasks,
                             session_id=session_id,
                             endpoint_name=self.TEXT_EXTRACTION_ENDPOINT,
                             error_code=status_code,
                             description=description,
                             method=post_api_method)
            raise HTTPException(status_code=status_code, detail=description)

    async def _process_textraction(self,
                                   job_id: str,
                                   therapist_id: str,
                                   session_id: str,
                                   logger: Logger,
                                   background_tasks: BackgroundTasks,
                                   supabase_client: SupabaseBaseClass):
        language_code = general_utilities.get_user_language_code(user_id=therapist_id, supabase_client=supabase_client)
        await self._image_processing_manager.process_textraction(document_id=job_id,
                                                                    docupanda_client=self._docupanda_client,
                                                                    session_id=session_id,
                                                                    environment=self._environment,
                                                                    language_code=language_code,
                                                                    logger_worker=logger,
                                                                    background_tasks=background_tasks,
                                                                    openai_client=self._openai_client,
                                                                    supabase_client=supabase_client,
                                                                    pinecone_client=self._pinecone_client,
                                                                    auth_manager=self._auth_manager,
                                                                    assistant_manager=self._assistant_manager)
