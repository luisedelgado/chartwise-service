import base64
import boto3
import os
import json
import requests

from datetime import datetime, timedelta, timezone

from botocore.awsrequest import AWSRequest
from botocore.auth import SigV4Auth
from botocore.httpsession import URLLib3Session
from botocore.session import get_session

from ..api.aws_kms_base_class import AwsKmsBaseClass
from ...internal.utilities.datetime_handler import DATE_TIME_TIMEZONE_FORMAT, WEEKDAY_DATE_TIME_TIMEZONE_FORMAT

class AwsKmsClient(AwsKmsBaseClass):
    def __init__(self):
        encryption_key = "CHARTWISE_PHI_ENCRYPTION_KEY"
        key_hex: str = os.environ.get(encryption_key)
        if not key_hex:
            raise ValueError(f"Missing encryption key in env var: {encryption_key}")

        self.key_hex = key_hex
        self.region = os.environ.get("AWS_PHI_ENCRYPTION_KEY_REGION")
        self.session = boto3.Session()
        self.botocore_session = get_session()

    def _get_aws_clock_skew_offset(self) -> int:
        try:
            response = requests.head("https://aws.amazon.com")
            aws_time_str = response.headers["Date"]
            aws_time = datetime.strptime(aws_time_str, WEEKDAY_DATE_TIME_TIMEZONE_FORMAT).astimezone(timezone.utc)
            local_time = datetime.now(timezone.utc)
            offset = int((aws_time - local_time).total_seconds())
            return offset
        except Exception as e:
            print(f"[AWS KMS] Failed to calculate clock skew: {e}")
            return 0

    def decrypt_encryption_key_ciphertext(self) -> str:
        try:
            encrypted_key_bytes = base64.b64decode(self.key_hex)
            clock_skew_offset = self._get_aws_clock_skew_offset()

            # Build the request
            payload = {
                "CiphertextBlob": base64.b64encode(encrypted_key_bytes).decode("utf-8")
            }
            headers = {
                "Content-Type": "application/x-amz-json-1.1",
                "X-Amz-Target": "TrentService.Decrypt",
            }

            endpoint_url = f"https://kms.{self.region}.amazonaws.com/"
            body = json.dumps(payload).encode("utf-8")

            request = AWSRequest(
                method="POST",
                url=endpoint_url,
                data=body,
                headers=headers,
            )

            # Adjust timestamp for SigV4
            adjusted_time = datetime.now(timezone.utc) + timedelta(seconds=clock_skew_offset)
            request.context["timestamp"] = adjusted_time.strftime(DATE_TIME_TIMEZONE_FORMAT)

            # Sign the request manually
            creds = self.session.get_credentials()
            SigV4Auth(creds, "kms", self.region).add_auth(request)

            # Send the request manually
            http_session = URLLib3Session()
            response = http_session.send(request.prepare())

            if response.status_code != 200:
                raise Exception(f"[AWS KMS] Decrypt failed: {response.status_code} {response.text}")

            response_body = response.content.decode("utf-8")
            result = json.loads(response_body)
            key_b64 = result["Plaintext"]
            return base64.b64decode(key_b64)
        except Exception as e:
            raise Exception(e)
