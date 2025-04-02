import base64
import boto3
import os

from ..api.aws_kms_base_class import AwsKmsBaseClass

class AwsKmsClient(AwsKmsBaseClass):

    def __init__(self):
        encryption_key = "CHARTWISE_PHI_ENCRYPTION_KEY"
        key_hex: str = os.environ.get(encryption_key)
        if not key_hex:
            raise ValueError(f"Missing encryption key in env var: {encryption_key}")

        self.key_hex = key_hex
        self.kms = boto3.client("kms", region_name=os.environ.get("AWS_PHI_ENCRYPTION_KEY_REGION"))

    def decrypt_encryption_key_ciphertext(self) -> str:
        try:
            encrypted_key_bytes = base64.b64decode(self.key_hex)
            response = self.kms.decrypt(CiphertextBlob=encrypted_key_bytes)
            key = response["Plaintext"]
            return key
        except Exception as e:
            raise Exception(e)
