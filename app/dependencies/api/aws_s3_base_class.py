from abc import ABC, abstractmethod

AUDIO_FILES_PROCESSING_PENDING_BUCKET = "session-audio-files-processing-pending"

class AwsS3BaseClass(ABC):

    @abstractmethod
    def get_audio_file_upload_signed_url(file_path: str,
                                         bucket_name: str) -> str:
        """
        Returns a signed URL for uploading an audio file to S3.
        """
        pass

    @abstractmethod
    def delete_file(source_bucket: str,
                    storage_filepath: str):
        """
        Deletes a file from S3 storage.

        Arguments:
        source_bucket – the bucket from which the file should be deleted.
        storage_filepath – the file path to be used for storing the file.
        """
        pass

    @abstractmethod
    def download_file(source_bucket: str,
                      storage_filepath: str):
        """
        Downloads a file from S3 storage.

        Arguments:
        source_bucket – the bucket from where the file should be downloaded.
        storage_filepath – the file path to be used for storing the file.
        """
        pass

    @abstractmethod
    def upload_file(destination_bucket: str,
                    storage_filepath: str,
                    content: str | bytes):
        """
        Uploads a file to S3 for further processing.

        Arguments:
        destination_bucket – the bucket where the file should be uploaded to.
        storage_filepath – the file path to be used for storing the file.
        content – the content to be uploaded in the form of bytes or a string filepath.
        """
        pass

    @abstractmethod
    def move_file_between_buckets(source_bucket: str,
                                  destination_bucket: str,
                                  file_path: str):
        """
        Move a file from one S3 bucket to another.

        :param source_bucket: The name of the source bucket.
        :param destination_bucket: The name of the destination bucket.
        :param file_path: Path to the file in the source bucket.
        """
        pass

    @abstractmethod
    def get_audio_file_read_signed_url(self,
                                       bucket_name: str,
                                       file_path: str) -> str:
        """
        Generates a signed url for reading an audio file.

        :param file_path: the filepath to be used for the file that will be read.
        :param bucket_name: the bucket name for the file that will be uploaded.
        """
        pass
