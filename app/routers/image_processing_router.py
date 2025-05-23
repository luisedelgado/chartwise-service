from fastapi import (
    APIRouter,
    BackgroundTasks,
    Cookie,
    Depends,
    File,
    Form,
    HTTPException,
    Request,
    Response,
    status,
    UploadFile
)
from typing import Annotated, Union

from ..dependencies.api.templates import SessionNotesTemplate
from ..dependencies.dependency_container import AwsDbBaseClass, dependency_container
from ..internal.schemas import USER_ID_KEY
from ..internal.security.security_schema import SESSION_TOKEN_MISSING_OR_EXPIRED_ERROR
from ..internal.utilities import datetime_handler, general_utilities
from ..internal.utilities.route_verification import get_user_info
from ..managers.assistant_manager import AssistantManager
from ..managers.auth_manager import AuthManager
from ..managers.image_processing_manager import ImageProcessingManager
from ..managers.subscription_manager import SubscriptionManager

class ImageProcessingRouter:

    TEXT_EXTRACTION_ENDPOINT = "/v1/textractions"
    ROUTER_TAG = "image-files"

    def __init__(
        self,
        environment: str
    ):
        self._environment = environment
        self._assistant_manager = AssistantManager()
        self._auth_manager = AuthManager()
        self._image_processing_manager = ImageProcessingManager()
        self._subscription_manager = SubscriptionManager()
        self.router = APIRouter()
        self._register_routes()

    def _register_routes(self):
        """
        Registers the set of routes that the class' router can access.
        """
        @self.router.post(type(self).TEXT_EXTRACTION_ENDPOINT, tags=[type(self).ROUTER_TAG])
        async def extract_text(
            request: Request,
            response: Response,
            background_tasks: BackgroundTasks,
            patient_id: Annotated[str, Form()],
            session_date: Annotated[str, Form()],
            template: Annotated[SessionNotesTemplate, Form()],
            client_timezone_identifier: Annotated[str, Form()],
            _: dict = Depends(get_user_info),
            image: UploadFile = File(...),
            session_token: Annotated[Union[str, None], Cookie()] = None,
            session_id: Annotated[Union[str, None], Cookie()] = None
        ):
            return await self._extract_text_internal(
                request=request,
                response=response,
                background_tasks=background_tasks,
                image=image,
                template=template,
                patient_id=patient_id,
                session_date=session_date,
                client_timezone_identifier=client_timezone_identifier,
                session_token=session_token,
                session_id=session_id
            )

    async def _extract_text_internal(
        self,
        request: Request,
        response: Response,
        background_tasks: BackgroundTasks,
        image: UploadFile,
        template: SessionNotesTemplate,
        patient_id: str,
        session_date: str,
        client_timezone_identifier: str,
        session_token: Annotated[Union[str, None], Cookie()],
        session_id: Annotated[Union[str, None], Cookie()]
    ):
        """
        Performs the textraction on the incoming image file.

        Arguments:
        request – the request object.
        response – the response model with which to create the final response.
        background_tasks – object for scheduling concurrent tasks.
        image – the image to be uploaded.
        template – the template to be used for returning the output.
        patient_id – the patient id.
        session_date – the associated session date.
        client_timezone_identifier – the client timezone id.
        session_token – the session_token cookie, if exists.
        session_id – the session_id cookie, if exists.
        """
        request.state.session_id = session_id
        request.state.patient_id = patient_id
        if not self._auth_manager.session_token_is_valid(session_token):
            raise SESSION_TOKEN_MISSING_OR_EXPIRED_ERROR

        try:
            user_id = self._auth_manager.extract_data_from_token(session_token)[USER_ID_KEY]
            request.state.therapist_id = user_id
            await self._auth_manager.refresh_session(
                user_id=user_id,
                session_id=session_id,
                response=response
            )
        except Exception as e:
            status_code = general_utilities.extract_status_code(
                e,
                fallback=status.HTTP_401_UNAUTHORIZED
            )
            dependency_container.inject_influx_client().log_error(
                endpoint_name=request.url.path,
                session_id=session_id,
                method=request.method,
                error_code=status_code,
                patient_id=patient_id,
                description=str(e)
            )
            raise RuntimeError(e) from e

        try:
            assert general_utilities.is_valid_uuid(patient_id or '') > 0, "Didn't receive a valid document id."
            assert general_utilities.is_valid_timezone_identifier(client_timezone_identifier), "Invalid timezone identifier parameter"
            assert datetime_handler.is_valid_date(
                date_input=session_date,
                incoming_date_format=datetime_handler.DATE_FORMAT,
                tz_identifier=client_timezone_identifier
            ), "Invalid date format. Date should not be in the future, and the expected format is mm-dd-yyyy"
        except Exception as e:
            status_code = general_utilities.extract_status_code(
                e,
                fallback=status.HTTP_400_BAD_REQUEST
            )
            description = str(e)
            dependency_container.inject_influx_client().log_error(
                endpoint_name=request.url.path,
                session_id=session_id,
                method=request.method,
                error_code=status_code,
                description=description
            )
            raise HTTPException(
                status_code=status_code,
                detail=description
            )

        try:
            subscription_data = await self._subscription_manager.subscription_data(
                user_id=user_id,
                request=request,
            )

            assert (
                not subscription_data[SubscriptionManager.SUBSCRIPTION_STATUS_KEY][SubscriptionManager.REACHED_TIER_USAGE_LIMIT_KEY]
                or subscription_data[SubscriptionManager.SUBSCRIPTION_STATUS_KEY][SubscriptionManager.IS_SUBSCRIPTION_ACTIVE_KEY]
            ), "Reached usage limit for freemium tier, and user is not subscribed."

            job_id, session_report_id = await self._image_processing_manager.upload_image_for_textraction(
                patient_id=patient_id,
                therapist_id=user_id,
                session_date=session_date,
                image=image,
                template=template,
                request=request,
            )
            request.state.session_report_id = session_report_id
            background_tasks.add_task(
                self._process_textraction,
                job_id,
                user_id,
                session_id,
                background_tasks,
                request,
            )

            return {
                "session_report_id": session_report_id
            }
        except Exception as e:
            description = str(e)
            status_code = general_utilities.extract_status_code(
                e,
                fallback=status.HTTP_417_EXPECTATION_FAILED
            )
            dependency_container.inject_influx_client().log_error(
                endpoint_name=request.url.path,
                session_id=session_id,
                method=request.method,
                error_code=status_code,
                description=description
            )
            raise HTTPException(
                status_code=status_code,
                detail=description
            )

    async def _process_textraction(
        self,
        job_id: str,
        therapist_id: str,
        session_id: str,
        background_tasks: BackgroundTasks,
        request: Request,
    ):
        """
        Processes the textraction job in the background after the image has been uploaded.

        Arguments:
        job_id – the ID of the textraction job.
        therapist_id – the ID of the therapist who initiated the textraction.
        session_id – the session ID for tracking.
        background_tasks – the background tasks manager for scheduling concurrent tasks.
        aws_db_client – the AWS database client for database operations.
        """
        aws_db_client: AwsDbBaseClass = dependency_container.inject_aws_db_client()
        language_code = await general_utilities.get_user_language_code(
            user_id=therapist_id,
            aws_db_client=aws_db_client,
            request=request,
        )
        await self._image_processing_manager.process_textraction(
            document_id=job_id,
            session_id=session_id,
            environment=self._environment,
            language_code=language_code,
            therapist_id=therapist_id,
            background_tasks=background_tasks,
            auth_manager=self._auth_manager,
            assistant_manager=self._assistant_manager,
            request=request,
        )
