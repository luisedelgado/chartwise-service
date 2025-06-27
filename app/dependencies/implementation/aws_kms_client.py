import base64
import os

from ..api.aws_kms_base_class import AwsKmsBaseClass
from ..api.resend_base_class import ResendBaseClass
from ...internal.utilities.aws_utils import sign_and_send_aws_request

class AwsKmsClient(AwsKmsBaseClass):
    def __init__(self):
        encryption_key = "CHARTWISE_PHI_ENCRYPTION_KEY"
        key_hex = os.environ.get(encryption_key)
        if not key_hex:
            raise ValueError(f"Missing encryption key in env var: {encryption_key}")

        self.key_hex = key_hex
        region = os.environ.get("AWS_SERVICES_REGION")

        assert region is not None, "Missing region"
        self.region = region

    def decrypt_encryption_key_ciphertext(
        self,
        resend_client: ResendBaseClass,
    ) -> bytes:
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
                resend_client=resend_client,
            )
            key_b64 = result["Plaintext"]
            return base64.b64decode(key_b64)
        except Exception as e:
            raise RuntimeError(e) from e
