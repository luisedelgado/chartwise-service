from ..api.aws_s3_base_class import AwsS3BaseClass

class AwsS3Client(AwsS3BaseClass):

    def get_audio_file_upload_signed_url(self,
                                         file_path: str,
                                         bucket_name: str) -> str:
        return "myFakeUrl"
