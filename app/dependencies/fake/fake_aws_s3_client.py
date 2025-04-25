from ..api.aws_s3_base_class import AwsS3BaseClass

class FakeAwsS3Client(AwsS3BaseClass):

    get_audio_file_read_signed_url_invoked = False

    def get_audio_file_upload_signed_url(
        self,
        file_path: str,
        bucket_name: str
    ) -> dict:
        return {"url": "myFakeUrl"}

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
        bucket_name: str,
        file_path: str
    ) -> dict:
        self.get_audio_file_read_signed_url_invoked = True
        return {"url": "myFakeUrl"}
