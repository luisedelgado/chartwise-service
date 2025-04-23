from abc import ABC, abstractmethod

class AwsS3BaseClass(ABC):

    SESSION_AUDIO_FILES_PROCESSING_BUCKET_NAME = "session-audio-files-processing"

    @abstractmethod
    def get_audio_file_upload_signed_url(
        file_path: str,
        bucket_name: str
    ) -> dict:
        """
        Returns a signed URL for uploading an audio file to S3.
        """
        pass

    @abstractmethod
    def delete_file(
        source_bucket: str,
        storage_filepath: str
    ):
        """
        Deletes a file from S3 storage.

        Arguments:
        source_bucket – the bucket from which the file should be deleted.
        storage_filepath – the file path to be used for storing the file.
        """
        pass

    @abstractmethod
    def upload_file(
        destination_bucket: str,
        storage_filepath: str,
        content: str | bytes
    ):
        """
        Uploads a file to S3 for further processing.

        Arguments:
        destination_bucket – the bucket where the file should be uploaded to.
        storage_filepath – the file path to be used for storing the file.
        content – the content to be uploaded in the form of bytes or a string filepath.
        """
        pass

    @abstractmethod
    def get_audio_file_read_signed_url(
        bucket_name: str,
        file_path: str
    ) -> dict:
        """
        Generates a signed url for reading an audio file.

        :param file_path: the filepath to be used for the file that will be read.
        :param bucket_name: the bucket name for the file that will be uploaded.
        """
        pass
