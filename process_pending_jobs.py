import os, time
import uuid

from datetime import datetime, timedelta
from fastapi import BackgroundTasks

from app.internal.dependency_container import dependency_container
from app.internal.utilities.datetime_handler import DATE_FORMAT_YYYY_MM_DD
from app.managers.assistant_manager import AssistantManager
from app.managers.audio_processing_manager import AudioProcessingManager
from app.managers.auth_manager import AuthManager

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

assistant_manager = AssistantManager()
audio_processing_manager = AudioProcessingManager()
auth_manager = AuthManager()

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
        supabase_client.delete_file(source_bucket=AUDIO_FILES_PROCESSING_COMPLETED_BUCKET,
                                    storage_filepath=job_file_path)

        supabase_client.delete(table_name=PENDING_AUDIO_JOBS_TABLE_NAME,
                               filters={"id": job["id"]})

async def _process_pending_audio_job(job: dict) -> bool:
    """
    This function processes a single pending audio job.
    It downloads the audio file, processes it, and then updates the respective session entry.
    If processing is successful, the job is also marked as processed in the database.

    Arguments:
        job: A dictionary representing a pending audio job.
    """
    local_temp_file = None
    for attempt_index in range(0, RETRY_ATTEMPTS):
        try:
            supabase_client = dependency_container.inject_supabase_client_factory().supabase_admin_client()
            storage_filepath = job["storage_filepath"]
            file_extension = os.path.splitext(storage_filepath)[1].lower()
            local_temp_file = "".join(["temp_file", file_extension])
            response = supabase_client.download_file(source_bucket=AUDIO_FILES_PROCESSING_PENDING_BUCKET,
                                                     storage_filepath=storage_filepath)

            assert response.status_code == 200, f"Failed to download file: {response.json()}"

            # Save the file locally
            with open(local_temp_file, "wb") as temp_file:
                temp_file.write(response.content)

            therapist_query = supabase_client.select(table_name=THERAPISTS_TABLE_NAME,
                                                     filters={"id": job["therapist_id"]})
            assert (0 != len((therapist_query).data)), "Something went wrong when querying the therapist data."

            therapist_query_dict = therapist_query.model_dump()['data'][0]
            language_code = therapist_query_dict["language_preference"]

            session_report_query = supabase_client.select(table_name=SESSION_REPORTS_TABLE_NAME,
                                                          filters={"id": job["session_report_id"]})
            assert (0 != len((session_report_query).data)), "Something went wrong when querying the session report."

            session_report_query_dict = session_report_query.model_dump()['data'][0]
            is_diarization_job = job["job_type"] == DIARIZATION_KEY
            audio_processing_manager.transcribe_audio_file(background_tasks=BackgroundTasks(),
                                                        auth_manager=auth_manager,
                                                        assistant_manager=assistant_manager,
                                                        supabase_client=supabase_client,
                                                        template=session_report_query_dict["template"],
                                                        therapist_id=job["therapist_id"],
                                                        session_id=uuid.uuid4(),
                                                        language_code=language_code,
                                                        patient_id=session_report_query_dict["patient_id"],
                                                        session_date=session_report_query_dict["session_date"],
                                                        environment=job["environment"],
                                                        audio_file=local_temp_file,
                                                        diarize=is_diarization_job)
            return True
        except Exception:
            pass
        finally:
            # Ensure the local temporary file is deleted
            if os.path.exists(local_temp_file):
                os.remove(local_temp_file)

        # If the job failed, retry the job with an exponential backoff
        backoff_in_minutes = min(5 ** attempt_index, 15)
        time.sleep(backoff_in_minutes / 60)

    # If the job failed after all retries, return False
    return False

async def _attempt_processing_job_batch(batch: list[dict]):
    """
    This function processes a batch of pending audio jobs.
    It iterates through each job in the batch and attempts to process it.
    If processing is successful, the job is marked as processed in the database.

    Arguments:
        batch: A list of dictionaries, where each dictionary represents a pending audio job.
    """
    supabase_client = dependency_container.inject_supabase_client_factory().supabase_admin_client()
    for job in batch:
        assert job[SUCCESSFUL_PROCESSING_DATE_KEY] == None, "Job has already been processed."

        succeeded = await _process_pending_audio_job(job)
        if succeeded:
            supabase_client.update(table_name=PENDING_AUDIO_JOBS_TABLE_NAME,
                                   payload={
                                       SUCCESSFUL_PROCESSING_DATE_KEY: datetime.now().strftime(DATE_FORMAT_YYYY_MM_DD)
                                   },
                                   filters={"id": job["id"]})

            supabase_client.move_file_between_buckets(source_bucket=AUDIO_FILES_PROCESSING_PENDING_BUCKET,
                                                      destination_bucket=AUDIO_FILES_PROCESSING_COMPLETED_BUCKET,
                                                      file_path=job["storage_filepath"])

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
    response = supabase_client.select_batch_where_is_not_null(table_name=PENDING_AUDIO_JOBS_TABLE_NAME,
                                                              fields="*",
                                                              non_null_column=SUCCESSFUL_PROCESSING_DATE_KEY,
                                                              limit=BATCH_LIMIT)
    batch = response.data

    # Continue fetching while the batch has exactly `BATCH_LIMIT` items
    while batch and len(batch) == BATCH_LIMIT:
        # Process the current batch
        await _attempt_processing_job_batch(batch)

        # Fetch the next batch
        response = supabase_client.select_batch_where_is_not_null(table_name=PENDING_AUDIO_JOBS_TABLE_NAME,
                                                                  fields="*",
                                                                  non_null_column=SUCCESSFUL_PROCESSING_DATE_KEY,
                                                                  limit=BATCH_LIMIT)
        batch = response.data

    # Process the final batch if it has fewer than LIMIT items
    if batch:
        _attempt_processing_job_batch(batch)

if __name__ == "__main__":
    purge_completed_audio_jobs()
    process_pending_audio_jobs()

    exit()
