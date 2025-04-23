import base64

from ..api.aws_kms_base_class import AwsKmsBaseClass

class FakeAwsKmsClient(AwsKmsBaseClass):

    def decrypt_encryption_key_ciphertext(ciphertext: str) -> str:
        return base64.b64decode("3DclmGMk9h9s+PFlIF9XjzQnCDgdGUk+Zud8Ilpxjx4=")
