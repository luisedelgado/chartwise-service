import os

from fastapi import (BackgroundTasks, File, UploadFile)

from ..dependencies.api.deepgram_base_class import DeepgramBaseClass
from ..dependencies.api.openai_base_class import OpenAIBaseClass
from ..dependencies.api.supabase_base_class import SupabaseBaseClass
from ..dependencies.api.pinecone_base_class import PineconeBaseClass
from ..dependencies.api.templates import SessionNotesTemplate
from ..internal.logging import Logger
from ..internal.utilities import file_copiers
from ..managers.assistant_manager import AssistantManager, SessionNotesSource
from ..managers.auth_manager import AuthManager

class AudioProcessingManager:

    async def transcribe_audio_file(self,
                                    background_tasks: BackgroundTasks,
                                    auth_manager: AuthManager,
                                    assistant_manager: AssistantManager,
                                    openai_client: OpenAIBaseClass,
                                    deepgram_client: DeepgramBaseClass,
                                    supabase_client: SupabaseBaseClass,
                                    pinecone_client: PineconeBaseClass,
                                    template: SessionNotesTemplate,
                                    therapist_id: str,
                                    session_id: str,
                                    language_code: str,
                                    patient_id: str,
                                    session_date: str,
                                    logger_worker: Logger,
                                    environment: str,
                                    diarize: bool = False,
                                    audio_file: UploadFile = File(...)) -> str:
        try:
            audio_copy_result: file_copiers.FileCopyResult = await file_copiers.make_file_copy(audio_file)
            files_to_clean = audio_copy_result.file_copies
            source = SessionNotesSource.FULL_SESSION_RECORDING.value if diarize else SessionNotesSource.NOTES_RECORDING.value

            if not os.path.exists(audio_copy_result.file_copy_full_path):
                await file_copiers.clean_up_files(files_to_clean)
                raise Exception("Something went wrong while processing the image.")

            session_report_creation_response = supabase_client.insert(table_name="session_reports",
                                                                      payload={
                                                                          "template": template.value,
                                                                          "session_date": session_date,
                                                                          "therapist_id": therapist_id,
                                                                          "patient_id": patient_id,
                                                                          "source": source,
                                                                      })
            assert (0 != len((session_report_creation_response).data)), "Something went wrong when inserting the session."
            session_report_id = session_report_creation_response.dict()['data'][0]['id']

            if diarize:
                background_tasks.add_task(self._diarize_audio_and_save,
                                          session_report_id,
                                          logger_worker,
                                          environment,
                                          background_tasks,
                                          pinecone_client,
                                          deepgram_client,
                                          openai_client,
                                          supabase_client,
                                          auth_manager,
                                          assistant_manager,
                                          therapist_id,
                                          patient_id,
                                          language_code,
                                          session_id,
                                          audio_copy_result,
                                          template,
                                          files_to_clean)
            else:
                background_tasks.add_task(self._transcribe_audio_and_save,
                                          session_report_id,
                                          logger_worker,
                                          environment,
                                          background_tasks,
                                          pinecone_client,
                                          deepgram_client,
                                          openai_client,
                                          supabase_client,
                                          auth_manager,
                                          assistant_manager,
                                          therapist_id,
                                          language_code,
                                          session_id,
                                          audio_copy_result,
                                          template,
                                          files_to_clean)

            return session_report_id
        except Exception as e:
            raise Exception(e)

    # Private

    async def _diarize_audio_and_save(self,
                                      session_report_id: str,
                                      logger_worker: Logger,
                                      environment: str,
                                      background_tasks: BackgroundTasks,
                                      pinecone_client: PineconeBaseClass,
                                      deepgram_client: DeepgramBaseClass,
                                      openai_client: OpenAIBaseClass,
                                      supabase_client: SupabaseBaseClass,
                                      auth_manager: AuthManager,
                                      assistant_manager: AssistantManager,
                                      therapist_id: str,
                                      patient_id: str,
                                      language_code: str,
                                      session_id: str,
                                      audio_copy_result: file_copiers.FileCopyResult,
                                      template: SessionNotesTemplate,
                                      files_to_clean: list):
        try:
            notes_text, diarization = await deepgram_client.diarize_audio(auth_manager=auth_manager,
                                                                        therapist_id=therapist_id,
                                                                        patient_id=patient_id,
                                                                        language_code=language_code,
                                                                        session_id=session_id,
                                                                        file_full_path=audio_copy_result.file_copy_full_path,
                                                                        openai_client=openai_client,
                                                                        assistant_manager=assistant_manager,
                                                                        template=template)

            update_body = {
                "id": session_report_id,
                "notes_text": notes_text,
                "diarization": diarization,
            }

            await assistant_manager.update_session(language_code=language_code,
                                                logger_worker=logger_worker,
                                                environment=environment,
                                                background_tasks=background_tasks,
                                                auth_manager=auth_manager,
                                                filtered_body=update_body,
                                                session_id=session_id,
                                                openai_client=openai_client,
                                                supabase_client=supabase_client,
                                                pinecone_client=pinecone_client)
        except Exception as e:
            raise Exception(e)
        finally:
            await file_copiers.clean_up_files(files_to_clean)

    async def _transcribe_audio_and_save(self,
                                         session_report_id: str,
                                         logger_worker: Logger,
                                         environment: str,
                                         background_tasks: BackgroundTasks,
                                         pinecone_client: PineconeBaseClass,
                                         deepgram_client: DeepgramBaseClass,
                                         openai_client: OpenAIBaseClass,
                                         supabase_client: SupabaseBaseClass,
                                         auth_manager: AuthManager,
                                         assistant_manager: AssistantManager,
                                         therapist_id: str,
                                         language_code: str,
                                         session_id: str,
                                         audio_copy_result: file_copiers.FileCopyResult,
                                         template: SessionNotesTemplate,
                                         files_to_clean: list):
        try:
            transcription = await deepgram_client.transcribe_audio(auth_manager=auth_manager,
                                                                therapist_id=therapist_id,
                                                                session_id=session_id,
                                                                file_full_path=audio_copy_result.file_copy_full_path,
                                                                openai_client=openai_client,
                                                                assistant_manager=assistant_manager,
                                                                template=template)

            update_body = {
                "id": session_report_id,
                "notes_text": transcription
            }

            await assistant_manager.update_session(language_code=language_code,
                                                logger_worker=logger_worker,
                                                environment=environment,
                                                background_tasks=background_tasks,
                                                auth_manager=auth_manager,
                                                filtered_body=update_body,
                                                session_id=session_id,
                                                openai_client=openai_client,
                                                supabase_client=supabase_client,
                                                pinecone_client=pinecone_client)
        except Exception as e:
            raise Exception(e)
        finally:
            await file_copiers.clean_up_files(files_to_clean)
