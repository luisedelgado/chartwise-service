from abc import ABC, abstractmethod

class SupabaseStorageBaseClass(ABC):

    """
    Deletes a file from Supabase storage.

    Arguments:
    source_bucket – the bucket from which the file should be deleted.
    storage_filepath – the file path to be used for storing the file.
    """
    @abstractmethod
    def delete_file(self,
                    source_bucket: str,
                    storage_filepath: str):
        pass

    """
    Downloads a file from Supabase storage.

    Arguments:
    source_bucket – the bucket from where the file should be downloaded.
    storage_filepath – the file path to be used for storing the file.
    """
    @abstractmethod
    def download_file(source_bucket: str,
                      storage_filepath: str):
        pass

    """
    Uploads a file to Supabase for further processing.

    Arguments:
    destination_bucket – the bucket where the file should be uploaded to.
    storage_filepath – the file path to be used for storing the file.
    content – the content to be uploaded in the form of bytes or a string filepath.
    """
    @abstractmethod
    def upload_file(destination_bucket: str,
                    storage_filepath: str,
                    content: str | bytes):
        pass

    """
    Move a file from one Supabase bucket to another.

    :param source_bucket: The name of the source bucket.
    :param destination_bucket: The name of the destination bucket.
    :param file_path: Path to the file in the source bucket.
    """
    def move_file_between_buckets(source_bucket: str,
                                  destination_bucket: str,
                                  file_path: str):
        pass
