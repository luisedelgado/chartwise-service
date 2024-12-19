import os
import uuid

from datetime import datetime, timedelta
from fastapi import BackgroundTasks
from supabase import Client

from app.internal.dependency_container import dependency_container
from app.internal.utilities.datetime_handler import DATE_FORMAT_YYYY_MM_DD
from app.managers.assistant_manager import AssistantManager
from app.managers.audio_processing_manager import AudioProcessingManager
from app.managers.auth_manager import AuthManager

BATCH_LIMIT = 10
RETENTION_POLICY_DAYS = 7
DIARIZATION_KEY = "diarization"
TRANSCRIPTION_KEY = "transcription"
SESSION_REPORTS_TABLE_NAME = "session_reports"
THERAPISTS_TABLE_NAME = "therapists"
PENDING_AUDIO_JOBS_TABLE_NAME = "pending_audio_jobs"
AUDIO_FILES_PROCESSING_PENDING_BUCKET = "session-audio-files-processing-pending"
AUDIO_FILES_PROCESSING_COMPLETED_BUCKET = "session-audio-files-processing-completed"
SUCCESSFUL_PROCESSING_DATE_KEY = "successful_processing_date"

assistant_manager = AssistantManager()
audio_processing_manager = AudioProcessingManager()
auth_manager = AuthManager()

def _move_file_between_buckets(source_bucket: str,
                               destination_bucket: str,
                               file_path: str):
    """
    Move a file from one Supabase bucket to another.

    :param source_bucket: The name of the source bucket.
    :param destination_bucket: The name of the destination bucket.
    :param file_path: Path to the file in the source bucket.
    """
    supabase_client: Client = dependency_container.inject_supabase_client_factory().supabase_admin_client()

    try:
        # Step 1: Download the file from the source bucket
        print("Downloading file from source bucket...")
        response = supabase_client.storage.from_(source_bucket).download(file_path)
        
        if response.status_code != 200:
            raise Exception(f"Failed to download file: {response.json()}")

        file_content = response.content

        # Step 2: Upload the file to the destination bucket
        print("Uploading file to destination bucket...")
        upload_response = supabase_client.storage.from_(destination_bucket).upload(file_path, file_content)

        if upload_response.status_code not in [200, 204]:
            raise Exception(f"Failed to upload file: {upload_response.json()}")

        # Step 3: Delete the file from the source bucket
        print("Deleting file from source bucket...")
        delete_response = supabase_client.storage.from_(source_bucket).remove([file_path])
        
        if delete_response.status_code != 200:
            raise Exception(f"Failed to delete file: {delete_response.json()}")

        print("File successfully moved!")
    except Exception as e:
        print(f"Error during file move: {e}")

def _delete_completed_audio_jobs_in_batch(batch: list[dict]):
    supabase_client: Client = dependency_container.inject_supabase_client_factory().supabase_admin_client()
    for job in batch:
        job_dict = job.dict()
        succesful_processing_date = datetime.strptime(job[SUCCESSFUL_PROCESSING_DATE_KEY], DATE_FORMAT_YYYY_MM_DD)

        # Check whether the retention policy has been met. Because the query is sorting dates in descending order,
        # we can return early as soon as we hit the first date that is within the retention policy.
        date_plus_seven_days = succesful_processing_date + timedelta(days=RETENTION_POLICY_DAYS)
        if date_plus_seven_days < datetime.now():
            break

        # Delete the object
        job_file_path = job_dict["file_path"]
        response = supabase_client.storage.from_(AUDIO_FILES_PROCESSING_COMPLETED_BUCKET).remove([job_file_path])

        # Check response
        if response["error"]:
            print("Error deleting file:", response["error"])
            continue

        delete_operation = supabase_client.table(PENDING_AUDIO_JOBS_TABLE_NAME).delete().eq(f"id", job_dict["id"]).execute()
        print(delete_operation)

async def _process_pending_audio_job(job: dict) -> bool:
    local_temp_file = None
    try:
        supabase_client: Client = dependency_container.inject_supabase_client_factory().supabase_admin_client()
        storage_filepath = job["storage_filepath"]
        file_extension = os.path.splitext(storage_filepath)[1].lower()
        local_temp_file = "".join(["temp_file", file_extension])
        response = supabase_client.storage.from_(PENDING_AUDIO_JOBS_TABLE_NAME).download(storage_filepath)

        assert response.status_code == 200, f"Failed to download file: {response.json()}"

        # Save the file locally
        with open(local_temp_file, "wb") as temp_file:
            temp_file.write(response.content)

        therapist_query = supabase_client.from_(THERAPISTS_TABLE_NAME).select("*").eq(f"id", f"{job["therapist_id"]}").execute()
        assert (0 != len((therapist_query).data)), "Something went wrong when querying the therapist data."

        therapist_query_dict = therapist_query.model_dump()['data'][0]
        language_code = therapist_query_dict["language_preference"]

        session_report_query = supabase_client.from_(SESSION_REPORTS_TABLE_NAME).select("*").eq(f"id", f"{job["session_report_id"]}").execute()
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
    except Exception as e:
        return False
    finally:
        # Ensure the local temporary file is deleted
        if os.path.exists(local_temp_file):
            os.remove(local_temp_file)

async def _attempt_processing_job_batch(batch: list[dict]):
    supabase_client: Client = dependency_container.inject_supabase_client_factory().supabase_admin_client()
    for job in batch:
        job_dict = job.dict()
        assert job_dict[SUCCESSFUL_PROCESSING_DATE_KEY] == None, "Job has already been processed."

        succeeded = await _process_pending_audio_job(job_dict)
        if succeeded:
            supabase_client.table(PENDING_AUDIO_JOBS_TABLE_NAME).update({
                SUCCESSFUL_PROCESSING_DATE_KEY: datetime.now().strftime(DATE_FORMAT_YYYY_MM_DD)
            }).eq("id", f"{job["id"]}").execute()

            _move_file_between_buckets(source_bucket=AUDIO_FILES_PROCESSING_PENDING_BUCKET,
                                       destination_bucket=AUDIO_FILES_PROCESSING_COMPLETED_BUCKET,
                                       file_path=job_dict["storage_filepath"])

def purge_completed_audio_jobs():
    supabase_client: Client = dependency_container.inject_supabase_client_factory().supabase_admin_client()
    offset = 0

    # Initial fetch
    response = supabase_client.table(PENDING_AUDIO_JOBS_TABLE_NAME).select("*").range(offset, offset + BATCH_LIMIT - 1).not_.is_(SUCCESSFUL_PROCESSING_DATE_KEY, "null").order(SUCCESSFUL_PROCESSING_DATE_KEY, desc=False).execute()
    batch = response.data

    # Continue fetching while the batch has exactly `BATCH_LIMIT` items
    while batch and len(batch) == BATCH_LIMIT:
        # Process the current batch
        _delete_completed_audio_jobs_in_batch(batch)

        # Update offset
        offset += BATCH_LIMIT

        # Fetch the next batch
        response = supabase_client.table(PENDING_AUDIO_JOBS_TABLE_NAME).select("*").range(offset, offset + BATCH_LIMIT - 1).not_.is_(SUCCESSFUL_PROCESSING_DATE_KEY, "null").order(SUCCESSFUL_PROCESSING_DATE_KEY, desc=False).execute()
        batch = response.data

    # Process the final batch if it has fewer than LIMIT items
    if batch:
        _delete_completed_audio_jobs_in_batch(batch)

async def process_pending_audio_jobs():
    supabase_client: Client = dependency_container.inject_supabase_client_factory().supabase_admin_client()
    
    offset = 0

    # Initial fetch
    response = supabase_client.table(PENDING_AUDIO_JOBS_TABLE_NAME).select("*").range(offset, offset + BATCH_LIMIT - 1).execute()
    batch = response.data

    # Continue fetching while the batch has exactly `BATCH_LIMIT` items
    while batch and len(batch) == BATCH_LIMIT:
        # Process the current batch
        await _attempt_processing_job_batch(batch)

        # Update offset
        offset += BATCH_LIMIT

        # Fetch the next batch
        response = supabase_client.table(PENDING_AUDIO_JOBS_TABLE_NAME).select("*").range(offset, offset + BATCH_LIMIT - 1).execute()
        batch = response.data

    # Process the final batch if it has fewer than LIMIT items
    if batch:
        _attempt_processing_job_batch(batch)

if __name__ == "__main__":
    purge_completed_audio_jobs()
    process_pending_audio_jobs()

    exit()
