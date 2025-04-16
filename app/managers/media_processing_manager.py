from abc import ABC
from datetime import datetime
from fastapi import BackgroundTasks, Request

from .assistant_manager import AssistantManager
from .auth_manager import AuthManager
from .email_manager import EmailManager
from ..dependencies.api.aws_db_base_class import AwsDbBaseClass
from ..dependencies.api.aws_s3_base_class import AwsS3BaseClass
from ..dependencies.dependency_container import dependency_container
from ..internal.internal_alert import MediaJobProcessingAlert
from ..internal.schemas import MediaType, SessionProcessingStatus
from ..internal.utilities.datetime_handler import DATE_TIME_FORMAT

class MediaProcessingManager(ABC):

    AUDIO_FILES_PROCESSING_PENDING_BUCKET = "session-audio-files-processing-pending"

    def __init__(self):
        self._email_manager = EmailManager()

    async def _update_session_processing_status(self,
                                                assistant_manager: AssistantManager,
                                                language_code: str,
                                                environment: str,
                                                background_tasks: BackgroundTasks,
                                                auth_manager: AuthManager,
                                                session_id: str,
                                                session_processing_status: str,
                                                session_notes_id: str,
                                                media_type: MediaType,
                                                therapist_id: str,
                                                email_manager: EmailManager,
                                                request: Request,
                                                storage_filepath: str = None):
        """
        Updates the incoming session's processing status.

        Arguments:
        assistant_manager – the assistant manager to leverage internally.
        language_code – the language code to be used for generating dynamic content.
        environment – the current environment.
        background_tasks – the object to schedule concurrent tasks.
        auth_manager – the auth manager to leverage internally.
        session_id – the current session id.
        session_processing_status – the session upload status.
        session_notes_id – the id of the session to be updated.
        media_type – the type of media that was processed.
        therapist_id – the therapist id.
        email_manager – the email manager object.
        request – the upstream Request object.
        storage_filepath – the storage filepath where the backing file is stored in S3.
        """
        aws_db_client: AwsDbBaseClass = dependency_container.inject_aws_db_client()
        await assistant_manager.update_session(
            therapist_id=therapist_id,
            language_code=language_code,
            environment=environment,
            background_tasks=background_tasks,
            auth_manager=auth_manager,
            filtered_body={
                "id": session_notes_id,
                "processing_status": session_processing_status
            },
            session_id=session_id,
            aws_db_client=aws_db_client,
            email_manager=email_manager,
            request=request,
        )

        if session_processing_status != SessionProcessingStatus.SUCCESS.value:
            internal_alert = MediaJobProcessingAlert(
                description="Failed to process a media job. It will automatically be picked-up by daily job for retry",
                media_type=media_type,
                environment=environment,
                session_id=session_id,
                session_report_id=session_notes_id,
                storage_filepath=storage_filepath,
                therapist_id=therapist_id
            )
            await self._email_manager.send_internal_alert(alert=internal_alert)
            return

        if media_type == MediaType.AUDIO:
            # Update tracking row from `pending_audio_jobs` table to reflect successful processing.
            today = datetime.now().date()
            today_formatted = today.strftime(DATE_TIME_FORMAT)
            await aws_db_client.update(
                user_id=therapist_id,
                request=request,
                table_name="pending_audio_jobs",
                filters={
                    "session_report_id": session_notes_id
                },
                payload={
                    "last_attempt_at_processing_date": today_formatted,
                    "successful_processing_date": today_formatted,
                }
            )

            # Delete the file from the processing bucket.
            aws_s3_client: AwsS3BaseClass = dependency_container.inject_aws_s3_client()
            aws_s3_client.delete_file(
                self.AUDIO_FILES_PROCESSING_PENDING_BUCKET,
                storage_filepath=storage_filepath
            )
