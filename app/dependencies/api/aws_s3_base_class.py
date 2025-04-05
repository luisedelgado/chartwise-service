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
