from abc import ABC
from datetime import datetime
from enum import Enum
from fastapi import BackgroundTasks

from .assistant_manager import AssistantManager
from .auth_manager import AuthManager
from ..dependencies.api.supabase_base_class import SupabaseBaseClass
from ..internal.schemas import SessionUploadStatus
from ..internal.utilities.datetime_handler import DATE_TIME_FORMAT

class MediaType(Enum):
    IMAGE = "image"
    AUDIO = "audio"

class MediaProcessingManager(ABC):

    AUDIO_FILES_PROCESSING_PENDING_BUCKET = "session-audio-files-processing-pending"
    AUDIO_FILES_PROCESSING_COMPLETED_BUCKET = "session-audio-files-processing-completed"

    """
    Updates the incoming session's processing status.

    Arguments:
    assistant_manager – the assistant manager to leverage internally.
    language_code – the language code to be used for generating dynamic content.
    environment – the current environment.
    background_tasks – the object to schedule concurrent tasks.
    auth_manager – the auth manager to leverage internally.
    session_id – the current session id.
    supabase_client – the supabase client to leverage internally.
    session_upload_status – the session upload status.
    session_notes_id – the id of the session to be updated.
    media_type – the type of media that was processed.
    storage_filepath – the storage filepath where the backing file is stored in Supabase.
    """
    async def _update_session_processing_status(self,
                                                assistant_manager: AssistantManager,
                                                language_code: str,
                                                environment: str,
                                                background_tasks: BackgroundTasks,
                                                auth_manager: AuthManager,
                                                session_id: str,
                                                supabase_client: SupabaseBaseClass,
                                                session_upload_status: str,
                                                session_notes_id: str,
                                                media_type: MediaType,
                                                storage_filepath: str = None):
        await assistant_manager.update_session(language_code=language_code,
                                               environment=environment,
                                               background_tasks=background_tasks,
                                               auth_manager=auth_manager,
                                               filtered_body={
                                                   "id": session_notes_id,
                                                   "processing_status": session_upload_status
                                               },
                                               session_id=session_id,
                                               supabase_client=supabase_client)

        if session_upload_status != SessionUploadStatus.SUCCESS.value:
            return

        # Update tracking row from `pending_audio_jobs` table to reflect successful processing.
        today = datetime.now().date()
        today_formatted = today.strftime(DATE_TIME_FORMAT)
        supabase_client.update(table_name="pending_audio_jobs",
                                filters={
                                    "session_report_id": session_notes_id
                                },
                                payload={
                                    "last_attempt_at_processing_date": today_formatted,
                                    "successful_processing_date": today_formatted,
                                })

        if media_type == MediaType.AUDIO:
            # Move the file from the processing pending bucket to the processing completed bucket.
            supabase_client.storage_client.move_file_between_buckets(source_bucket=self.AUDIO_FILES_PROCESSING_PENDING_BUCKET,
                                                                     destination_bucket=self.AUDIO_FILES_PROCESSING_COMPLETED_BUCKET,
                                                                     file_path=storage_filepath)
