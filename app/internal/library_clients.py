import asyncio, base64, datetime, json, os, requests, shutil, ssl, uuid

from deepgram import (
    DeepgramClient,
    PrerecordedOptions,
    FileSource,
)
from fastapi import (File, HTTPException, status, UploadFile)
from httpx import Timeout
from PIL import Image
from portkey_ai import PORTKEY_GATEWAY_URL, createHeaders
from pytz import timezone
from speechmatics.models import ConnectionSettings
from speechmatics.batch_client import BatchClient
from supabase import create_client, Client

from . import endpoints
from . import utilities

# Supabase

"""
Returns an active supabase instance based on a user's auth tokens.

Arguments:
access_token  – the access_token associated with a live supabase session.
refresh_token  – the refresh_token associated with a live supabase session.
"""
def supabase_user_instance(access_token, refresh_token) -> Client:
    key: str = os.environ.get("SUPABASE_ANON_KEY")
    url: str = os.environ.get("SUPABASE_URL")
    supabase: Client = create_client(url, key)
    supabase.auth.set_session(access_token=access_token,
                            refresh_token=refresh_token)
    return supabase

"""
Returns an active supabase instance with admin priviledges.
"""
def supabase_admin_instance() -> Client:
    key: str = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    url: str = os.environ.get("SUPABASE_URL")
    return create_client(url, key)

# Docupanda

"""
Uploads an image file to the DocuPanda service.
Returns an ID associated with the uploaded resource.
Arguments:
image  – the image to be uploaded.
"""
def docupanda_upload_image(image: UploadFile = File(...)) -> str:
    url = os.getenv("DOCUPANDA_URL")
    api_key = os.getenv("DOCUPANDA_API_KEY")
    file_name, file_extension = os.path.splitext(image.filename)

    # Format name to be used for image copy using current timestamp
    files_dir = 'app/files'
    pdf_extension = '.pdf'
    image_copy_bare_name = datetime.datetime.now().strftime("%d-%m-%Y-%H-%M-%S")
    image_copy_path = files_dir + '/' + image_copy_bare_name + file_extension
    image_copy_pdf_path = files_dir + '/' + image_copy_bare_name + pdf_extension
    files_to_clean = [image_copy_path]

    # Write incoming image to our local volume for further processing
    with open(image_copy_path, 'wb+') as buffer:
        shutil.copyfileobj(image.file, buffer)

    # Convert to PDF if necessary
    if file_extension.lower() != pdf_extension:
        Image.open(image_copy_path).convert('RGB').save(image_copy_pdf_path)
        files_to_clean.append(image_copy_pdf_path)

    if not os.path.exists(image_copy_pdf_path):
        os.remove(image_copy_path)
        raise Exception("Something went wrong while processing the image.")

    # Send to DocuPanda
    payload = {"document": {"file": {
        "contents": base64.b64encode(open(image_copy_pdf_path, 'rb').read()).decode(),
        "filename": file_name + pdf_extension
    }}}
    headers = {
        "accept": "application/json",
        "content-type": "application/json",
        "X-API-Key": api_key
    }

    response = requests.post(url, json=payload, headers=headers)

    # Clean up temp files
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(utilities.clean_up_files(files_to_clean))

    if response.status_code != status.HTTP_200_OK:
        raise HTTPException(status_code=response.status_code,
                            detail=response.text)

    return response.json()['documentId']

"""
Returns a textract result based on the incoming id.
Arguments:
image  – the image to be uploaded.
"""
def docupanda_extract_text(document_id: str) -> str:
    url = os.getenv("DOCUPANDA_URL") + "/" + document_id

    headers = {
        "accept": "application/json",
        "X-API-Key": os.getenv("DOCUPANDA_API_KEY")
    }

    response = requests.get(url, headers=headers)

    if response.status_code != status.HTTP_200_OK:
        raise HTTPException(status_code=response.status_code,
                            detail=response.text)

    text_sections = response.json()['result']['pages'][0]['sections']
    full_text = ""
    for section in text_sections:
        full_text = full_text + section['text'] + " "

    return full_text

# Deepgram

"""
Returns the incoming audio's transcription.
Arguments:
audio_file  – the audio file to be transcribed.
"""
async def deepgram_transcribe_notes(audio_file: UploadFile = File(...)) -> str:
    try:
        _, file_extension = os.path.splitext(audio_file.filename)
        files_dir = 'app/files'
        audio_copy_bare_name = datetime.datetime.now().strftime("%d-%m-%Y-%H-%M-%S")
        audio_copy_path = files_dir + '/' + audio_copy_bare_name + file_extension

        # Write incoming audio to our local volume for further processing
        with open(audio_copy_path, 'wb+') as buffer:
            shutil.copyfileobj(audio_file.file, buffer)

        assert os.path.exists(audio_copy_path), "Something went wrong while processing the file."
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                            detail=str(e))
    finally:
        await audio_file.close()

    # Process local copy with DeepgramClient
    try:
        deepgram = DeepgramClient(os.getenv("DG_API_KEY"))

        with open(audio_copy_path, "rb") as file:
            buffer_data = file.read()

        payload: FileSource = {
            "buffer": buffer_data,
        }

        options = PrerecordedOptions(
            model="nova-2",
            smart_format=True,
            detect_language=True,
            utterances=True,
            numerals=True
        )

        # Increase the timeout to 300 seconds (5 minutes)
        response = deepgram.listen.prerecorded.v("1").transcribe_file(payload,
                                                                      options,
                                                                      timeout=Timeout(300.0, connect=10.0))

        json_response = json.loads(response.to_json(indent=4))
        transcript = json_response.get('results').get('channels')[0]['alternatives'][0]['transcript']
    except HTTPException as e:
        raise HTTPException(status_code=e.status_code,
                            detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                            detail="The transcription operation failed.")
    finally:
        await utilities.clean_up_files([audio_copy_path])

    return transcript

"""
The set of IPs that Speechmatics may use to trigger a notification to our service.
"""
SPEECHMATICS_NOTIFICATION_IPS = [
    "40.74.41.91",
    "52.236.157.154",
    "40.74.37.0",
    "20.73.209.153",
    "20.73.142.44",
    "20.105.89.153",
    "20.105.89.173",
    "20.105.89.184",
    "20.105.89.98",
    "20.105.88.228",
    "52.149.21.32",
    "52.149.21.10",
    "52.137.102.83",
    "40.64.107.92",
    "40.64.107.99",
    "52.146.58.224",
    "52.146.58.159",
    "52.146.59.242",
    "52.146.59.213",
    "52.146.58.64",
    "20.248.249.20",
    "20.248.249.47",
    "20.248.249.181",
    "20.248.249.119",
    "20.248.249.164",
]

"""
Queues a new job for a diarization transcription using the incoming audio file.
Returns the Speechmatics job id that is processing.

Arguments:
auth_token  – the access_token associated with the current server session.
audio_file  – the audio file to be diarized.
"""
async def speechmatics_transcribe(auth_token: str,
                                  audio_file: UploadFile = File(...)) -> str:
    _, file_extension = os.path.splitext(audio_file.filename)
    files_dir = 'app/files'
    audio_copy_bare_name = datetime.datetime.now().strftime("%d-%m-%Y-%H-%M-%S")
    audio_copy_path = files_dir + '/' + audio_copy_bare_name + file_extension

    try:
        # Write incoming audio to our local volume for further processing
        with open(audio_copy_path, 'wb+') as buffer:
            shutil.copyfileobj(audio_file.file, buffer)

        assert os.path.exists(audio_copy_path), "Something went wrong while processing the file."
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                            detail=str(e))
    finally:
        await audio_file.close()

    # Temporary workaround until we add our own certificates
    ssl_context = ssl._create_unverified_context()
    # ssl_context = ssl.create_default_context()

    # Process local copy with Speechmatics client
    settings = ConnectionSettings(
        url=os.getenv("SPEECHMATICS_URL"),
        auth_token=os.getenv("SPEECHMATICS_API_KEY"),
        ssl_context=ssl_context,
    )

    conf = {
        "type": "transcription",
        "transcription_config": {
            "language": "auto",
            "operating_point": "enhanced",
            "diarization": "speaker",
            "enable_entities": True,
        },
        "notification_config": [
            {
            "url": os.environ.get("ENVIRONMENT_URL") + endpoints.DIARIZATION_NOTIFICATION_ENDPOINT,
            "method": "post",
            "contents": ["transcript"],
            "auth_headers": [f"Authorization: Bearer {auth_token}"]
            }
        ],
        "language_identification_config": {
            "expected_languages": ["en", "es"],
            "low_confidence_action": "allow"
        },
        "summarization_config": {
            "content_type": "conversational",
            "summary_length": "detailed",
            "summary_type": "bullets"
        },
    }

    with BatchClient(settings) as client:
        try:
            return client.submit_job(
                audio=audio_copy_path,
                transcription_config=conf,
            )
        except TimeoutError as e:
            raise HTTPException(status_code=status.HTTP_408_REQUEST_TIMEOUT)
        except HTTPException as e:
            raise HTTPException(status_code=e.status_code, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                                detail=str(e))
        finally:
            await utilities.clean_up_files([audio_copy_path])

# Portkey

"""
Returns whether or not the Portkey service is reachable.
"""
def is_portkey_reachable() -> bool:
    try:
        return requests.get(PORTKEY_GATEWAY_URL).status_code < status.HTTP_500_INTERNAL_SERVER_ERROR
    except:
        return False

"""
Returns a Portkey config to be used for their service.

Arguments:
cache_max_age  – the ttl of the cache.
"""
def create_portkey_config(cache_max_age, llm_model):
    return {
        "provider": "openai",
        "virtual_key": os.environ.get("PORTKEY_OPENAI_VIRTUAL_KEY"),
        "cache": {
            "mode": "semantic",
            "max_age": cache_max_age,
        },
        "retry": {
            "attempts": 2,
        },
        "override_params": {
            "model": llm_model,
            "temperature": 0,
        }
    }

"""
Returns a set of Portkey headers to be used for their service.

Arguments:
kwargs  – the set of optional arguments.
"""
def create_portkey_headers(**kwargs):
    environment = None if "environment" not in kwargs else kwargs["environment"]
    session_id = None if "session_id" not in kwargs else kwargs["session_id"]
    user = None if "user" not in kwargs else kwargs["user"]
    caching_shard_key = None if "caching_shard_key" not in kwargs else kwargs["caching_shard_key"]
    cache_max_age = None if "cache_max_age" not in kwargs else kwargs["cache_max_age"]
    endpoint_name = None if "endpoint_name" not in kwargs else kwargs["endpoint_name"]
    llm_model = None if "llm_model" not in kwargs else kwargs["llm_model"]
    method = None if "method" not in kwargs else kwargs["method"]
    return createHeaders(trace_id=uuid.uuid4(),
                         api_key=os.environ.get("PORTKEY_API_KEY"),
                         config=create_portkey_config(cache_max_age, llm_model),
                         cache_namespace=caching_shard_key,
                         metadata={
                            "environment": environment,
                            "user": user,
                            "vector_index": caching_shard_key,
                            "session_id": session_id,
                            "endpoint_name": endpoint_name,
                            "method": method,
                        })
