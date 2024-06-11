import asyncio, base64, datetime, os, requests, shutil

from fastapi import (File, HTTPException, status, UploadFile)
from PIL import Image
from supabase import create_client, Client

from . import utilities

"""
Returns an active supabase instance based on a user's auth tokens.

Arguments:
access_token  – the access_token associated with a live supabase session
refresh_token  – the refresh_token associated with a live supabase session
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

"""
Uploads an image file to the DocuPanda service.
Returns an ID associated with the uploaded resource.
Arguments:
image  – the image to be uploaded
"""
def docupanda_upload_image(image: UploadFile = File(...)) -> str:
    global __session_id
    global __image_files_endpoint_name

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
image  – the image to be uploaded
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
