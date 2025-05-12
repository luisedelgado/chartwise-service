import os

from abc import ABC
from fastapi import BackgroundTasks, Request

from .assistant_manager import AssistantManager
from .auth_manager import AuthManager
from ..dependencies.api.aws_s3_base_class import AwsS3BaseClass
from ..dependencies.dependency_container import dependency_container
from ..internal.alerting.internal_alert import MediaJobProcessingAlert
from ..internal.schemas import MediaType, SessionProcessingStatus

class MediaProcessingManager(ABC):

    async def _update_session_processing_status(
        self,
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
        request: Request,
        storage_filepath: str = None
    ):
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
        request – the upstream Request object.
        storage_filepath – the storage filepath where the backing file is stored in S3.
        """
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
            dependency_container.inject_resend_client().send_internal_alert(alert=internal_alert)
            return

        if media_type == MediaType.AUDIO:
            # Delete the file from the processing bucket.
            aws_s3_client: AwsS3BaseClass = dependency_container.inject_aws_s3_client()
            aws_s3_client.delete_file(
                os.environ.get("SESSION_AUDIO_FILES_PROCESSING_BUCKET_NAME"),
                storage_filepath=storage_filepath
            )
