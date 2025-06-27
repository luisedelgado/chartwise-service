from ..api.aws_s3_base_class import AwsS3BaseClass

class FakeAwsS3Client(AwsS3BaseClass):

    get_audio_file_read_signed_url_invoked = False

    def initiate_multipart_audio_file_upload(
        self,
        file_path: str,
        bucket_name: str | None
    ) -> dict:
        return {"url": "myFakeUrl"}

    def retrieve_presigned_url_for_multipart_upload(
        self,
        part_number: int,
        bucket_name: str | None,
        upload_id: str | None,
        file_path: str | None,
    ) -> str:
        return "myFakeURL"

    def complete_multipart_audio_file_upload(
        self,
        file_path: str,
        upload_id: str,
        parts: list,
        bucket_name: str | None,
    ):
        pass

    def delete_file(
        self,
        source_bucket: str,
        storage_filepath: str
    ):
        pass

    def upload_file(
        self,
        destination_bucket: str,
        storage_filepath: str,
        content: str | bytes
    ):
        pass

    def get_audio_file_read_signed_url(
        self,
        bucket_name: str | None,
        file_path: str
    ) -> dict:
        self.get_audio_file_read_signed_url_invoked = True
        return {"url": "myFakeUrl"}
