from abc import ABC
from fastapi import BackgroundTasks

from .assistant_manager import AssistantManager
from .auth_manager import AuthManager
from ..dependencies.api.supabase_base_class import SupabaseBaseClass

class MediaProcessingManager(ABC):

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
                                                session_notes_id: str):
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
