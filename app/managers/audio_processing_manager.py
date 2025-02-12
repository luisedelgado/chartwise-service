from datetime import datetime
from fastapi import BackgroundTasks
from langchain.text_splitter import RecursiveCharacterTextSplitter
from tiktoken import Encoding, get_encoding

from .media_processing_manager import MediaProcessingManager
from ..data_processing.diarization_cleaner import DiarizationCleaner
from ..dependencies.api.supabase_base_class import SupabaseBaseClass
from ..dependencies.api.templates import SessionNotesTemplate
from ..dependencies.dependency_container import dependency_container
from ..internal.schemas import MediaType, SessionUploadStatus
from ..internal.utilities import datetime_handler
from ..managers.assistant_manager import AssistantManager, SessionNotesSource
from ..managers.auth_manager import AuthManager
from ..managers.email_manager import EmailManager
from ..vectors import data_cleaner

from ..vectors.chartwise_assistant import PromptCrafter, PromptScenario

class AudioProcessingManager(MediaProcessingManager):

    DIARIZATION_SUMMARY_ACTION_NAME = "diarization_summary"
    DIARIZATION_CHUNKS_GRAND_SUMMARY_ACTION_NAME = "diarization_chunks_grand_summary"

    async def transcribe_audio_file(self,
                                    background_tasks: BackgroundTasks,
                                    file_path: str,
                                    auth_manager: AuthManager,
                                    assistant_manager: AssistantManager,
                                    supabase_client: SupabaseBaseClass,
                                    template: SessionNotesTemplate,
                                    therapist_id: str,
                                    session_id: str,
                                    language_code: str,
                                    patient_id: str,
                                    session_date: str,
                                    environment: str,
                                    email_manager: EmailManager,
                                    diarize: bool) -> str:
        session_report_id = None

        try:
            # Upload initial attributes of session report, so client can mark it as 'processing'.
            source = SessionNotesSource.FULL_SESSION_RECORDING.value if diarize else SessionNotesSource.NOTES_RECORDING.value
            session_report_creation_response = supabase_client.insert(table_name="session_reports",
                                                                      payload={
                                                                          "template": template.value,
                                                                          "session_date": session_date,
                                                                          "therapist_id": therapist_id,
                                                                          "patient_id": patient_id,
                                                                          "source": source,
                                                                          "processing_status": SessionUploadStatus.PROCESSING.value
                                                                      })
            assert (0 != len((session_report_creation_response).data)), "Something went wrong when inserting the session."
            session_report_id = session_report_creation_response.dict()['data'][0]['id']

            today = datetime.now().date()
            today_formatted = today.strftime(datetime_handler.DATE_TIME_FORMAT)
            supabase_client.insert(table_name="pending_audio_jobs",
                                   payload={
                                       "session_report_id": session_report_id,
                                       "therapist_id": therapist_id,
                                       "storage_filepath": file_path,
                                       "last_attempt_at_processing_date": today_formatted,
                                       "environment": environment,
                                       "job_type": "transcription" if not diarize else "diarization",
                                   })
            audio_file_url = supabase_client.storage_client.get_audio_file_read_signed_url(
                file_path=file_path,
                bucket_name=MediaProcessingManager.AUDIO_FILES_PROCESSING_PENDING_BUCKET
            ).get("signedURL")

            # Attempt immediate processing.
            if diarize:
                background_tasks.add_task(self._diarize_audio_and_save,
                                          session_report_id,
                                          environment,
                                          background_tasks,
                                          supabase_client,
                                          auth_manager,
                                          assistant_manager,
                                          therapist_id,
                                          patient_id,
                                          language_code,
                                          session_id,
                                          template,
                                          file_path,
                                          email_manager,
                                          audio_file_url)
            else:
                background_tasks.add_task(self._transcribe_audio_and_save,
                                          session_report_id,
                                          environment,
                                          background_tasks,
                                          supabase_client,
                                          auth_manager,
                                          assistant_manager,
                                          therapist_id,
                                          language_code,
                                          session_id,
                                          template,
                                          file_path,
                                          email_manager,
                                          audio_file_url)

            background_tasks.add_task(self._update_patient_metrics_after_processing_transcription_session,
                                      patient_id,
                                      session_date,
                                      supabase_client)

            return session_report_id
        except Exception as e:
            if session_report_id is not None:
                await self._update_session_processing_status(assistant_manager=assistant_manager,
                                                             language_code=language_code,
                                                             environment=environment,
                                                             background_tasks=background_tasks,
                                                             auth_manager=auth_manager,
                                                             therapist_id=therapist_id,
                                                             session_id=session_id,
                                                             supabase_client=supabase_client,
                                                             session_upload_status=SessionUploadStatus.FAILED.value,
                                                             session_notes_id=session_report_id,
                                                             media_type=MediaType.AUDIO,
                                                             email_manager=email_manager)
            raise Exception(e)

    # Private

    async def _diarize_audio_and_save(self,
                                      session_report_id: str,
                                      environment: str,
                                      background_tasks: BackgroundTasks,
                                      supabase_client: SupabaseBaseClass,
                                      auth_manager: AuthManager,
                                      assistant_manager: AssistantManager,
                                      therapist_id: str,
                                      patient_id: str,
                                      language_code: str,
                                      session_id: str,
                                      template: SessionNotesTemplate,
                                      storage_filepath: str,
                                      email_manager: EmailManager,
                                      audio_file_url: str):
        try:
            diarization = await dependency_container.inject_deepgram_client().diarize_audio(audio_file_url=audio_file_url)
            update_body = {
                "id": session_report_id,
                "diarization": diarization,
            }
            await assistant_manager.update_session(language_code=language_code,
                                                   environment=environment,
                                                   background_tasks=background_tasks,
                                                   auth_manager=auth_manager,
                                                   filtered_body=update_body,
                                                   session_id=session_id,
                                                   supabase_client=supabase_client,
                                                   email_manager=email_manager)
        except Exception as e:
            await self._update_session_processing_status(assistant_manager=assistant_manager,
                                                         language_code=language_code,
                                                         environment=environment,
                                                         background_tasks=background_tasks,
                                                         auth_manager=auth_manager,
                                                         therapist_id=therapist_id,
                                                         session_id=session_id,
                                                         supabase_client=supabase_client,
                                                         session_upload_status=SessionUploadStatus.FAILED.value,
                                                         session_notes_id=session_report_id,
                                                         media_type=MediaType.AUDIO,
                                                         email_manager=email_manager)
            raise Exception(e)

        # Generate summary for diarization
        try:
            metadata = {
                "user_id": therapist_id,
                "patient_id": patient_id,
                "session_id": str(session_id),
                "action": self.DIARIZATION_SUMMARY_ACTION_NAME
            }

            prompt_crafter = PromptCrafter()
            user_prompt = prompt_crafter.get_user_message_for_scenario(scenario=PromptScenario.DIARIZATION_SUMMARY,
                                                                       diarization=diarization)
            system_prompt = prompt_crafter.get_system_message_for_scenario(scenario=PromptScenario.DIARIZATION_SUMMARY,
                                                                           language_code=language_code)
            encoding = get_encoding("o200k_base")
            prompt_tokens = len(encoding.encode(f"{system_prompt}\n{user_prompt}"))

            openai_client = dependency_container.inject_openai_client()
            max_tokens = openai_client.GPT_4O_MINI_MAX_OUTPUT_TOKENS - prompt_tokens

            if max_tokens < 0:
                # Need to chunk diarization and generate summary of the union of all chunks.
                session_summary = await self._chunk_diarization_and_summarize(encoding=encoding,
                                                                              diarization=diarization,
                                                                              metadata=metadata,
                                                                              prompt_crafter=prompt_crafter,
                                                                              summarize_chunk_system_prompt=system_prompt,
                                                                              language_code=language_code,
                                                                              patient_id=patient_id,
                                                                              therapist_id=therapist_id,
                                                                              session_id=session_id)
            else:
                session_summary = await openai_client.trigger_async_chat_completion(metadata=metadata,
                                                                                    max_tokens=max_tokens,
                                                                                    messages=[
                                                                                        {"role": "system", "content": system_prompt},
                                                                                        {"role": "user", "content": user_prompt},
                                                                                    ],
                                                                                    expects_json_response=False)

            if template == SessionNotesTemplate.SOAP:
                session_summary = await assistant_manager.adapt_session_notes_to_soap(auth_manager=auth_manager,
                                                                                      therapist_id=therapist_id,
                                                                                      session_notes_text=session_summary,
                                                                                      session_id=session_id)

            update_summary_body = {
                "id": session_report_id,
                "notes_text": session_summary,
            }

            await assistant_manager.update_session(language_code=language_code,
                                                   environment=environment,
                                                   background_tasks=background_tasks,
                                                   auth_manager=auth_manager,
                                                   filtered_body=update_summary_body,
                                                   session_id=session_id,
                                                   supabase_client=supabase_client,
                                                   email_manager=email_manager)

            await self._update_session_processing_status(assistant_manager=assistant_manager,
                                                         language_code=language_code,
                                                         environment=environment,
                                                         background_tasks=background_tasks,
                                                         auth_manager=auth_manager,
                                                         therapist_id=therapist_id,
                                                         session_id=session_id,
                                                         supabase_client=supabase_client,
                                                         session_upload_status=SessionUploadStatus.SUCCESS.value,
                                                         session_notes_id=session_report_id,
                                                         media_type=MediaType.AUDIO,
                                                         storage_filepath=storage_filepath,
                                                         email_manager=email_manager)
        except Exception as e:
            await self._update_session_processing_status(assistant_manager=assistant_manager,
                                                         language_code=language_code,
                                                         environment=environment,
                                                         background_tasks=background_tasks,
                                                         auth_manager=auth_manager,
                                                         therapist_id=therapist_id,
                                                         session_id=session_id,
                                                         supabase_client=supabase_client,
                                                         session_upload_status=SessionUploadStatus.FAILED.value,
                                                         session_notes_id=session_report_id,
                                                         media_type=MediaType.AUDIO,
                                                         email_manager=email_manager)
            raise Exception(e)

    async def _transcribe_audio_and_save(self,
                                         session_report_id: str,
                                         environment: str,
                                         background_tasks: BackgroundTasks,
                                         supabase_client: SupabaseBaseClass,
                                         auth_manager: AuthManager,
                                         assistant_manager: AssistantManager,
                                         therapist_id: str,
                                         language_code: str,
                                         session_id: str,
                                         template: SessionNotesTemplate,
                                         storage_filepath: str,
                                         email_manager: EmailManager,
                                         audio_file_url: str):
        try:
            transcription = await dependency_container.inject_deepgram_client().transcribe_audio(audio_file_url=audio_file_url)
            if template == SessionNotesTemplate.SOAP:
                transcription = await assistant_manager.adapt_session_notes_to_soap(auth_manager=auth_manager,
                                                                                    therapist_id=therapist_id,
                                                                                    session_notes_text=transcription,
                                                                                    session_id=session_id)

            update_body = {
                "id": session_report_id,
                "notes_text": transcription
            }

            await assistant_manager.update_session(language_code=language_code,
                                                   environment=environment,
                                                   background_tasks=background_tasks,
                                                   auth_manager=auth_manager,
                                                   filtered_body=update_body,
                                                   session_id=session_id,
                                                   supabase_client=supabase_client,
                                                   email_manager=email_manager)

            await self._update_session_processing_status(assistant_manager=assistant_manager,
                                                         language_code=language_code,
                                                         environment=environment,
                                                         background_tasks=background_tasks,
                                                         auth_manager=auth_manager,
                                                         session_id=session_id,
                                                         therapist_id=therapist_id,
                                                         supabase_client=supabase_client,
                                                         session_upload_status=SessionUploadStatus.SUCCESS.value,
                                                         session_notes_id=session_report_id,
                                                         media_type=MediaType.AUDIO,
                                                         storage_filepath=storage_filepath,
                                                         email_manager=email_manager)
        except Exception as e:
            await self._update_session_processing_status(assistant_manager=assistant_manager,
                                                         language_code=language_code,
                                                         environment=environment,
                                                         therapist_id=therapist_id,
                                                         background_tasks=background_tasks,
                                                         auth_manager=auth_manager,
                                                         session_id=session_id,
                                                         supabase_client=supabase_client,
                                                         session_upload_status=SessionUploadStatus.FAILED.value,
                                                         session_notes_id=session_report_id,
                                                         media_type=MediaType.AUDIO,
                                                         email_manager=email_manager)
            raise Exception(e)

    async def _update_patient_metrics_after_processing_transcription_session(self,
                                                                             patient_id: str,
                                                                             session_date: str,
                                                                             supabase_client: SupabaseBaseClass):
        try:
            # Fetch last session date
            patient_query = supabase_client.select(fields="*",
                                                   filters={
                                                      'id': patient_id
                                                   },
                                                   table_name="patients")
            assert (0 != len((patient_query).data)), "Did not find any data for the patient"

            patient_query_data = patient_query.dict()['data']
            patient_last_session_date = patient_query_data[0]['last_session_date']

            # Fetch total sessions count
            session_reports_query = supabase_client.select(fields="id",
                                                           filters={
                                                               'patient_id': patient_id
                                                           },
                                                           table_name="session_reports")
            total_sessions_count = len(session_reports_query.dict()['data'])

            # Determine the updated value for last_session_date depending on if the patient
            # has met with the therapist before or not.
            if patient_last_session_date is None:
                patient_last_session_date = session_date
            else:
                formatted_date = datetime_handler.convert_to_date_format_mm_dd_yyyy(incoming_date=patient_last_session_date,
                                                                                    incoming_date_format=datetime_handler.DATE_FORMAT_YYYY_MM_DD)
                patient_last_session_date = datetime_handler.retrieve_most_recent_date(first_date=session_date,
                                                                                       first_date_format=datetime_handler.DATE_FORMAT,
                                                                                       second_date=formatted_date,
                                                                                       second_date_format=datetime_handler.DATE_FORMAT)
            supabase_client.update(table_name="patients",
                                    payload={
                                        "last_session_date": patient_last_session_date,
                                        "total_sessions": total_sessions_count,
                                    },
                                    filters={
                                        'id': patient_id
                                    })
        except Exception as e:
            raise Exception(e)

    async def _chunk_diarization_and_summarize(self,
                                               encoding: Encoding,
                                               diarization: list,
                                               metadata: dict,
                                               prompt_crafter: PromptCrafter,
                                               summarize_chunk_system_prompt: str,
                                               language_code: str,
                                               patient_id: str,
                                               therapist_id: str,
                                               session_id: str):
        try:
            splitter = RecursiveCharacterTextSplitter(
                separators=["\n\n", "\n", " ", ""],
                chunk_size=256,
                chunk_overlap=25,
                length_function=lambda text: len(encoding.encode(text)),
            )

            chunk_summaries = []
            flattened_diarization = DiarizationCleaner.flatten_diarization(diarization)
            chunks = splitter.split_text(flattened_diarization)
            for chunk in chunks:
                current_chunk_text = data_cleaner.clean_up_text(chunk)
                user_prompt = prompt_crafter.get_user_message_for_scenario(scenario=PromptScenario.DIARIZATION_SUMMARY,
                                                                           diarization=current_chunk_text)

                prompt_tokens = len(encoding.encode(f"{summarize_chunk_system_prompt}\n{user_prompt}"))

                openai_client = dependency_container.inject_openai_client()
                max_tokens = openai_client.GPT_4O_MINI_MAX_OUTPUT_TOKENS - prompt_tokens
                current_chunk_summary = await openai_client.trigger_async_chat_completion(metadata=metadata,
                                                                                          max_tokens=max_tokens,
                                                                                          messages=[
                                                                                              {"role": "system", "content": summarize_chunk_system_prompt},
                                                                                              {"role": "user", "content": user_prompt},
                                                                                          ],
                                                                                          expects_json_response=False)
                chunk_summaries.append(current_chunk_summary)

            assert len(chunk_summaries or '') > 0, "No chunked summaries available to create a grand summary for incoming (large) diarization"
            grand_summary_raw = " ".join([chunk_summary for chunk_summary in chunk_summaries])
            grand_summary_system_prompt = prompt_crafter.get_system_message_for_scenario(scenario=PromptScenario.DIARIZATION_CHUNKS_GRAND_SUMMARY,
                                                                                         language_code=language_code)
            grand_summary_user_prompt = prompt_crafter.get_user_message_for_scenario(scenario=PromptScenario.DIARIZATION_CHUNKS_GRAND_SUMMARY,
                                                                                     diarization=grand_summary_raw)
            prompt_tokens = len(encoding.encode(f"{summarize_chunk_system_prompt}\n{user_prompt}"))
            max_tokens = openai_client.GPT_4O_MINI_MAX_OUTPUT_TOKENS - prompt_tokens

            grand_summary_metadata = {
                "user_id": therapist_id,
                "patient_id": patient_id,
                "session_id": str(session_id),
                "action": self.DIARIZATION_CHUNKS_GRAND_SUMMARY_ACTION_NAME
            }
            grand_summary = await openai_client.trigger_async_chat_completion(metadata=grand_summary_metadata,
                                                                              max_tokens=max_tokens,
                                                                              messages=[
                                                                                  {"role": "system", "content": grand_summary_system_prompt},
                                                                                  {"role": "user", "content": grand_summary_user_prompt},
                                                                              ],
                                                                              expects_json_response=False)
            return grand_summary
        except Exception as e:
            raise Exception(e)
