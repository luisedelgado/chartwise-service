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
            download_response = self.download_file(source_bucket=source_bucket,
                                                   storage_filepath=file_path)

            self.upload_file(destination_bucket=destination_bucket,
                             storage_filepath=file_path,
                             content=download_response)

            self.delete_file(source_bucket=source_bucket,
                             storage_filepath=file_path)
        except Exception as e:
            raise Exception(e)
