from datetime import datetime
from fastapi import (APIRouter,
                     BackgroundTasks,
                     Cookie,
                     Security,
                     Form,
                     Header,
                     HTTPException,
                     Request,
                     Response,
                     status)
from typing import Annotated, Union

from ..dependencies.api.templates import SessionNotesTemplate
from ..dependencies.dependency_container import (
    AwsDbBaseClass,
    dependency_container
)
from ..dependencies.api.aws_s3_base_class import AUDIO_FILES_PROCESSING_PENDING_BUCKET, AwsS3BaseClass
from ..internal.schemas import USER_ID_KEY
from ..internal.security.cognito_auth import verify_cognito_token
from ..internal.security.security_schema import SESSION_TOKEN_MISSING_OR_EXPIRED_ERROR
from ..internal.utilities.general_utilities import is_valid_extension
from ..internal.utilities import datetime_handler, general_utilities
from ..managers.assistant_manager import AssistantManager
from ..managers.audio_processing_manager import AudioProcessingManager
from ..managers.auth_manager import AuthManager
from ..managers.email_manager import EmailManager

UUID_LENGTH = 36

class AudioProcessingRouter:

    UPLOAD_URL_ENDPOINT = "/v1/upload-url"
    DIARIZATION_ENDPOINT = "/v1/diarization"
    NOTES_TRANSCRIPTION_ENDPOINT = "/v1/transcriptions"
    ROUTER_TAG = "audio-files"

    def __init__(self, environment: str):
            self._environment = environment
            self._auth_manager = AuthManager()
            self._assistant_manager = AssistantManager()
            self._audio_processing_manager = AudioProcessingManager()
            self._email_manager = EmailManager()
            self.router = APIRouter()
            self._register_routes()

    def _register_routes(self):
        """
        Registers the set of routes that the class' router can access.
        """
        @self.router.post(self.NOTES_TRANSCRIPTION_ENDPOINT, tags=[self.ROUTER_TAG])
        async def transcribe_session_notes(request: Request,
                                           response: Response,
                                           background_tasks: BackgroundTasks,
                                           file_path: Annotated[str, Form()],
                                           template: Annotated[SessionNotesTemplate, Form()],
                                           patient_id: Annotated[str, Form()],
                                           session_date: Annotated[str, Form()],
                                           client_timezone_identifier: Annotated[str, Form()],
                                           _: dict = Security(verify_cognito_token),
                                           session_token: Annotated[Union[str, None], Cookie()] = None,
                                           session_id: Annotated[Union[str, None], Cookie()] = None):
            return await self._transcribe_session_notes_internal(request=request,
                                                                 response=response,
                                                                 background_tasks=background_tasks,
                                                                 template=template,
                                                                 patient_id=patient_id,
                                                                 session_date=session_date,
                                                                 client_timezone_identifier=client_timezone_identifier,
                                                                 file_path=file_path,
                                                                 session_token=session_token,
                                                                 session_id=session_id)

        @self.router.post(self.DIARIZATION_ENDPOINT, tags=[self.ROUTER_TAG])
        async def diarize_session(request: Request,
                                  response: Response,
                                  background_tasks: BackgroundTasks,
                                  file_path: Annotated[str, Form()],
                                  template: Annotated[SessionNotesTemplate, Form()],
                                  patient_id: Annotated[str, Form()],
                                  session_date: Annotated[str, Form()],
                                  client_timezone_identifier: Annotated[str, Form()],
                                  _: dict = Security(verify_cognito_token),
                                  session_token: Annotated[Union[str, None], Cookie()] = None,
                                  session_id: Annotated[Union[str, None], Cookie()] = None):
            return await self._diarize_session_internal(request=request,
                                                        response=response,
                                                        background_tasks=background_tasks,
                                                        template=template,
                                                        patient_id=patient_id,
                                                        session_date=session_date,
                                                        client_timezone_identifier=client_timezone_identifier,
                                                        file_path=file_path,
                                                        session_token=session_token,
                                                        session_id=session_id)

        @self.router.get(self.UPLOAD_URL_ENDPOINT, tags=[self.ROUTER_TAG])
        async def generate_audio_upload_url(request: Request,
                                            response: Response,
                                            patient_id: str = None,
                                            file_extension: str = None,
                                            _: dict = Security(verify_cognito_token),
                                            session_token: Annotated[Union[str, None], Cookie()] = None,
                                            session_id: Annotated[Union[str, None], Cookie()] = None):
            return await self._generate_audio_upload_url_internal(file_extension=file_extension,
                                                                  patient_id=patient_id,
                                                                  request=request,
                                                                  response=response,
                                                                  session_token=session_token,
                                                                  session_id=session_id)

    async def _transcribe_session_notes_internal(self,
                                                 request: Request,
                                                 response: Response,
                                                 background_tasks: BackgroundTasks,
                                                 file_path: str,
                                                 template: Annotated[SessionNotesTemplate, Form()],
                                                 patient_id: Annotated[str, Form()],
                                                 session_date: Annotated[str, Form()],
                                                 client_timezone_identifier: Annotated[str, Form()],
                                                 session_token: Annotated[Union[str, None], Cookie()],
                                                 session_id: Annotated[Union[str, None], Cookie()]):
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
                response=response
            )
        except Exception as e:
            status_code = general_utilities.extract_status_code(e, fallback=status.HTTP_401_UNAUTHORIZED)
            dependency_container.inject_influx_client().log_error(
                endpoint_name=request.url.path,
                session_id=session_id,
                method=request.method,
                error_code=status_code,
                description=str(e),
                patient_id=patient_id
            )
            raise Exception(e)

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

            aws_db_client: AwsDbBaseClass = dependency_container.inject_aws_db_client()
            language_code = await general_utilities.get_user_language_code(
                user_id=user_id,
                aws_db_client=aws_db_client,
            )
            session_report_id = await self._audio_processing_manager.transcribe_audio_file(
                background_tasks=background_tasks,
                assistant_manager=self._assistant_manager,
                auth_manager=self._auth_manager,
                template=template,
                therapist_id=user_id,
                session_id=session_id,
                file_path=file_path,
                session_date=session_date,
                patient_id=patient_id,
                environment=self._environment,
                language_code=language_code,
                diarize=False,
                email_manager=self._email_manager,
                request=request,
            )

            request.state.session_report_id = session_report_id
            return {"session_report_id": session_report_id}
        except Exception as e:
            description = str(e)
            status_code = general_utilities.extract_status_code(e, fallback=status.HTTP_417_EXPECTATION_FAILED)
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

    async def _generate_audio_upload_url_internal(self,
                                                  file_extension: str,
                                                  patient_id: str,
                                                  request: Request,
                                                  response: Response,
                                                  session_token: Annotated[Union[str, None], Cookie()],
                                                  session_id: Annotated[Union[str, None], Cookie()]):
        """
        Generates a URL for the client to be able to upload an (audio) file.

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
                response=response
            )
        except Exception as e:
            status_code = general_utilities.extract_status_code(e, fallback=status.HTTP_401_UNAUTHORIZED)
            dependency_container.inject_influx_client().log_error(
                endpoint_name=request.url.path,
                session_id=session_id,
                method=request.method,
                error_code=status_code,
                description=str(e),
                patient_id=patient_id
            )
            raise Exception(e)

        try:
            assert is_valid_extension(file_extension), "Received invalid file extension."
            assert general_utilities.is_valid_uuid(patient_id or '') > 0, "Invalid patient_id value"
        except Exception as e:
            description = str(e)
            status_code = general_utilities.extract_status_code(e, fallback=status.HTTP_400_BAD_REQUEST)
            dependency_container.inject_influx_client().log_error(
                endpoint_name=request.url.path,
                session_id=session_id,
                method=request.method,
                error_code=status_code,
                description=description
            )
            raise HTTPException(status_code=status_code, detail=description)

        try:
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
            response = storage_client.get_audio_file_upload_signed_url(
                file_path=file_path,
                bucket_name=AUDIO_FILES_PROCESSING_PENDING_BUCKET
            )
            return {
                "upload_token": response.get("token"),
                "file_path": file_path,
                "bucket_name": AUDIO_FILES_PROCESSING_PENDING_BUCKET
            }
        except Exception as e:
            description = str(e)
            status_code = general_utilities.extract_status_code(e, fallback=status.HTTP_417_EXPECTATION_FAILED)
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

    async def _diarize_session_internal(self,
                                        request: Request,
                                        response: Response,
                                        file_path: str,
                                        background_tasks: BackgroundTasks,
                                        template: Annotated[SessionNotesTemplate, Form()],
                                        patient_id: Annotated[str, Form()],
                                        session_date: Annotated[str, Form()],
                                        client_timezone_identifier: Annotated[str, Form()],
                                        session_token: Annotated[Union[str, None], Cookie()],
                                        session_id: Annotated[Union[str, None], Cookie()]):
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
                response=response
            )
        except Exception as e:
            status_code = general_utilities.extract_status_code(e, fallback=status.HTTP_401_UNAUTHORIZED)
            dependency_container.inject_influx_client().log_error(
                endpoint_name=request.url.path,
                session_id=session_id,
                method=request.method,
                error_code=status_code,
                description=str(e)
            )
            raise Exception(e)

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
            )
        except Exception as e:
            description = str(e)
            status_code = general_utilities.extract_status_code(e, fallback=status.HTTP_400_BAD_REQUEST)
            dependency_container.inject_influx_client().log_error(
                endpoint_name=request.url.path,
                session_id=session_id,
                method=request.method,
                error_code=status_code,
                description=description
            )
            raise HTTPException(status_code=status_code, detail=description)

        try:
            session_report_id = await self._audio_processing_manager.transcribe_audio_file(
                background_tasks=background_tasks,
                assistant_manager=self._assistant_manager,
                auth_manager=self._auth_manager,
                template=template,
                therapist_id=user_id,
                session_date=session_date,
                patient_id=patient_id,
                session_id=session_id,
                file_path=file_path,
                environment=self._environment,
                language_code=language_code,
                diarize=True,
                email_manager=self._email_manager,
                request=request,
            )
            request.state.session_report_id = session_report_id
            return {"session_report_id": session_report_id}
        except Exception as e:
            description = str(e)
            status_code = general_utilities.extract_status_code(e, fallback=status.HTTP_417_EXPECTATION_FAILED)
            dependency_container.inject_influx_client().log_error(endpoint_name=request.url.path,
                                                                  session_id=session_id,
                                                                  method=request.method,
                                                                  error_code=status_code,
                                                                  description=description)
            raise HTTPException(status_code=status_code, detail=description)
