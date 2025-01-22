import asyncio, os, sys, time
import uuid

from datetime import datetime, timedelta
from fastapi import BackgroundTasks

from app.dependencies.api.templates import SessionNotesTemplate
from app.dependencies.dependency_container import dependency_container
from app.internal.internal_alert import MediaJobProcessingAlert
from app.internal.schemas import MediaType
from app.internal.utilities.datetime_handler import (convert_to_date_format_mm_dd_yyyy,
                                                     DATE_FORMAT_YYYY_MM_DD,
                                                     DATE_TIME_FORMAT)
from app.managers.assistant_manager import AssistantManager
from app.managers.audio_processing_manager import AudioProcessingManager
from app.managers.auth_manager import AuthManager
from app.managers.email_manager import EmailManager

BATCH_LIMIT = 10
RETENTION_POLICY_DAYS = 7
RETRY_ATTEMPTS = 3
DIARIZATION_KEY = "diarization"
TRANSCRIPTION_KEY = "transcription"
ENVIRONMENT_KEY = "environment"
SESSION_REPORTS_TABLE_NAME = "session_reports"
THERAPISTS_TABLE_NAME = "therapists"
PENDING_AUDIO_JOBS_TABLE_NAME = "pending_audio_jobs"
AUDIO_FILES_PROCESSING_PENDING_BUCKET = "session-audio-files-processing-pending"
AUDIO_FILES_PROCESSING_COMPLETED_BUCKET = "session-audio-files-processing-completed"
SUCCESSFUL_PROCESSING_DATE_KEY = "successful_processing_date"

class BackgroundTasksContainer:
    def __init__(self):
        self.tasks = []

    def add_task(self, func, *args, **kwargs):
        task = asyncio.create_task(func(*args, **kwargs))
        self.tasks.append(task)

    async def wait_for_all(self):
        """Wait for all background tasks to finish."""
        if self.tasks:
            await asyncio.gather(*self.tasks)

assistant_manager = AssistantManager()
audio_processing_manager = AudioProcessingManager()
auth_manager = AuthManager()
email_manager = EmailManager()
background_tasks_container = BackgroundTasksContainer()
files_to_delete = []

def _delete_completed_audio_jobs_in_batch(batch: list[dict]):
    """
    This function deletes completed audio jobs in a batch.
    It iterates through each job in the batch and deletes the respective file from the storage bucket.

    Arguments:
        batch: A list of dictionaries, where each dictionary represents a completed audio job.
    """
    supabase_client = dependency_container.inject_supabase_client_factory().supabase_admin_client()
    for job in batch:
        succesful_processing_date = datetime.strptime(job[SUCCESSFUL_PROCESSING_DATE_KEY], DATE_FORMAT_YYYY_MM_DD)

        # Check whether the retention policy has been met. Because the query is sorting dates in descending order,
        # we can return early as soon as we hit the first date that is within the retention policy.
        date_plus_seven_days = succesful_processing_date + timedelta(days=RETENTION_POLICY_DAYS)
        if date_plus_seven_days < datetime.now():
            break

        # Delete the object
        job_file_path = job["storage_filepath"]
        supabase_client.storage_client.delete_file(source_bucket=AUDIO_FILES_PROCESSING_COMPLETED_BUCKET,
                                                   storage_filepath=job_file_path)

        supabase_client.delete(table_name=PENDING_AUDIO_JOBS_TABLE_NAME,
                               filters={"id": job["id"]})

async def _process_pending_audio_job(job: dict):
    """
    This function processes a single pending audio job.
    It downloads the audio file, processes it, and then updates the respective session entry.
    If processing is successful, the job is also marked as processed in the database.

    Arguments:
        job: A dictionary representing a pending audio job.
    """
    local_temp_file = None
    supabase_client = dependency_container.inject_supabase_client_factory().supabase_admin_client()
    for attempt_index in range(0, RETRY_ATTEMPTS):
        try:
            storage_filepath = job["storage_filepath"]
            file_extension = os.path.splitext(storage_filepath)[1].lower()
            local_temp_file = "".join(["temp_file", file_extension])
            response = supabase_client.storage_client.download_file(source_bucket=AUDIO_FILES_PROCESSING_PENDING_BUCKET,
                                                                    storage_filepath=storage_filepath)

            # Save the file locally
            with open(local_temp_file, "wb") as temp_file:
                temp_file.write(response)

            files_to_delete.append(local_temp_file)
            therapist_query = supabase_client.select(table_name=THERAPISTS_TABLE_NAME,
                                                     fields="*",
                                                     filters={"id": job["therapist_id"]})
            assert (0 != len((therapist_query).data)), "Something went wrong when querying the therapist data."

            therapist_query_dict = therapist_query.model_dump()['data'][0]
            language_code = therapist_query_dict["language_preference"]

            old_session_report_id = job["session_report_id"]
            old_storage_filepath = job["storage_filepath"]
            session_report_query = supabase_client.select(table_name=SESSION_REPORTS_TABLE_NAME,
                                                          fields="*",
                                                          filters={"id": old_session_report_id})
            assert (0 != len((session_report_query).data)), "Something went wrong when querying the session report."

            session_report_query_dict = session_report_query.model_dump()['data'][0]
            is_diarization_job = job["job_type"] == DIARIZATION_KEY

            background_tasks = BackgroundTasks()
            background_tasks_container.add_task(background_tasks)

            formatted_session_date = convert_to_date_format_mm_dd_yyyy(incoming_date=session_report_query_dict["session_date"],
                                                                       incoming_date_format=DATE_FORMAT_YYYY_MM_DD)
            new_session_report_id = await audio_processing_manager.transcribe_audio_file(background_tasks=background_tasks,
                                                                                         auth_manager=auth_manager,
                                                                                         assistant_manager=assistant_manager,
                                                                                         supabase_client=supabase_client,
                                                                                         template=SessionNotesTemplate(session_report_query_dict["template"]),
                                                                                         therapist_id=job["therapist_id"],
                                                                                         session_id=uuid.uuid4(),
                                                                                         language_code=language_code,
                                                                                         patient_id=session_report_query_dict["patient_id"],
                                                                                         session_date=formatted_session_date,
                                                                                         environment=job["environment"],
                                                                                         audio_file=local_temp_file,
                                                                                         diarize=is_diarization_job,
                                                                                         email_manager=email_manager)

            new_session_report_query = supabase_client.select(table_name=SESSION_REPORTS_TABLE_NAME,
                                                              fields="*",
                                                              filters={"id": new_session_report_id})
            assert (0 != len((new_session_report_query).data)), "Did not find a valid session report."
            assert new_session_report_query.dict()['data'][0]['processing_status'] != "failed", "Processing failed."

            # Processing succeeded. Delete the old session report entry, as well as the backing file.
            supabase_client.storage_client.delete_file(source_bucket=AUDIO_FILES_PROCESSING_PENDING_BUCKET,
                                                       storage_filepath=old_storage_filepath)
            supabase_client.delete(table_name=SESSION_REPORTS_TABLE_NAME,
                                   filters={"id": old_session_report_id})
            return

        except Exception as e:
            processing_retry_count = (1 + job["processing_retry_count"])
            supabase_client.update(payload={
                                       "processing_retry_count": processing_retry_count
                                   },
                                   filters={
                                       "id": job["id"],
                                   },
                                   table_name="pending_audio_jobs")
            alert = MediaJobProcessingAlert(description=f"Failed to process pending audio job with ID <b>{job["id"]}</b> in daily script.",
                                            media_type=MediaType.AUDIO,
                                            exception=e,
                                            environment=os.environ.get("ENVIRONMENT"),
                                            therapist_id=job["therapist_id"],
                                            storage_filepath=job["storage_filepath"],
                                            session_report_id=job["session_report_id"])
            await email_manager.send_internal_alert(alert)
            pass

        # If the job failed, retry the job with an exponential backoff
        backoff_in_minutes = min(5 ** attempt_index, 15)
        time.sleep(backoff_in_minutes / 60)

async def _attempt_processing_job_batch(batch: list[dict]):
    """
    This function processes a batch of pending audio jobs.
    It iterates through each job in the batch and attempts to process it.
    If processing is successful, the job is marked as processed in the database.

    Arguments:
        batch: A list of dictionaries, where each dictionary represents a pending audio job.
    """
    for job in batch:
        assert job[SUCCESSFUL_PROCESSING_DATE_KEY] == None, "Job has already been processed."

        await _process_pending_audio_job(job)

def purge_completed_audio_jobs():
    """
    This function purges completed audio jobs in batches of `BATCH_LIMIT` items.
    """
    supabase_client = dependency_container.inject_supabase_client_factory().supabase_admin_client()

    # Clean up job entries in Supabase table from non-prod environments, since those don't write to Supabase storage.
    supabase_client.delete_where_is_not(table_name=PENDING_AUDIO_JOBS_TABLE_NAME,
                                        is_not_filters={
                                            ENVIRONMENT_KEY: "prod"
                                        })

    # Initial fetch for pending prod jobs
    response = supabase_client.select_batch_where_is_not_null(table_name=PENDING_AUDIO_JOBS_TABLE_NAME,
                                                              fields="*",
                                                              non_null_column=SUCCESSFUL_PROCESSING_DATE_KEY,
                                                              limit=BATCH_LIMIT,
                                                              order_ascending_column=SUCCESSFUL_PROCESSING_DATE_KEY)
    batch = response.data

    # Continue fetching while the batch has exactly `BATCH_LIMIT` items
    while batch and len(batch) == BATCH_LIMIT:
        # Process the current batch
        _delete_completed_audio_jobs_in_batch(batch)

        # Fetch the next batch
        response = supabase_client.select_batch_where_is_not_null(table_name=PENDING_AUDIO_JOBS_TABLE_NAME,
                                                                  fields="*",
                                                                  non_null_column=SUCCESSFUL_PROCESSING_DATE_KEY,
                                                                  limit=BATCH_LIMIT,
                                                                  order_ascending_column=SUCCESSFUL_PROCESSING_DATE_KEY)
        batch = response.data

    # Process the final batch if it has fewer than LIMIT items
    if batch:
        _delete_completed_audio_jobs_in_batch(batch)

async def process_pending_audio_jobs():
    """
    This function processes pending audio jobs in batches of `BATCH_LIMIT` items.
    It fetches the first batch of items, processes them, and then fetches the next batch.
    This process continues until there are no more items to process.
    """
    supabase_client = dependency_container.inject_supabase_client_factory().supabase_admin_client()

    # Initial fetch
    response = supabase_client.select_batch_where_is_null(table_name=PENDING_AUDIO_JOBS_TABLE_NAME,
                                                          fields="*",
                                                          null_column=SUCCESSFUL_PROCESSING_DATE_KEY,
                                                          limit=BATCH_LIMIT)
    batch = response.data

    # Continue fetching while the batch has exactly `BATCH_LIMIT` items
    while batch and len(batch) == BATCH_LIMIT:
        # Process the current batch
        await _attempt_processing_job_batch(batch)

        # Fetch the next batch
        response = supabase_client.select_batch_where_is_null(table_name=PENDING_AUDIO_JOBS_TABLE_NAME,
                                                              fields="*",
                                                              null_column=SUCCESSFUL_PROCESSING_DATE_KEY,
                                                              limit=BATCH_LIMIT)
        batch = response.data

    # Process the final batch if it has fewer than LIMIT items
    if batch:
        await _attempt_processing_job_batch(batch)

    # Wait for all background tasks to finish to ensure all processing is complete
    await background_tasks_container.wait_for_all()

if __name__ == "__main__":
    start_timestamp = datetime.now().timestamp()
    start_timestamp_formatted = datetime.fromtimestamp(start_timestamp).strftime(DATE_TIME_FORMAT)

    supabase_client = dependency_container.inject_supabase_client_factory().supabase_admin_client()
    script_schedule_query = supabase_client.select(table_name="pending_audio_jobs_script_schedule",
                                                   fields="*",
                                                   filters={},
                                                   limit=1,
                                                   order_desc_column="run_start")
    script_schedule_query_dict = script_schedule_query.model_dump()['data']

    if (len(script_schedule_query_dict) > 0):
        last_run_datetime = datetime.fromisoformat(script_schedule_query_dict[0]['run_start'])
        now_datetime = datetime.now(last_run_datetime.tzinfo)

        # Check if the script has already ran today, if so, exit.
        try:
            assert last_run_datetime.date() < now_datetime.date()
        except Exception:
            sys.exit()

    try:
        purge_completed_audio_jobs()
        purge_completed_audio_jobs_success = True
        purge_completed_audio_jobs_exception = None
    except Exception as e:
        purge_completed_audio_jobs_success = False
        purge_completed_audio_jobs_exception = str(e)

    try:
        asyncio.run(process_pending_audio_jobs())
        process_pending_audio_jobs_success = True
        process_pending_audio_jobs_success_exception = None
    except Exception as e:
        process_pending_audio_jobs_result = False
        process_pending_audio_jobs_success_exception = str(e)

    for file in files_to_delete:
        if os.path.exists(file):
            os.remove(file)

    end_timestamp = datetime.now().timestamp()
    end_timestamp_formatted = datetime.fromtimestamp(end_timestamp).strftime(DATE_TIME_FORMAT)

    status = "success" if purge_completed_audio_jobs_success and process_pending_audio_jobs_success else "failed"
    supabase_client.insert(table_name="pending_audio_jobs_script_schedule",
                           payload={
                               "run_start": start_timestamp_formatted,
                               "run_end": end_timestamp_formatted,
                               "result": status,
                               "process_pending_audio_jobs_exception": process_pending_audio_jobs_success_exception,
                               "purge_completed_audio_jobs_exception": purge_completed_audio_jobs_exception
                           })

    sys.exit()
