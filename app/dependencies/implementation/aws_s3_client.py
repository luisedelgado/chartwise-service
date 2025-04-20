import boto3
import mimetypes
import os

from ..api.aws_s3_base_class import AwsS3BaseClass

class AwsS3Client(AwsS3BaseClass):

    FIFTEEN_MIN_IN_SECONDS = 900

    def __init__(self):
        self.client = boto3.client('s3',
            region_name=os.environ.get("AWS_SERVICES_REGION"),
        )

    def get_audio_file_upload_signed_url(self,
                                         file_path: str,
                                         bucket_name: str) -> str:
        try:
            content_type, _ = mimetypes.guess_type(file_path)
            if not content_type:
                # Default to audio/wav if content type cannot be guessed
                content_type = "audio/wav"

            response = self.client.generate_presigned_url(
                'put_object',
                Params={
                    'Bucket': bucket_name,
                    'Key': file_path,
                    'ContentType': content_type,
                },
                ExpiresIn=self.FIFTEEN_MIN_IN_SECONDS,
            )
        except Exception as e:
            raise Exception(f"Could not generate upload URL: {e}")

        return {
            "url": response,
            "key": file_path,
        }

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

    def get_audio_file_read_signed_url(self,
                                       bucket_name: str,
                                       file_path: str) -> str:
        return {
            "signedURL": "testUrl"
        }
