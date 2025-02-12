import httpx

from supabase import Client

from ...dependencies.api.supabase_storage_base_class import SupabaseStorageBaseClass

class SupabaseStorageClient(SupabaseStorageBaseClass):

    def __init__(self, client: Client):
        self.client = client

    def delete_file(self,
                    source_bucket: str,
                    storage_filepath: str):
        try:
            return self.client.storage.from_(source_bucket).remove([storage_filepath])
        except Exception as e:
            raise Exception(e)

    def download_file(self,
                      source_bucket: str,
                      storage_filepath: str):
        try:
            return self.client.storage.from_(source_bucket).download(storage_filepath)
        except Exception as e:
            raise Exception(e)

    def upload_file(self,
                    destination_bucket: str,
                    storage_filepath: str,
                    content: str | bytes):
        try:
            self.client.storage.from_(destination_bucket).upload(path=storage_filepath,
                                                                 file=content)
        except Exception as e:
            raise Exception(e)

    def move_file_between_buckets(self,
                                  source_bucket: str,
                                  destination_bucket: str,
                                  file_path: str):
        try:
            source_file_url = self.get_audio_file_read_signed_url(file_path=file_path,
                                                                  bucket_name=source_bucket)
            destination_upload_url = self.get_audio_file_upload_signed_url(bucket_name=destination_bucket,
                                                                           file_path=file_path)

            with httpx.stream("GET", source_file_url) as source_response:
                # Ensure the request was successful
                source_response.raise_for_status()

                # Open a streaming PUT request to upload the file to the destination signed URL
                with httpx.stream("PUT",
                                  destination_upload_url,
                                  content=source_response.iter_bytes()) as dest_response:
                    # Ensure the upload was successful
                    dest_response.raise_for_status()

            self.delete_file(source_bucket=source_bucket,
                             storage_filepath=file_path)
        except Exception as e:
            raise Exception(e)

    def get_audio_file_upload_signed_url(self,
                                         bucket_name: str,
                                         file_path: str) -> str:
        try:
            return self.client.storage.from_(bucket_name).create_signed_upload_url(file_path)
        except Exception as e:
            raise Exception(e)

    def get_audio_file_read_signed_url(self,
                                       bucket_name: str,
                                       file_path: str) -> str:
        try:
            return self.client.storage.from_(bucket_name).create_signed_url(path=file_path,
                                                                                                      expires_in=600)
        except Exception as e:
            raise Exception(e)
