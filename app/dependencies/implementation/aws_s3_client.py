import boto3
import mimetypes
import os

from ..api.aws_s3_base_class import AwsS3BaseClass

class AwsS3Client(AwsS3BaseClass):

    TEN_MIN_IN_SECONDS = 600
    FIFTEEN_MIN_IN_SECONDS = 900

    def __init__(self):
        self.client = boto3.client('s3',
            region_name=os.environ.get("AWS_SERVICES_REGION"),
        )

    def get_audio_file_upload_signed_url(self,
                                         file_path: str,
                                         bucket_name: str) -> dict:
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
            return {
                "url": response,
                "content_type": content_type,
            }
        except Exception as e:
            raise RuntimeError(f"Could not generate upload URL: {e}") from e

    def delete_file(self,
                    source_bucket: str,
                    storage_filepath: str):
        try:
            self.client.delete_object(
                Bucket=source_bucket,
                Key=storage_filepath
            )
        except Exception as e:
            raise RuntimeError(f"Could not delete file: {e}") from e

    def download_file(self,
                      source_bucket: str,
                      storage_filepath: str):
        try:
            return self.client.download_file(
                Bucket=source_bucket,
                Key=storage_filepath,
                Filename=storage_filepath
            )
        except Exception as e:
            raise RuntimeError(f"Could not download file: {e}") from e

    def upload_file(self,
                    destination_bucket: str,
                    storage_filepath: str,
                    content: str | bytes):
        try:
            if isinstance(content, str):
                content = content.encode('utf-8')

            self.client.put_object(
                Bucket=destination_bucket,
                Key=storage_filepath,
                Body=content
            )
        except Exception as e:
            raise RuntimeError(f"Could not upload file: {e}") from e

    def get_audio_file_read_signed_url(self,
                                       bucket_name: str,
                                       file_path: str) -> dict:
        try:
            response = self.client.generate_presigned_url(
                'get_object',
                Params={
                    'Bucket': bucket_name,
                    'Key': file_path,
                },
                ExpiresIn=self.TEN_MIN_IN_SECONDS,
            )
            return {
                "url": response,
            }
        except Exception as e:
            raise RuntimeError(f"Could not generate read URL: {e}") from e
