import os

from datetime import datetime
from fastapi import (APIRouter,
                     BackgroundTasks,
                     Cookie,
                     Depends,
                     Form,
                     HTTPException,
                     Request,
                     Response,
                     status)
from pydantic import BaseModel
from typing import Annotated, Union

from ..dependencies.api.templates import SessionNotesTemplate
from ..dependencies.dependency_container import (
    AwsDbBaseClass,
    dependency_container
)
from ..dependencies.api.aws_s3_base_class import AwsS3BaseClass
from ..internal.schemas import USER_ID_KEY
from ..internal.security.security_schema import SESSION_TOKEN_MISSING_OR_EXPIRED_ERROR
from ..internal.utilities.general_utilities import is_valid_extension
from ..internal.utilities import datetime_handler, general_utilities
from ..internal.utilities.route_verification import get_user_info
from ..managers.assistant_manager import AssistantManager
from ..managers.audio_processing_manager import AudioProcessingManager
from ..managers.auth_manager import AuthManager
from ..managers.subscription_manager import SubscriptionManager

UUID_LENGTH = 36

class StartMultipartUploadPayload(BaseModel):
    patient_id: str
    file_extension: str

class CompleteMultipartUploadPayload(BaseModel):
    file_path: str
    upload_id: str
    parts: list
    patient_id: str

class AudioProcessingRouter:

    UPLOAD_URL_START_MULTIPART_ENDPOINT = "/v1/upload-url/start-multipart"
    UPLOAD_URL_PRESIGN_PART_ENDPOINT = "/v1/upload-url/presign-part"
    UPLOAD_URL_COMPLETE_ENDPOINT = "/v1/upload-url/complete"
    DIARIZATION_ENDPOINT = "/v1/diarization"
    NOTES_TRANSCRIPTION_ENDPOINT = "/v1/transcriptions"
    ROUTER_TAG = "audio-files"

    def __init__(
        self,
        environment: str
    ):
            self._environment = environment
            self._auth_manager = AuthManager()
            self._assistant_manager = AssistantManager()
            self._audio_processing_manager = AudioProcessingManager()
            self._subscription_manager = SubscriptionManager()
            self.router = APIRouter()
            self._register_routes()

    def _register_routes(self):
        """
        Registers the set of routes that the class' router can access.
        """
        @self.router.post(type(self).NOTES_TRANSCRIPTION_ENDPOINT, tags=[type(self).ROUTER_TAG])
        async def transcribe_session_notes(
            request: Request,
            response: Response,
            background_tasks: BackgroundTasks,
            file_path: Annotated[str, Form()],
            template: Annotated[SessionNotesTemplate, Form()],
            patient_id: Annotated[str, Form()],
            session_date: Annotated[str, Form()],
            client_timezone_identifier: Annotated[str, Form()],
            _: dict = Depends(get_user_info),
            session_token: Annotated[Union[str, None], Cookie()] = None,
            session_id: Annotated[Union[str, None], Cookie()] = None
        ):
            return await self._transcribe_session_notes_internal(
                request=request,
                response=response,
                background_tasks=background_tasks,
                template=template,
                patient_id=patient_id,
                session_date=session_date,
                client_timezone_identifier=client_timezone_identifier,
                file_path=file_path,
                session_token=session_token,
                session_id=session_id
            )

        @self.router.post(type(self).DIARIZATION_ENDPOINT, tags=[type(self).ROUTER_TAG])
        async def diarize_session(
            request: Request,
            response: Response,
            background_tasks: BackgroundTasks,
            file_path: Annotated[str, Form()],
            template: Annotated[SessionNotesTemplate, Form()],
            patient_id: Annotated[str, Form()],
            session_date: Annotated[str, Form()],
            client_timezone_identifier: Annotated[str, Form()],
            _: dict = Depends(get_user_info),
            session_token: Annotated[Union[str, None], Cookie()] = None,
            session_id: Annotated[Union[str, None], Cookie()] = None
        ):
            return await self._diarize_session_internal(
                request=request,
                response=response,
                background_tasks=background_tasks,
                template=template,
                patient_id=patient_id,
                session_date=session_date,
                client_timezone_identifier=client_timezone_identifier,
                file_path=file_path,
                session_token=session_token,
                session_id=session_id
            )

        @self.router.post(type(self).UPLOAD_URL_START_MULTIPART_ENDPOINT, tags=[type(self).ROUTER_TAG])
        async def start_multipart_audio_upload_url(
            request: Request,
            response: Response,
            body: StartMultipartUploadPayload,
            _: dict = Depends(get_user_info),
            session_token: Annotated[Union[str, None], Cookie()] = None,
            session_id: Annotated[Union[str, None], Cookie()] = None
        ):
            return await self._start_multipart_audio_upload_url_internal(
                file_extension=body.file_extension,
                patient_id=body.patient_id,
                request=request,
                response=response,
                session_token=session_token,
                session_id=session_id
            )

        @self.router.get(type(self).UPLOAD_URL_PRESIGN_PART_ENDPOINT, tags=[type(self).ROUTER_TAG])
        async def retrieve_presign_part_url(
            request: Request,
            response: Response,
            file_path: str = None,
            patient_id: str = None,
            upload_id: str = None,
            part_number: int = None,
            _: dict = Depends(get_user_info),
            session_token: Annotated[Union[str, None], Cookie()] = None,
            session_id: Annotated[Union[str, None], Cookie()] = None
        ):
            return await self._retrieve_presign_part_url_internal(
                upload_id=upload_id,
                part_number=part_number,
                file_path=file_path,
                patient_id=patient_id,
                request=request,
                response=response,
                session_token=session_token,
                session_id=session_id
            )

        @self.router.post(type(self).UPLOAD_URL_COMPLETE_ENDPOINT, tags=[type(self).ROUTER_TAG])
        async def complete_multipart_file_upload(
            request: Request,
            response: Response,
            body: CompleteMultipartUploadPayload,
            _: dict = Depends(get_user_info),
            session_token: Annotated[Union[str, None], Cookie()] = None,
            session_id: Annotated[Union[str, None], Cookie()] = None
        ):
            return await self._complete_multipart_file_upload_internal(
                file_path=body.file_path,
                upload_id=body.upload_id,
                parts=body.parts,
                patient_id=body.patient_id,
                request=request,
                response=response,
                session_token=session_token,
                session_id=session_id
            )

    async def _transcribe_session_notes_internal(
        self,
        request: Request,
        response: Response,
        background_tasks: BackgroundTasks,
        file_path: str,
        template: Annotated[SessionNotesTemplate, Form()],
        patient_id: Annotated[str, Form()],
        session_date: Annotated[str, Form()],
        client_timezone_identifier: Annotated[str, Form()],
        session_token: Annotated[Union[str, None], Cookie()],
        session_id: Annotated[Union[str, None], Cookie()]
    ):
        """
        Returns the transcription created from the incoming audio file.

        Arguments:
        request – the response object.
        response – the response model with which to create the final response.
        background_tasks – object for scheduling concurrent tasks.
        file_path – the file_path where the audio file to be transcribed lives in.
        template – the template to be used for generating the output.
        patient_id – the patient id associated with the operation.
        session_date – the session date associated with the operation.
        client_timezone_identifier – the timezone associated with the client.
        session_token – the session_token cookie, if exists.
        session_id – the session_id cookie, if exists.
        """
        request.state.session_id = session_id
        request.state.patient_id = session_id
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
                description=str(e),
                patient_id=patient_id
            )
            raise RuntimeError(e) from e

        try:
            assert len(file_path or '') > 0, "Invalid file path value"
            assert file_path[0:UUID_LENGTH] == user_id, "Attempting to create a diarization session for the wrong patient."
            assert general_utilities.is_valid_uuid(patient_id or '') > 0, "Invalid patient_id payload value"
            assert general_utilities.is_valid_timezone_identifier(client_timezone_identifier), "Invalid timezone identifier parameter"
            assert datetime_handler.is_valid_date(
                date_input=session_date,
                incoming_date_format=datetime_handler.DATE_FORMAT,
                tz_identifier=client_timezone_identifier
            ), "Invalid date format. Date should not be in the future, and the expected format is mm-dd-yyyy"
        except Exception as e:
            description = str(e)
            status_code = general_utilities.extract_status_code(
                e,
                fallback=status.HTTP_400_BAD_REQUEST
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

        try:
            subscription_data = await self._subscription_manager.subscription_data(
                user_id=user_id,
                request=request,
            )
            assert subscription_data[SubscriptionManager.SUBSCRIPTION_STATUS_KEY][SubscriptionManager.IS_SUBSCRIPTION_ACTIVE_KEY], \
                "Subscription is inactive. Unable to add new session."
            assert not subscription_data[SubscriptionManager.SUBSCRIPTION_STATUS_KEY][SubscriptionManager.REACHED_TIER_USAGE_LIMIT_KEY], \
                "Reached usage limit for basic subscription"

            aws_db_client: AwsDbBaseClass = dependency_container.inject_aws_db_client()
            language_code = await general_utilities.get_user_language_code(
                user_id=user_id,
                aws_db_client=aws_db_client,
                request=request,
            )
            session_report_id = await self._audio_processing_manager.transcribe_audio_file(
                background_tasks=background_tasks,
                assistant_manager=self._assistant_manager,
                auth_manager=self._auth_manager,
                template=template,
                therapist_id=user_id,
                session_id=session_id,
                file_path=file_path,
                session_date=datetime.strptime(
                    session_date,
                    datetime_handler.DATE_FORMAT
                ).date(),
                patient_id=patient_id,
                environment=self._environment,
                language_code=language_code,
                diarize=False,
                request=request,
            )

            request.state.session_report_id = session_report_id
            return {"session_report_id": session_report_id}
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

    async def _start_multipart_audio_upload_url_internal(
        self,
        file_extension: str,
        patient_id: str,
        request: Request,
        response: Response,
        session_token: Annotated[Union[str, None], Cookie()],
        session_id: Annotated[Union[str, None], Cookie()]
    ):
        """
        Kicks-off a multipart upload of an audio file.

        Arguments:
        patient_id – the patient id associated with the operation.
        file_extension – the file extension for the file that will be uploaded.
        request – the response object.
        response – the response model with which to create the final response.
        session_token – the session_token cookie, if exists.
        session_id – the session_id cookie, if exists.
        """
        request.state.session_id = session_id
        request.state.patient_id = session_id
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
                description=str(e),
                patient_id=patient_id
            )
            raise RuntimeError(e) from e

        try:
            assert is_valid_extension(file_extension), "Received invalid file extension."
            assert general_utilities.is_valid_uuid(patient_id or '') > 0, "Invalid patient_id value"
        except Exception as e:
            description = str(e)
            status_code = general_utilities.extract_status_code(
                e,
                fallback=status.HTTP_400_BAD_REQUEST
            )
            dependency_container.inject_influx_client().log_error(
                endpoint_name=request.url.path,
                session_id=session_id,
                method=request.method,
                error_code=status_code,
                description=description
            )
            raise HTTPException(status_code=status_code, detail=description)

        try:
            subscription_data = await self._subscription_manager.subscription_data(
                user_id=user_id,
                request=request,
            )
            assert subscription_data[SubscriptionManager.SUBSCRIPTION_STATUS_KEY][SubscriptionManager.IS_SUBSCRIPTION_ACTIVE_KEY], \
                "Subscription is inactive. Unable to add new session."
            assert not subscription_data[SubscriptionManager.SUBSCRIPTION_STATUS_KEY][SubscriptionManager.REACHED_TIER_USAGE_LIMIT_KEY], \
                "Reached usage limit for basic subscription"

            current_timestamp = datetime.now().strftime(datetime_handler.DATE_TIME_FORMAT_FILE)
            file_path = "".join(
                [
                    user_id,
                    "/",
                    patient_id,
                    "-",
                    current_timestamp,
                    file_extension
                ]
            )

            storage_client: AwsS3BaseClass = dependency_container.inject_aws_s3_client()
            file_upload_data = storage_client.initiate_multipart_audio_file_upload(
                file_path=file_path,
                bucket_name=os.environ.get("SESSION_AUDIO_FILES_PROCESSING_BUCKET_NAME")
            )
            return file_upload_data
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

    async def _retrieve_presign_part_url_internal(
        self,
        upload_id: str,
        part_number: int,
        file_path: str,
        patient_id: str,
        request: Request,
        response: Response,
        session_token: Annotated[Union[str, None], Cookie()],
        session_id: Annotated[Union[str, None], Cookie()]
    ):
        """
        Retrieves a url for uploading part #`part_number` of an audio file.

        Arguments:
        upload_id – the ID associated with the overall upload.
        part_number – the part number.
        patient_id – the patient id associated with the operation.
        request – the response object.
        response – the response model with which to create the final response.
        session_token – the session_token cookie, if exists.
        session_id – the session_id cookie, if exists.
        """
        request.state.session_id = session_id
        request.state.patient_id = session_id
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
                description=str(e),
                patient_id=patient_id
            )
            raise RuntimeError(e) from e

        try:
            assert general_utilities.is_valid_uuid(patient_id or '') > 0, "Invalid patient_id value"
            assert len(upload_id or '') > 0, "Invalid upload ID."
            assert len(file_path or '') > 0, "Invalid file path."
            assert part_number > 0, "Invalid part number."
        except Exception as e:
            description = str(e)
            status_code = general_utilities.extract_status_code(
                e,
                fallback=status.HTTP_400_BAD_REQUEST
            )
            dependency_container.inject_influx_client().log_error(
                endpoint_name=request.url.path,
                session_id=session_id,
                method=request.method,
                error_code=status_code,
                description=description
            )
            raise HTTPException(status_code=status_code, detail=description)

        try:
            storage_client: AwsS3BaseClass = dependency_container.inject_aws_s3_client()
            url = storage_client.retrieve_presigned_url_for_multipart_upload(
                file_path=file_path,
                bucket_name=os.environ.get("SESSION_AUDIO_FILES_PROCESSING_BUCKET_NAME"),
                upload_id=upload_id,
                part_number=part_number,
            )
            return {
                "url": url,
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

    async def _complete_multipart_file_upload_internal(
        self,
        file_path: str,
        upload_id: str,
        parts: list,
        patient_id: str,
        request: Request,
        response: Response,
        session_token: Annotated[Union[str, None], Cookie()],
        session_id: Annotated[Union[str, None], Cookie()]
    ):
        """
        Wraps up a multipart upload of an audio file.

        Arguments:
        file_path – the file_path associated with the uploaded file.
        upload_id – the upload ID.
        parts – the (uploaded) parts that make up the file.
        patient_id – the patient ID.
        request – the incoming request object.
        response – the response model with which to create the final response.
        session_token – the session_token cookie, if exists.
        session_id – the session_id cookie, if exists.
        """
        request.state.session_id = session_id
        request.state.patient_id = session_id
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
                description=str(e),
                patient_id=patient_id
            )
            raise RuntimeError(e) from e

        try:
            assert general_utilities.is_valid_uuid(patient_id or '') > 0, "Invalid patient_id value"
            assert len(upload_id or '') > 0, "Invalid upload ID."
            assert len(parts or '') > 0, "Empty parts object"
            assert len(file_path or '') > 0, "Empty file path."
        except Exception as e:
            description = str(e)
            status_code = general_utilities.extract_status_code(
                e,
                fallback=status.HTTP_400_BAD_REQUEST
            )
            dependency_container.inject_influx_client().log_error(
                endpoint_name=request.url.path,
                session_id=session_id,
                method=request.method,
                error_code=status_code,
                description=description
            )
            raise HTTPException(status_code=status_code, detail=description)

        try:
            storage_client: AwsS3BaseClass = dependency_container.inject_aws_s3_client()
            response = storage_client.complete_multipart_audio_file_upload(
                file_path=file_path,
                upload_id=upload_id,
                parts=parts,
                bucket_name=os.environ.get("SESSION_AUDIO_FILES_PROCESSING_BUCKET_NAME")
            )
            return {
                "file_path": file_path
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

    async def _diarize_session_internal(
        self,
        request: Request,
        response: Response,
        file_path: str,
        background_tasks: BackgroundTasks,
        template: Annotated[SessionNotesTemplate, Form()],
        patient_id: Annotated[str, Form()],
        session_date: Annotated[str, Form()],
        client_timezone_identifier: Annotated[str, Form()],
        session_token: Annotated[Union[str, None], Cookie()],
        session_id: Annotated[Union[str, None], Cookie()]
    ):
        """
        Returns the transcription created from the incoming audio file.

        Arguments:
        request – the request object.
        response – the response model with which to create the final response.
        file_path – the file_path where the audio file to be transcribed lives in.
        background_tasks – object for scheduling concurrent tasks.
        template – the template to be used for generating the output.
        patient_id – the patient id associated with the operation.
        session_date – the session date associated with the operation.
        client_timezone_identifier – the timezone associated with the client.
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
                description=str(e)
            )
            raise RuntimeError(e) from e

        try:
            assert len(file_path or '') > 0, "Empty file path value"
            assert file_path[0:UUID_LENGTH] == user_id, "Attempting to create a diarization session for the wrong patient."
            assert general_utilities.is_valid_uuid(patient_id or '') > 0, "Invalid patient_id payload value"
            assert general_utilities.is_valid_timezone_identifier(client_timezone_identifier), "Invalid timezone identifier parameter"
            assert datetime_handler.is_valid_date(
                date_input=session_date,
                incoming_date_format=datetime_handler.DATE_FORMAT,
                tz_identifier=client_timezone_identifier
            ), "Invalid date format. Date should not be in the future, and the expected format is mm-dd-yyyy"

            aws_db_client: AwsDbBaseClass = dependency_container.inject_aws_db_client()
            language_code = await general_utilities.get_user_language_code(
                user_id=user_id,
                aws_db_client=aws_db_client,
                request=request,
            )
        except Exception as e:
            description = str(e)
            status_code = general_utilities.extract_status_code(
                e,
                fallback=status.HTTP_400_BAD_REQUEST
            )
            dependency_container.inject_influx_client().log_error(
                endpoint_name=request.url.path,
                session_id=session_id,
                method=request.method,
                error_code=status_code,
                description=description
            )
            raise HTTPException(status_code=status_code, detail=description)

        try:
            subscription_data = await self._subscription_manager.subscription_data(
                user_id=user_id,
                request=request,
            )
            assert subscription_data[SubscriptionManager.SUBSCRIPTION_STATUS_KEY][SubscriptionManager.IS_SUBSCRIPTION_ACTIVE_KEY], \
                "Subscription is inactive. Unable to add new session."
            assert not subscription_data[SubscriptionManager.SUBSCRIPTION_STATUS_KEY][SubscriptionManager.REACHED_TIER_USAGE_LIMIT_KEY], \
                "Reached usage limit for basic subscription"

            session_report_id = await self._audio_processing_manager.transcribe_audio_file(
                background_tasks=background_tasks,
                assistant_manager=self._assistant_manager,
                auth_manager=self._auth_manager,
                template=template,
                therapist_id=user_id,
                session_date=datetime.strptime(
                    session_date,
                    datetime_handler.DATE_FORMAT
                ).date(),
                patient_id=patient_id,
                session_id=session_id,
                file_path=file_path,
                environment=self._environment,
                language_code=language_code,
                diarize=True,
                request=request,
            )
            request.state.session_report_id = session_report_id
            return {"session_report_id": session_report_id}
        except Exception as e:
            description = str(e)
            status_code = general_utilities.extract_status_code(
                e,
                fallback=status.HTTP_417_EXPECTATION_FAILED
            )
            dependency_container.inject_influx_client().log_error(endpoint_name=request.url.path,
                                                                  session_id=session_id,
                                                                  method=request.method,
                                                                  error_code=status_code,
                                                                  description=description)
            raise HTTPException(status_code=status_code, detail=description)
