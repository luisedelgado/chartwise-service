import base64
import os

from ..api.aws_kms_base_class import AwsKmsBaseClass
from ...internal.utilities.aws_utils import sign_and_send_aws_request

class AwsKmsClient(AwsKmsBaseClass):
    def __init__(self):
        encryption_key = "CHARTWISE_PHI_ENCRYPTION_KEY"
        key_hex: str = os.environ.get(encryption_key)
        if not key_hex:
            raise ValueError(f"Missing encryption key in env var: {encryption_key}")

        self.key_hex = key_hex
        self.region = os.environ.get("AWS_SERVICES_REGION")

    def decrypt_encryption_key_ciphertext(self) -> str:
        try:
            encrypted_key_bytes = base64.b64decode(self.key_hex)
            payload = {
                "CiphertextBlob": base64.b64encode(encrypted_key_bytes).decode("utf-8")
            }
            result = sign_and_send_aws_request(
                service="kms",
                region=self.region,
                endpoint_url=f"https://kms.{self.region}.amazonaws.com/",
                payload=payload,
                target_action="TrentService.Decrypt",
            )
            key_b64 = result["Plaintext"]
            return base64.b64decode(key_b64)
        except Exception as e:
            raise RuntimeError(e) from e
