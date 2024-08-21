import os

from fastapi import (BackgroundTasks, File, UploadFile)

from ..dependencies.api.deepgram_base_class import DeepgramBaseClass
from ..dependencies.api.openai_base_class import OpenAIBaseClass
from ..dependencies.api.speechmatics_base_class import SpeechmaticsBaseClass
from ..dependencies.api.supabase_base_class import SupabaseBaseClass
from ..dependencies.api.supabase_factory_base_class import SupabaseFactoryBaseClass
from ..dependencies.api.pinecone_base_class import PineconeBaseClass
from ..dependencies.api.templates import SessionNotesTemplate
from ..internal.logging import Logger
from ..internal.utilities import file_copiers
from ..managers.assistant_manager import AssistantManager, SessionNotesInsert, SessionNotesSource
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
                                    client_timezone_identifier: str,
                                    logger_worker: Logger,
                                    environment: str,
                                    audio_file: UploadFile = File(...)) -> str:
        try:
            audio_copy_result: file_copiers.FileCopyResult = await file_copiers.make_file_copy(audio_file)
            files_to_clean = audio_copy_result.file_copies

            if not os.path.exists(audio_copy_result.file_copy_full_path):
                await file_copiers.clean_up_files(files_to_clean)
                raise Exception("Something went wrong while processing the image.")

            transcription = await deepgram_client.transcribe_audio(auth_manager=auth_manager,
                                                                   therapist_id=therapist_id,
                                                                   session_id=session_id,
                                                                   file_full_path=audio_copy_result.file_copy_full_path,
                                                                   openai_client=openai_client,
                                                                   assistant_manager=assistant_manager,
                                                                   template=template)

            session_insert_body = SessionNotesInsert(patient_id=patient_id,
                                                     notes_text=transcription,
                                                     session_date=session_date,
                                                     client_timezone_identifier=client_timezone_identifier,
                                                     source=SessionNotesSource.NOTES_RECORDING)

            return await assistant_manager.process_new_session_data(environment=environment,
                                                                    language_code=language_code,
                                                                    background_tasks=background_tasks,
                                                                    auth_manager=auth_manager,
                                                                    patient_id=session_insert_body.patient_id,
                                                                    session_date=session_insert_body.session_date,
                                                                    notes_text=session_insert_body.notes_text,
                                                                    source=session_insert_body.source,
                                                                    session_id=session_id,
                                                                    therapist_id=therapist_id,
                                                                    openai_client=openai_client,
                                                                    supabase_client=supabase_client,
                                                                    pinecone_client=pinecone_client,
                                                                    logger_worker=logger_worker)

        except Exception as e:
            raise Exception(e)
        finally:
            await file_copiers.clean_up_files(files_to_clean)

    async def diarize_audio_file(self,
                                 auth_manager: AuthManager,
                                 therapist_id: str,
                                 background_tasks: BackgroundTasks,
                                 supabase_client_factory: SupabaseFactoryBaseClass,
                                 speechmatics_client: SpeechmaticsBaseClass,
                                 session_auth_token: str,
                                 endpoint_url: str,
                                 session_id: str,
                                 audio_file: UploadFile = File(...)) -> str:
        try:
            audio_copy_result: file_copiers.FileCopyResult = await file_copiers.make_file_copy(audio_file)
            return speechmatics_client.diarize_audio(auth_manager=auth_manager,
                                                     therapist_id=therapist_id,
                                                     background_tasks=background_tasks,
                                                     session_id=session_id,
                                                     file_name=audio_copy_result.file_copy_name,
                                                     file_full_path=audio_copy_result.file_copy_full_path,
                                                     supabase_client_factory=supabase_client_factory,
                                                     session_auth_token=session_auth_token,
                                                     endpoint_url=endpoint_url)
        except Exception as e:
            raise Exception(e)
        finally:
            await file_copiers.clean_up_files([audio_copy_result.file_copy_full_path])
