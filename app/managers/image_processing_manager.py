import asyncio, os

from fastapi import (
    BackgroundTasks,
    File,
    HTTPException,
    Request,
    status,
    UploadFile
)
from typing import Tuple

from .media_processing_manager import MediaProcessingManager
from ..dependencies.api.templates import SessionNotesTemplate
from ..dependencies.dependency_container import AwsDbBaseClass, dependency_container
from ..internal.internal_alert import MediaJobProcessingAlert
from ..internal.schemas import (MediaType,
                                SessionProcessingStatus,
                                ENCRYPTED_SESSION_REPORTS_TABLE_NAME)
from ..internal.utilities import datetime_handler, file_copiers
from ..managers.assistant_manager import (AssistantManager,
                                          SessionNotesSource)
from ..managers.auth_manager import AuthManager
from ..managers.email_manager import EmailManager

MAX_RETRIES = 5
RETRY_DELAY = 3  # Delay in seconds

class ImageProcessingManager(MediaProcessingManager):

    async def upload_image_for_textraction(self,
                                           patient_id: str,
                                           therapist_id: str,
                                           session_date: str,
                                           template: SessionNotesTemplate,
                                           request: Request,
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

            aws_db_client: AwsDbBaseClass = dependency_container.inject_aws_db_client()
            insert_result = aws_db_client.insert(
                request=request,
                table_name=ENCRYPTED_SESSION_REPORTS_TABLE_NAME,
                payload={
                    "textraction_job_id": doc_id,
                    "template": template.value,
                    "session_date": session_date,
                    "therapist_id": therapist_id,
                    "patient_id": patient_id,
                    "processing_status": SessionProcessingStatus.PROCESSING.value,
                    "source": SessionNotesSource.NOTES_IMAGE.value,
                }
            )
            session_notes_id = insert_result['data'][0]['id']

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
                                  therapist_id: str,
                                  background_tasks: BackgroundTasks,
                                  auth_manager: AuthManager,
                                  assistant_manager: AssistantManager,
                                  email_manager: EmailManager,
                                  request: Request) -> str:
        try:
            session_notes_id = None

            for attempt in range(MAX_RETRIES):
                textraction_status_code, textraction = await dependency_container.inject_docupanda_client().retrieve_text_from_document(document_id)

                if textraction_status_code == status.HTTP_202_ACCEPTED:
                    if attempt < MAX_RETRIES - 1:
                        await asyncio.sleep(RETRY_DELAY)
                    else:
                        alert = MediaJobProcessingAlert(
                            description=f"Textraction with job id {document_id} is still processing after maximum retries",
                            media_type=MediaType.IMAGE,
                            environment=environment,
                            therapist_id=therapist_id,
                            session_id=session_id
                        )
                        await email_manager.send_internal_alert(alert)
                        raise HTTPException(
                            status_code=status.HTTP_408_REQUEST_TIMEOUT,
                            detail="Textraction is still processing after maximum retries"
                        )
                else:
                    # Got successful response
                    break

            aws_db_client: AwsDbBaseClass = dependency_container.inject_aws_db_client()
            session_report_query = aws_db_client.select(
                fields="*",
                table_name=ENCRYPTED_SESSION_REPORTS_TABLE_NAME,
                filters={
                    "textraction_job_id": document_id,
                }
            )
            session_report_data = session_report_query['data']
            assert len(session_report_data) > 0, "Did not find data associated with the textraction job id"
            session_report_data = session_report_data[0]
            therapist_id = session_report_data['therapist_id']
            patient_id = session_report_data['patient_id']
            session_notes_id = session_report_data['id']
            session_date = (None if 'session_date' not in session_report_data
                            else datetime_handler.convert_to_date_format_mm_dd_yyyy(
                                incoming_date=session_report_data['session_date'],
                                incoming_date_format=datetime_handler.DATE_FORMAT_YYYY_MM_DD
                            )
            )

            # If the textraction has already been stored in our DB we can return early.
            if len(session_report_data['notes_text'] or '') > 0:
                return session_notes_id

            if session_report_data['template'] == SessionNotesTemplate.SOAP.value:
                textraction = await assistant_manager.adapt_session_notes_to_soap(
                    therapist_id=therapist_id,
                    session_id=session_id,
                    session_notes_text=textraction
            )

            filtered_body = {
                "id": session_notes_id,
                "patient_id": patient_id,
                "notes_text": textraction,
                "session_date": session_date,
                "source": SessionNotesSource.NOTES_IMAGE,
                "therapist_id": therapist_id
            }

            await assistant_manager.update_session(
                language_code=language_code,
                environment=environment,
                background_tasks=background_tasks,
                auth_manager=auth_manager,
                filtered_body=filtered_body,
                session_id=session_id,
                email_manager=email_manager,
                request=request,
            )

            await self._update_session_processing_status(
                assistant_manager=assistant_manager,
                language_code=language_code,
                environment=environment,
                background_tasks=background_tasks,
                auth_manager=auth_manager,
                session_id=session_id,
                session_processing_status=SessionProcessingStatus.SUCCESS.value,
                session_notes_id=session_notes_id,
                therapist_id=therapist_id,
                media_type=MediaType.IMAGE,
                email_manager=email_manager,
                request=request
            )

        except HTTPException as e:
            # We want to synchronously log the failed processing status to avoid execution
            # stoppage when the exception is raised.
            if session_notes_id is not None:
                await self._update_session_processing_status(
                    assistant_manager=assistant_manager,
                    language_code=language_code,
                    environment=environment,
                    background_tasks=background_tasks,
                    auth_manager=auth_manager,
                    session_id=session_id,
                    therapist_id=therapist_id,
                    session_processing_status=SessionProcessingStatus.FAILED.value,
                    session_notes_id=session_notes_id,
                    media_type=MediaType.IMAGE,
                    email_manager=email_manager,
                    request=request
                )
            alert = MediaJobProcessingAlert(
                description=f"Textraction with job id {document_id} is still processing after maximum retries",
                media_type=MediaType.IMAGE,
                exception=e,
                environment=environment,
                therapist_id=therapist_id,
                session_id=session_id
            )
            await email_manager.send_internal_alert(alert)
            raise HTTPException(
                status_code=e.status_code,
                detail=e.detail
            )
        except Exception as e:
            # We want to synchronously log the failed processing status to avoid execution
            # stoppage when the exception is raised.
            if session_notes_id is not None:
                await self._update_session_processing_status(
                    assistant_manager=assistant_manager,
                    language_code=language_code,
                    environment=environment,
                    background_tasks=background_tasks,
                    auth_manager=auth_manager,
                    session_id=session_id,
                    therapist_id=therapist_id,
                    session_processing_status=SessionProcessingStatus.FAILED.value,
                    session_notes_id=session_notes_id,
                    media_type=MediaType.IMAGE,
                    email_manager=email_manager,
                    request=request,
                )
            alert = MediaJobProcessingAlert(
                description=f"Textraction with job id {document_id} is still processing after maximum retries",
                media_type=MediaType.IMAGE,
                exception=e,
                environment=environment,
                therapist_id=therapist_id,
                session_id=session_id
            )
            await email_manager.send_internal_alert(alert)
            raise Exception(e)
