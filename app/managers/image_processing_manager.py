import asyncio, os

from fastapi import (BackgroundTasks, File, HTTPException, status, UploadFile)
from typing import Tuple

from .media_processing_manager import MediaProcessingManager
from ..dependencies.api.supabase_base_class import SupabaseBaseClass
from ..dependencies.api.templates import SessionNotesTemplate
from ..internal.dependency_container import dependency_container
from ..internal.logging import log_textraction_event
from ..internal.schemas import SessionUploadStatus
from ..internal.utilities import datetime_handler, file_copiers
from ..managers.assistant_manager import (AssistantManager,
                                          SessionNotesSource)
from ..managers.auth_manager import AuthManager

MAX_RETRIES = 5
RETRY_DELAY = 3  # Delay in seconds

class ImageProcessingManager(MediaProcessingManager):

    async def upload_image_for_textraction(self,
                                           patient_id: str,
                                           therapist_id: str,
                                           session_date: str,
                                           template: SessionNotesTemplate,
                                           supabase_client: SupabaseBaseClass,
                                           image: UploadFile = File(...)) -> Tuple[str, str]:
        files_to_clean = None
        try:
            image_copy_result: file_copiers.FileCopyResult = await file_copiers.make_image_pdf_copy(image)
            image_copy_path = image_copy_result.file_copy_full_path
            files_to_clean = image_copy_result.file_copies

            if not os.path.exists(image_copy_path):
                await file_copiers.clean_up_files(files_to_clean)
                raise Exception("Something went wrong while processing the image.")

            doc_id = await dependency_container.inject_docupanda_client().upload_image(image_filepath=image_copy_path,
                                                                                    image_filename=image.filename)

            insert_result = supabase_client.insert(table_name="session_reports",
                                                   payload={
                                                       "textraction_job_id": doc_id,
                                                       "template": template.value,
                                                       "session_date": session_date,
                                                       "therapist_id": therapist_id,
                                                       "patient_id": patient_id,
                                                       "processing_status": SessionUploadStatus.PROCESSING.value,
                                                       "source": SessionNotesSource.NOTES_IMAGE.value,
                                                   })
            session_notes_id = insert_result.dict()['data'][0]['id']

            # Clean up the image copies we used for processing.
            await file_copiers.clean_up_files(files_to_clean)
            return (doc_id, session_notes_id)
        except Exception as e:
            await file_copiers.clean_up_files(files_to_clean)
            raise Exception(str(e))

    async def process_textraction(self,
                                  document_id: str,
                                  session_id: str,
                                  environment: str,
                                  language_code: str,
                                  background_tasks: BackgroundTasks,
                                  supabase_client: SupabaseBaseClass,
                                  auth_manager: AuthManager,
                                  assistant_manager: AssistantManager) -> str:
        try:
            session_notes_id = None

            for attempt in range(MAX_RETRIES):
                textraction_status_code, textraction = await dependency_container.inject_docupanda_client().retrieve_text_from_document(document_id)

                if textraction_status_code == status.HTTP_202_ACCEPTED:
                    if attempt < MAX_RETRIES - 1:
                        await asyncio.sleep(RETRY_DELAY)
                    else:
                        log_textraction_event(background_tasks=background_tasks,
                                              therapist_id=therapist_id,
                                              session_id=session_id,
                                              job_id=document_id,
                                              error_code=status.HTTP_408_REQUEST_TIMEOUT,
                                              description=f"Textraction with job id {document_id} is still processing after maximum retries")
                        raise HTTPException(status_code=status.HTTP_408_REQUEST_TIMEOUT, detail="Textraction is still processing after maximum retries")
                else:
                    # Got successful response
                    break

            session_report_query = supabase_client.select(fields="*",
                                                          table_name="session_reports",
                                                          filters={
                                                              "textraction_job_id": document_id,
                                                          })
            session_report_data = session_report_query.dict()['data']
            assert len(session_report_data) > 0, "Did not find data associated with the textraction job id"
            session_report_data = session_report_data[0]
            therapist_id = session_report_data['therapist_id']
            patient_id = session_report_data['patient_id']
            session_notes_id = session_report_data['id']
            session_date = (None if 'session_date' not in session_report_data
                            else datetime_handler.convert_to_date_format_mm_dd_yyyy(incoming_date=session_report_data['session_date'],
                                                                                    incoming_date_format=datetime_handler.DATE_FORMAT_YYYY_MM_DD))

            # If the textraction has already been stored in Supabase we can return early.
            if len(session_report_data['notes_text'] or '') > 0:
                return session_notes_id

            if session_report_data['template'] == SessionNotesTemplate.SOAP.value:
                textraction = await assistant_manager.adapt_session_notes_to_soap(auth_manager=auth_manager,
                                                                                  therapist_id=therapist_id,
                                                                                  session_id=session_id,
                                                                                  session_notes_text=textraction)

            formatted_session_date = datetime_handler.convert_to_date_format_mm_dd_yyyy(incoming_date=session_report_data['session_date'],
                                                                                        incoming_date_format=datetime_handler.DATE_FORMAT_YYYY_MM_DD)
            filtered_body = {
                "id": session_notes_id,
                "patient_id": patient_id,
                "notes_text": textraction,
                "session_date": formatted_session_date,
                "source": SessionNotesSource.NOTES_IMAGE,
                "therapist_id": therapist_id
            }

            await assistant_manager.update_session(language_code=language_code,
                                                   environment=environment,
                                                   background_tasks=background_tasks,
                                                   auth_manager=auth_manager,
                                                   filtered_body=filtered_body,
                                                   session_id=session_id,
                                                   supabase_client=supabase_client)

            await self._update_session_processing_status(assistant_manager=assistant_manager,
                                                         language_code=language_code,
                                                         environment=environment,
                                                         background_tasks=background_tasks,
                                                         auth_manager=auth_manager,
                                                         session_id=session_id,
                                                         supabase_client=supabase_client,
                                                         session_upload_status=SessionUploadStatus.SUCCESS.value,
                                                         session_notes_id=session_notes_id)

        except HTTPException as e:
            # We want to synchronously log the failed processing status to avoid execution
            # stoppage when the exception is raised.
            if session_notes_id is not None:
                await self._update_session_processing_status(assistant_manager=assistant_manager,
                                                             language_code=language_code,
                                                             environment=environment,
                                                             background_tasks=background_tasks,
                                                             auth_manager=auth_manager,
                                                             session_id=session_id,
                                                             supabase_client=supabase_client,
                                                             session_upload_status=SessionUploadStatus.FAILED.value,
                                                             session_notes_id=session_notes_id)
            raise HTTPException(status_code=e.status_code, detail=e.detail)
        except Exception as e:
            # We want to synchronously log the failed processing status to avoid execution
            # stoppage when the exception is raised.
            if session_notes_id is not None:
                await self._update_session_processing_status(assistant_manager=assistant_manager,
                                                            language_code=language_code,
                                                            environment=environment,
                                                            background_tasks=background_tasks,
                                                            auth_manager=auth_manager,
                                                            session_id=session_id,
                                                            supabase_client=supabase_client,
                                                            session_upload_status=SessionUploadStatus.FAILED.value,
                                                            session_notes_id=session_notes_id)
            raise Exception(e)
