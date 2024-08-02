from datetime import datetime

from ..dependencies.api.openai_base_class import OpenAIBaseClass
from ..dependencies.api.supabase_base_class import SupabaseBaseClass
from ..managers.auth_manager import AuthManager
from ..internal.model import (AssistantQuery,
                              PatientInsertPayload,
                              PatientUpdatePayload,
                              SessionNotesInsert,
                              SessionNotesTemplate,
                              SessionNotesUpdate)
from ..internal.utilities import datetime_handler
from ..vectors import vector_writer
from ..vectors.vector_query import IncludeSessionDateOverride, VectorQueryWorker

class AssistantManager:

    async def process_new_session_data(self,
                                       auth_manager: AuthManager,
                                       body: SessionNotesInsert,
                                       session_id: str,
                                       openai_manager: OpenAIBaseClass,
                                       supabase_manager: SupabaseBaseClass) -> str:
        try:
            patient_query = supabase_manager.select(fields="*",
                                                    filters={
                                                        'id': body.patient_id,
                                                        'therapist_id': body.therapist_id
                                                    },
                                                    table_name="patients")
            patient_query_dict = patient_query.dict()
            patient_therapist_match = (0 != len(patient_query_dict['data']))
            assert patient_therapist_match, "There isn't a patient-therapist match with the incoming ids."

            therapist_query = supabase_manager.select(fields="*",
                                                      filters={
                                                          'id': body.therapist_id
                                                      },
                                                      table_name="therapists")
            assert (0 != len(therapist_query.data))

            language_code = therapist_query.dict()['data'][0]["language_preference"]
            mini_summary = await VectorQueryWorker().create_session_mini_summary(session_notes=body.text,
                                                                                 therapist_id=body.therapist_id,
                                                                                 language_code=language_code,
                                                                                 auth_manager=auth_manager,
                                                                                 openai_manager=openai_manager,
                                                                                 session_id=session_id)

            patient_last_session_date = patient_query_dict['data'][0]['last_session_date']

            # Determine the updated value for last_session_date depending on if the patient
            # has met with the therapist before or not.
            if patient_last_session_date is None:
                patient_last_session_date = body.date
            else:
                patient_last_session_date = datetime_handler.retrieve_most_recent_date(body.date,
                                                                                       datetime_handler.convert_to_internal_date_format(patient_last_session_date))

            supabase_manager.update(table_name="patients",
                                    payload={
                                        "last_session_date": patient_last_session_date,
                                        "total_sessions": (1 + (patient_query_dict['data'][0]['total_sessions'])),
                                    },
                                    filters={
                                        'id': body.patient_id
                                    })

            now_timestamp = datetime.now().strftime(datetime_handler.DATE_TIME_FORMAT)
            insert_result = supabase_manager.insert(table_name="session_reports",
                                                    payload={
                                                        "notes_text": body.text,
                                                        "notes_mini_summary": mini_summary,
                                                        "session_date": body.date,
                                                        "patient_id": body.patient_id,
                                                        "source": body.source.value,
                                                        "last_updated": now_timestamp,
                                                        "therapist_id": body.therapist_id
                                                    })
            session_notes_id = insert_result.dict()['data'][0]['id']

            # Upload vector embeddings
            await vector_writer.insert_session_vectors(index_id=body.therapist_id,
                                                       namespace=body.patient_id,
                                                       text=body.text,
                                                       therapy_session_date=body.date,
                                                       openai_manager=openai_manager,
                                                       auth_manager=auth_manager,
                                                       session_id=session_id)

            return session_notes_id
        except Exception as e:
            raise Exception(e)

    async def update_session(self,
                             auth_manager: AuthManager,
                             body: SessionNotesUpdate,
                             session_id: str,
                             openai_manager: OpenAIBaseClass,
                             supabase_manager: SupabaseBaseClass):
        try:
            report_query = supabase_manager.select(fields="*",
                                                   table_name="session_reports",
                                                   filters={
                                                       'id': body.session_notes_id,
                                                       'therapist_id': body.therapist_id,
                                                   })
            assert (0 != len((report_query).data)), "There isn't a match with the incoming session data."
            report_query_dict = report_query.dict()
            patient_id = report_query_dict['data'][0]['patient_id']
            current_mini_summary = report_query_dict['data'][0]['notes_mini_summary']
            current_session_text = report_query_dict['data'][0]['notes_text']
            current_session_date = report_query_dict['data'][0]['session_date']
            current_session_date_formatted = datetime_handler.convert_to_internal_date_format(current_session_date)
            session_text_changed = body.text != current_session_text
            session_date_changed = current_session_date_formatted != body.date

            # We only have to generate a new mini_summary if the session text changed.
            if session_text_changed:
                therapist_query = supabase_manager.select(fields="*",
                                                        table_name="therapists",
                                                        filters={
                                                            'id': body.therapist_id
                                                        })
                assert (0 != len((therapist_query).data))

                language_code = therapist_query.dict()['data'][0]["language_preference"]
                mini_summary = await VectorQueryWorker().create_session_mini_summary(session_notes=body.text,
                                                                                    therapist_id=body.therapist_id,
                                                                                    language_code=language_code,
                                                                                    auth_manager=auth_manager,
                                                                                    openai_manager=openai_manager,
                                                                                    session_id=session_id)
            else:
                mini_summary = current_mini_summary

            now_timestamp = datetime.now().strftime(datetime_handler.DATE_TIME_FORMAT)
            supabase_manager.update(table_name="session_reports",
                                    payload={
                                        "notes_text": body.text,
                                        "notes_mini_summary": mini_summary,
                                        "last_updated": now_timestamp,
                                        "source": body.source.value,
                                        "session_date": body.date,
                                        "diarization": body.diarization,
                                    },
                                    filters={
                                        'id': body.session_notes_id
                                    })

            if session_date_changed or session_text_changed:
                # Upload vector embeddings with the original session date since that's what was used for insertion.
                await vector_writer.update_session_vectors(index_id=body.therapist_id,
                                                           namespace=patient_id,
                                                           text=body.text,
                                                           session_id=session_id,
                                                           old_date=current_session_date_formatted,
                                                           new_date=body.date,
                                                           openai_manager=openai_manager,
                                                           auth_manager=auth_manager)
        except Exception as e:
            raise Exception(e)

    def delete_session(self,
                       therapist_id: str,
                       session_report_id: str,
                       supabase_manager: SupabaseBaseClass):
        try:
            # Validate the session report is linked to the therapist id
            report_query = supabase_manager.select(fields="*",
                                                   table_name="session_reports",
                                                   filters={
                                                       'id': session_report_id,
                                                       'therapist_id': therapist_id
                                                   })
            assert (0 != len((report_query).data)), "The incoming therapist_id isn't associated with the session_report_id."
            patient_id = report_query.dict()['data'][0]['patient_id']

            # Grab the most recent session date to determine if we'll have to update it
            patient_query = supabase_manager.select(fields="*",
                                        filters={
                                            'id': patient_id,
                                            'therapist_id': therapist_id
                                        },
                                        table_name="patients")
            patient_query_dict = patient_query.dict()
            assert len(patient_query_dict['data']) > 0, "No patient data found"
            patient_last_session_date = patient_query_dict['data'][0]['last_session_date']

            # Delete the session notes from Supabase
            delete_result = supabase_manager.delete(table_name="session_reports",
                                                    filters={
                                                        'id': session_report_id
                                                    })
            delete_result_dict = delete_result.dict()
            assert len(delete_result_dict['data']) > 0, "No session found with the incoming session_report_id"

            therapist_id = delete_result_dict['data'][0]['therapist_id']
            patient_id = delete_result_dict['data'][0]['patient_id']
            session_date = delete_result_dict['data'][0]['session_date']

            # If we deleted the last_session_date we were tracking for the patient, we should update what the new last_session_date is
            if session_date == patient_last_session_date:
                patient_session_notes_response = supabase_manager.select(fields="*",
                                                                         table_name="session_reports",
                                                                         filters={
                                                                             "patient_id": patient_id
                                                                         },
                                                                         order_desc_column="session_date")
                patient_session_notes_response_dict = patient_session_notes_response.dict()
                patient_last_session_date = (None if len(patient_session_notes_response_dict['data']) == 0
                                             else patient_session_notes_response_dict['data'][0]['session_date'])

            # Update total_sessions and last_session_date
            supabase_manager.update(table_name="patients",
                                    payload={
                                        "total_sessions": (patient_query_dict['data'][0]['total_sessions'] - 1),
                                        "last_session_date": patient_last_session_date,
                                    },
                                    filters={
                                        'id': patient_id
                                    })

            # Delete vector embeddings
            session_date_formatted = datetime_handler.convert_to_internal_date_format(session_date)
            vector_writer.delete_session_vectors(index_id=therapist_id,
                                                 namespace=patient_id,
                                                 date=session_date_formatted)
        except Exception as e:
            raise Exception(e)

    async def add_patient(self,
                          auth_manager: AuthManager,
                          payload: PatientInsertPayload,
                          session_id: str,
                          openai_manager: OpenAIBaseClass,
                          supabase_manager: SupabaseBaseClass) -> str:
        try:
            response = supabase_manager.insert(table_name="patients",
                                               payload={
                                                   "first_name": payload.first_name,
                                                   "middle_name": payload.middle_name,
                                                   "last_name": payload.last_name,
                                                   "birth_date": payload.birth_date,
                                                   "email": payload.email,
                                                   "pre_existing_history": payload.pre_existing_history,
                                                   "gender": payload.gender.value,
                                                   "phone_number": payload.phone_number,
                                                   "therapist_id": payload.therapist_id,
                                                   "consentment_channel": payload.consentment_channel.value,
                                               })
            patient_id = response.dict()['data'][0]['id']

            if len(payload.pre_existing_history or '') > 0:
                await vector_writer.insert_preexisting_history_vectors(index_id=payload.therapist_id,
                                                                       namespace=patient_id,
                                                                       text=payload.pre_existing_history,
                                                                       auth_manager=auth_manager,
                                                                       openai_manager=openai_manager,
                                                                       session_id=session_id)

            return patient_id
        except Exception as e:
            raise Exception(e)

    async def update_patient(self,
                             auth_manager: AuthManager,
                             payload: PatientUpdatePayload,
                             session_id: str,
                             openai_manager: OpenAIBaseClass,
                             supabase_manager: SupabaseBaseClass):
        patient_query = supabase_manager.select(fields="*",
                                                filters={
                                                    'id': payload.patient_id,
                                                    'therapist_id': payload.therapist_id
                                                },
                                                table_name="patients")
        assert (0 != len((patient_query).data)), "There isn't a patient-therapist match with the incoming ids."
        current_pre_existing_history = patient_query.dict()['data'][0]['pre_existing_history']

        supabase_manager.update(table_name="patients",
                                payload={
                                    "first_name": payload.first_name,
                                    "middle_name": payload.middle_name,
                                    "last_name": payload.last_name,
                                    "birth_date": payload.birth_date,
                                    "pre_existing_history": payload.pre_existing_history,
                                    "email": payload.email,
                                    "gender": payload.gender.value,
                                    "phone_number": payload.phone_number,
                                    "consentment_channel": payload.consentment_channel.value,
                                },
                                filters={
                                    'id': payload.patient_id
                                })

        if len(payload.pre_existing_history or '') > 0 and payload.pre_existing_history != current_pre_existing_history:
            await vector_writer.update_preexisting_history_vectors(index_id=payload.therapist_id,
                                                                   namespace=payload.patient_id,
                                                                   text=payload.pre_existing_history,
                                                                   session_id=session_id,
                                                                   openai_manager=openai_manager,
                                                                   auth_manager=auth_manager)

    async def adapt_session_notes_to_soap(self,
                                          auth_manager: AuthManager,
                                          openai_manager: OpenAIBaseClass,
                                          therapist_id: str,
                                          session_notes_text: str,
                                          session_id: str) -> str:
        try:
            soap_report = await VectorQueryWorker().create_soap_report(text=session_notes_text,
                                                                       therapist_id=therapist_id,
                                                                       auth_manager=auth_manager,
                                                                       openai_manager=openai_manager,
                                                                       session_id=session_id)
            return soap_report
        except Exception as e:
            raise Exception(e)

    def delete_all_data_for_patient(self,
                                    therapist_id: str,
                                    patient_id: str):
        try:
            vector_writer.delete_session_vectors(index_id=therapist_id, namespace=patient_id)
            vector_writer.delete_preexisting_history_vectors(index_id=therapist_id, namespace=patient_id)
        except Exception as e:
            # Index doesn't exist, failing silently. Patient may have been queued for deletion prior to having any
            # data in our vector db
            pass

    def delete_all_sessions_for_therapist(self, id: str):
        try:
            vector_writer.delete_index(id)
        except Exception as e:
            raise Exception(e)

    async def query_session(self,
                            auth_manager: AuthManager,
                            query: AssistantQuery,
                            session_id: str,
                            api_method: str,
                            endpoint_name: str,
                            environment: str,
                            openai_manager: OpenAIBaseClass,
                            supabase_manager: SupabaseBaseClass):
        try:
            # Confirm that the incoming patient id is assigned to the incoming therapist id.
            patient_query = supabase_manager.select(fields="*",
                                                    filters={
                                                        'id': query.patient_id,
                                                        'therapist_id': query.therapist_id
                                                    },
                                                    table_name="patients")
            patient_therapist_match = (0 != len((patient_query).data))
            assert patient_therapist_match, "There isn't a patient-therapist match with the incoming ids."

            patient_query_dict = patient_query.dict()
            patient_first_name = patient_query_dict['data'][0]['first_name']
            patient_last_name = patient_query_dict['data'][0]['last_name']
            patient_gender = patient_query_dict['data'][0]['gender']
            patient_last_session_date = patient_query_dict['data'][0]['last_session_date']

            if len(patient_last_session_date or '') > 0:
                session_date_override = IncludeSessionDateOverride(output_prefix_override="*** The following data is from the patient's last session with the therapist ***\n",
                                                                    output_suffix_override="*** End of data associated with the patient's last session with the therapist ***",
                                                                    session_date=patient_last_session_date)
            else:
                session_date_override = None

            therapist_query = supabase_manager.select(fields="*",
                                                      filters={
                                                          'id': query.therapist_id
                                                      },
                                                      table_name="therapists")
            assert (0 != len((therapist_query).data))
            language_code = therapist_query.dict()['data'][0]["language_preference"]

            vector_query_worker = VectorQueryWorker()
            async for part in vector_query_worker.query_store(index_id=query.therapist_id,
                                                              namespace=query.patient_id,
                                                              patient_name=(" ".join([patient_first_name, patient_last_name])),
                                                              patient_gender=patient_gender,
                                                              query_input=query.text,
                                                              response_language_code=language_code,
                                                              session_id=session_id,
                                                              endpoint_name=endpoint_name,
                                                              method=api_method,
                                                              environment=environment,
                                                              auth_manager=auth_manager,
                                                              openai_manager=openai_manager,
                                                              session_date_override=session_date_override):
                yield part
        except Exception as e:
            raise Exception(e)

    async def fetch_todays_greeting(self,
                                    client_tz_identifier: str,
                                    therapist_id: str,
                                    session_id: str,
                                    endpoint_name: str,
                                    api_method: str,
                                    environment: str,
                                    openai_manager: OpenAIBaseClass,
                                    auth_manager: AuthManager,
                                    supabase_manager: SupabaseBaseClass) -> str:
        try:
            therapist_query = supabase_manager.select(fields="*",
                                                      filters={
                                                          'id': therapist_id
                                                      },
                                                      table_name="therapists")
            assert (0 != len((therapist_query).data)), "No user was found with the incoming id"

            therapist_query_dict = therapist_query.dict()
            addressing_name = therapist_query_dict['data'][0]["first_name"]
            language_code = therapist_query_dict['data'][0]["language_preference"]
            therapist_gender = therapist_query_dict['data'][0]["gender"]
            result = await VectorQueryWorker().create_greeting(therapist_name=addressing_name,
                                                               therapist_gender=therapist_gender,
                                                               language_code=language_code,
                                                               tz_identifier=client_tz_identifier,
                                                               session_id=session_id,
                                                               endpoint_name=endpoint_name,
                                                               therapist_id=therapist_id,
                                                               method=api_method,
                                                               environment=environment,
                                                               openai_manager=openai_manager,
                                                               auth_manager=auth_manager)
            return result
        except Exception as e:
            raise Exception(e)

    async def fetch_question_suggestions(self,
                                         therapist_id: str,
                                         patient_id: str,
                                         auth_manager: AuthManager,
                                         environment: str,
                                         session_id: str,
                                         endpoint_name: str,
                                         api_method: str,
                                         openai_manager: OpenAIBaseClass,
                                         supabase_manager: SupabaseBaseClass):
        try:
            therapist_query = supabase_manager.select(fields="*",
                                                   table_name="therapists",
                                                   filters={
                                                       'id': therapist_id
                                                   })
            assert (0 != len((therapist_query).data)), "Did not find any store data for incoming user."

            language_code = therapist_query.dict()['data'][0]["language_preference"]
            patient_query = supabase_manager.select(fields="*",
                                                    table_name="patients",
                                                    filters={
                                                        'therapist_id': therapist_id,
                                                        'id': patient_id
                                                    })
            assert (0 != len((patient_query).data)), "There isn't a patient-therapist match with the incoming ids."

            patient_query_dict = patient_query.dict()
            patient_first_name = patient_query_dict['data'][0]['first_name']
            patient_last_name = patient_query_dict['data'][0]['last_name']
            patient_gender = patient_query_dict['data'][0]['gender']

            response = await VectorQueryWorker().create_question_suggestions(language_code=language_code,
                                                                             session_id=session_id,
                                                                             endpoint_name=endpoint_name,
                                                                             index_id=therapist_id,
                                                                             namespace=patient_id,
                                                                             method=api_method,
                                                                             environment=environment,
                                                                             auth_manager=auth_manager,
                                                                             openai_manager=openai_manager,
                                                                             patient_name=(" ".join([patient_first_name, patient_last_name])),
                                                                             patient_gender=patient_gender)

            assert 'questions' in response, "Something went wrong in generating a response. Please try again"
            return response
        except Exception as e:
            raise Exception(e)

    async def update_diarization_with_notification_data(self,
                                                        auth_manager: AuthManager,
                                                        supabase_manager: SupabaseBaseClass,
                                                        openai_manager: OpenAIBaseClass,
                                                        job_id: str,
                                                        diarization_summary: str,
                                                        diarization: str) -> str:
        try:
            now_timestamp = datetime.now().strftime(datetime_handler.DATE_TIME_FORMAT)

            session_query = supabase_manager.select(fields="*",
                                                    filters={
                                                        'diarization_job_id': job_id
                                                    },
                                                    table_name="session_reports")
            session_query_dict = session_query.dict()
            therapist_id = session_query_dict['data'][0]['therapist_id']
            patient_id = session_query_dict['data'][0]['patient_id']
            template = session_query_dict['data'][0]['diarization_template']
            session_date_raw = session_query_dict['data'][0]['session_date']
            session_date_formatted = datetime_handler.convert_to_internal_date_format(session_date_raw)

            session_id_query = supabase_manager.select(fields="*",
                                                       filters={
                                                           'job_id': job_id
                                                       },
                                                       table_name="diarization_logs")
            assert (0 != len((session_id_query).data)), "Expected to find a response."
            session_id = session_id_query.dict()['data'][0]['session_id']

            patient_query = supabase_manager.select(fields="*",
                                                    filters={
                                                        'id': patient_id,
                                                        'therapist_id': therapist_id
                                                    },
                                                    table_name="patients")
            assert (0 != len((patient_query).data))
            therapist_query = supabase_manager.select(fields="*",
                                                      filters={
                                                          'id': therapist_id
                                                      },
                                                      table_name="therapists")
            assert (0 != len((therapist_query).data))
            language_code = therapist_query.dict()['data'][0]["language_preference"]
            mini_summary = await VectorQueryWorker().create_session_mini_summary(session_notes=diarization_summary,
                                                                                 therapist_id=therapist_id,
                                                                                 language_code=language_code,
                                                                                 auth_manager=auth_manager,
                                                                                 openai_manager=openai_manager,
                                                                                 session_id=session_id)

            patient_query_dict = patient_query.dict()
            patient_last_session_date = patient_query_dict['data'][0]['last_session_date']

            # Determine the updated value for last_session_date depending on if the patient
            # has met with the therapist before or not.
            if patient_last_session_date is None:
                patient_last_session_date = session_date_formatted
            else:
                patient_last_session_date = datetime_handler.retrieve_most_recent_date(session_date_formatted,
                                                                                       datetime_handler.convert_to_internal_date_format(patient_last_session_date))

            supabase_manager.update(table_name="patients",
                                    payload={
                                        "last_session_date": patient_last_session_date,
                                        "total_sessions": (1 + (patient_query_dict['data'][0]['total_sessions'])),
                                    },
                                    filters={
                                        'id': patient_id
                                    })

            if template == SessionNotesTemplate.SOAP.value:
                soap_notes = await self.adapt_session_notes_to_soap(auth_manager=auth_manager,
                                                                    openai_manager=openai_manager,
                                                                    therapist_id=therapist_id,
                                                                    session_notes_text=diarization_summary,
                                                                    session_id=session_id)
                supabase_manager.update(table_name="session_reports",
                                        payload={
                                            "notes_text": soap_notes,
                                            "notes_mini_summary": mini_summary,
                                            "diarization_summary": diarization_summary,
                                            "diarization": diarization,
                                            "last_updated": now_timestamp,
                                        },
                                        filters={
                                            'diarization_job_id': job_id
                                        })
            else:
                assert template == SessionNotesTemplate.FREE_FORM.value, f"Unexpected template: {template}"
                supabase_manager.update(table_name="session_reports",
                                        payload={
                                            "notes_text": diarization_summary,
                                            "notes_mini_summary": mini_summary,
                                            "diarization_summary": diarization_summary,
                                            "diarization": diarization,
                                            "last_updated": now_timestamp,
                                        },
                                        filters={
                                            'diarization_job_id': job_id
                                        })

            await vector_writer.insert_session_vectors(index_id=therapist_id,
                                                       namespace=patient_id,
                                                       text=diarization_summary,
                                                       therapy_session_date=session_date_formatted,
                                                       auth_manager=auth_manager,
                                                       openai_manager=openai_manager,
                                                       session_id=session_id)
            return session_id
        except Exception as e:
            raise Exception(e)

    async def create_patient_summary(self,
                                     therapist_id: str,
                                     patient_id: str,
                                     auth_manager: AuthManager,
                                     environment: str,
                                     session_id: str,
                                     endpoint_name: str,
                                     api_method: str,
                                     openai_manager: OpenAIBaseClass,
                                     supabase_manager: SupabaseBaseClass):
        try:
            patient_query = supabase_manager.select(fields="*",
                                                    filters={
                                                        'therapist_id': therapist_id,
                                                        'id': patient_id
                                                    },
                                                    table_name="patients")
            assert (0 != len((patient_query).data)), "There isn't a patient-therapist match with the incoming ids."

            patient_response_dict = patient_query.dict()
            patient_name = patient_response_dict['data'][0]['first_name']
            patient_gender = patient_response_dict['data'][0]['gender']
            last_session_date = patient_response_dict['data'][0]['last_session_date']
            session_number = 1 + patient_response_dict['data'][0]['total_sessions']

            therapist_query = supabase_manager.select(fields="*",
                                                      filters={
                                                          "id": therapist_id
                                                      },
                                                      table_name="therapists")
            therapist_response_dict = therapist_query.dict()
            therapist_name = therapist_response_dict['data'][0]['first_name']
            language_code = therapist_response_dict['data'][0]['language_preference']
            therapist_gender = therapist_response_dict['data'][0]['gender']

            if len(last_session_date or '') > 0:
                session_date_override = IncludeSessionDateOverride(output_prefix_override="*** The following data is from the patient's last session with the therapist ***\n",
                                                                   output_suffix_override="*** End of data associated with the patient's last session with the therapist ***",
                                                                   session_date=last_session_date)
            else:
                session_date_override = None

            vector_query_worker = VectorQueryWorker()
            result = await vector_query_worker.create_briefing(index_id=therapist_id,
                                                               namespace=patient_id,
                                                               environment=environment,
                                                               language_code=language_code,
                                                               session_id=session_id,
                                                               endpoint_name=endpoint_name,
                                                               method=api_method,
                                                               patient_name=patient_name,
                                                               patient_gender=patient_gender,
                                                               therapist_name=therapist_name,
                                                               therapist_gender=therapist_gender,
                                                               session_number=session_number,
                                                               auth_manager=auth_manager,
                                                               openai_manager=openai_manager,
                                                               session_date_override=session_date_override)

            assert 'summary' in result, "Something went wrong in generating a response. Please try again"
            return result
        except Exception as e:
            raise Exception(e)

    async def fetch_frequent_topics(self,
                                    therapist_id: str,
                                    patient_id: str,
                                    auth_manager: AuthManager,
                                    environment: str,
                                    session_id: str,
                                    endpoint_name: str,
                                    api_method: str,
                                    openai_manager: OpenAIBaseClass,
                                    supabase_manager: SupabaseBaseClass):
        try:
            therapist_query = supabase_manager.select(fields="*",
                                                      filters={
                                                          'id': therapist_id
                                                      },
                                                      table_name="therapists")
            assert (0 != len((therapist_query).data)), "Did not find any store data for incoming user."

            language_code = therapist_query.dict()['data'][0]["language_preference"]
            patient_query = supabase_manager.select(fields="*",
                                                    filters={
                                                        'therapist_id': therapist_id,
                                                        'id': patient_id
                                                    },
                                                    table_name="patients")
            assert (0 != len((patient_query).data)), "There isn't a patient-therapist match with the incoming ids."

            patient_query_dict = patient_query.dict()
            patient_first_name = patient_query_dict['data'][0]['first_name']
            patient_last_name = patient_query_dict['data'][0]['last_name']
            patient_gender = patient_query_dict['data'][0]['gender']

            response = await VectorQueryWorker().fetch_frequent_topics(language_code=language_code,
                                                                       session_id=session_id,
                                                                       endpoint_name=endpoint_name,
                                                                       index_id=therapist_id,
                                                                       namespace=patient_id,
                                                                       method=api_method,
                                                                       environment=environment,
                                                                       openai_manager=openai_manager,
                                                                       auth_manager=auth_manager,
                                                                       patient_name=(" ".join([patient_first_name, patient_last_name])),
                                                                       patient_gender=patient_gender)

            error_message = "Something went wrong in generating a response. Please try again"
            assert 'topics' in response, error_message
            return response
        except Exception as e:
            raise Exception(e)
