import httpx

from supabase import Client

from ...dependencies.api.supabase_storage_base_class import SupabaseStorageBaseClass

class SupabaseStorageClient(SupabaseStorageBaseClass):

    FIVE_MB = 5 * 1024 * 1024

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
            source_file_url = self.get_audio_file_read_signed_url(
                file_path=file_path,
                bucket_name=source_bucket
            ).get("signedURL")

            destination_upload_url = self.get_audio_file_upload_signed_url(
                bucket_name=destination_bucket,
                file_path=file_path
            ).get("signed_url")

            client = httpx.Client(timeout=300)
            head_response = client.head(source_file_url)
            total_size = int(head_response.headers.get('content-length', 0))

            # Download and upload in chunks
            with client.stream("GET", source_file_url) as source_response:
                source_response.raise_for_status()

                chunks = source_response.iter_bytes(chunk_size=self.FIVE_MB)
                headers = {
                    'Content-Length': str(total_size),
                    'Content-Type': 'application/octet-stream'
                }

                # Stream the file in chunks to avoid memory issues
                with client.stream("PUT",
                                    destination_upload_url,
                                    content=chunks,
                                    headers=headers) as dest_response:
                    dest_response.raise_for_status()

                    # Consume the response to ensure the upload completes
                    for _ in dest_response.iter_bytes():
                        pass

            # Only delete the source file if the transfer was successful
            self.delete_file(
                source_bucket=source_bucket,
                storage_filepath=file_path
            )

        except Exception as e:
            # Fail silently and log the error.
            print(f"Error while moving file between Supabase buckets: {str(e)}")
        finally:
            client.close()

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
