from ..api.supabase_storage_base_class import SupabaseStorageBaseClass

class FakeSupabaseStorageClient(SupabaseStorageBaseClass):

    def delete_file(self,
                    source_bucket: str,
                    storage_filepath: str):
        pass

    def download_file(self,
                      source_bucket: str,
                      storage_filepath: str):
        pass

    def upload_file(self,
                    destination_bucket: str,
                    storage_filepath: str,
                    content: str | bytes):
        pass

    def move_file_between_buckets(self,
                                  source_bucket: str,
                                  destination_bucket: str,
                                  file_path: str):
        pass

    def get_audio_file_upload_signed_url(self,
                                         file_path: str,
                                         bucket_name: str) -> str:
        pass

    def get_audio_file_read_signed_url(self,
                                       bucket_name: str,
                                       file_path: str) -> str:
        return {
            "signedURL": "testUrl"
        }
