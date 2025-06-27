from ..api.aws_s3_base_class import AwsS3BaseClass
from ..core.boto3_client_factory import Boto3ClientFactory

class AwsS3Client(AwsS3BaseClass):

    TEN_MIN_IN_SECONDS = 600
    FIFTEEN_MIN_IN_SECONDS = 900

    def __init__(self):
        self.client = Boto3ClientFactory.get_client(
            service_name="s3",
        )

    def initiate_multipart_audio_file_upload(
        self,
        file_path: str,
        bucket_name: str | None,
    ) -> dict:
        try:
            assert bucket_name is not None, "Received a nullable bucket name"

            response = self.client.create_multipart_upload(
                Bucket=bucket_name,
                Key=file_path
            )
            return {
                "upload_id": response["UploadId"],
                "file_path": file_path
            }
        except Exception as e:
            raise RuntimeError(f"Failed to initiate file upload: {e}") from e

    def retrieve_presigned_url_for_multipart_upload(
        self,
        part_number: int,
        bucket_name: str | None,
        upload_id: str | None,
        file_path: str | None,
    ) -> str:
        try:
            assert bucket_name is not None, "Received nullable bucket name"
            assert upload_id is not None, "Received nullable upload id"
            assert file_path is not None, "Received nullable file path"
            url = self.client.generate_presigned_url(
                "upload_part",
                Params={
                    "Bucket": bucket_name,
                    "Key": file_path,
                    "UploadId": upload_id,
                    "PartNumber": part_number,
                },
                ExpiresIn=900
            )
            return url
        except Exception as e:
            raise RuntimeError(f"Failed to retrieve presigned URL for multipart upload: {e}") from e

    def complete_multipart_audio_file_upload(
        self,
        file_path: str,
        upload_id: str,
        parts: list,
        bucket_name: str | None,
    ):
        try:
            assert bucket_name is not None, "Received nullable bucket name"
            self.client.complete_multipart_upload(
                Bucket=bucket_name,
                Key=file_path,
                UploadId=upload_id,
                MultipartUpload={"Parts": parts}
            )
        except Exception as e:
            raise RuntimeError(f"Failed to complete file upload: {e}") from e

    def delete_file(
        self,
        source_bucket: str,
        storage_filepath: str
    ):
        try:
            self.client.delete_object(
                Bucket=source_bucket,
                Key=storage_filepath
            )
        except Exception as e:
            raise RuntimeError(f"Could not delete file: {e}") from e

    def upload_file(
        self,
        destination_bucket: str,
        storage_filepath: str,
        content: str | bytes
    ):
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

    def get_audio_file_read_signed_url(
        self,
        bucket_name: str | None,
        file_path: str
    ) -> dict:
        try:
            assert bucket_name is not None, "Received nullable bucket name"
            response = self.client.generate_presigned_url(
                'get_object',
                Params={
                    'Bucket': bucket_name,
                    'Key': file_path,
                },
                ExpiresIn=type(self).TEN_MIN_IN_SECONDS,
            )
            return {
                "url": response,
            }
        except Exception as e:
            raise RuntimeError(f"Could not generate read URL: {e}") from e
