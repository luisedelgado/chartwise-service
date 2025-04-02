from ..api.aws_kms_base_class import AwsKmsBaseClass

class FakeAwsKmsClient(AwsKmsBaseClass):

    def decrypt_encryption_key_ciphertext(ciphertext: str) -> str:
        return "a887874cff8ebbadb84ecf26cd36994f7b2354253bb80f4e250cf5823323df1b"
