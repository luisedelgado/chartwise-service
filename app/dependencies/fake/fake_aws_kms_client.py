import base64

from ..api.aws_kms_base_class import AwsKmsBaseClass
from ..api.resend_base_class import ResendBaseClass

class FakeAwsKmsClient(AwsKmsBaseClass):

    def decrypt_encryption_key_ciphertext(
        self,
        resend_client: ResendBaseClass,
    ) -> str:
        return base64.b64decode("3DclmGMk9h9s+PFlIF9XjzQnCDgdGUk+Zud8Ilpxjx4=")
