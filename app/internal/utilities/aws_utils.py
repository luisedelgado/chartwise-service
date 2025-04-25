import json
import requests

from botocore.awsrequest import AWSRequest
from botocore.auth import SigV4Auth
from botocore.httpsession import URLLib3Session
from datetime import datetime, timedelta, timezone

from .datetime_handler import DATE_TIME_TIMEZONE_FORMAT, WEEKDAY_DATE_TIME_TIMEZONE_FORMAT
from ...dependencies.api.resend_base_class import ResendBaseClass
from ...dependencies.core.boto3_session_factory import Boto3SessionFactory

def sign_and_send_aws_request(
    service: str,
    region: str,
    endpoint_url: str,
    payload: dict,
    target_action: str,
    resend_client: ResendBaseClass,
) -> dict:
    """
    Constructs and sends a SigV4-signed AWS API request, adjusting for clock skew.

    Args:
        service: The AWS service name (e.g., 'kms', 'secretsmanager').
        region: The AWS region (e.g., 'us-east-1').
        endpoint_url: Full HTTPS endpoint URL.
        payload: The request body (as a dict).
        target_action: e.g., 'TrentService.Decrypt' or 'secretsmanager.GetSecretValue'
        timeout: Timeout in seconds for the request.
        resend_client: Resend client for sending internal alerts.

    Returns:
        dict response parsed from JSON.
    """
    try:
        session = Boto3SessionFactory.get_session(resend_client=resend_client)
        creds = session.get_credentials().get_frozen_credentials()

        clock_skew_offset = get_aws_clock_skew_offset()
        adjusted_time = datetime.now(timezone.utc) + timedelta(seconds=clock_skew_offset)

        body = json.dumps(payload).encode("utf-8")
        headers = {
            "Content-Type": "application/x-amz-json-1.1",
            "X-Amz-Target": target_action
        }

        request = AWSRequest(
            method="POST",
            url=endpoint_url,
            data=body,
            headers=headers,
        )
        request.context["timestamp"] = adjusted_time.strftime(DATE_TIME_TIMEZONE_FORMAT)
        SigV4Auth(creds, service, region).add_auth(request)

        http_session = URLLib3Session()
        response = http_session.send(request.prepare())

        if response.status_code != 200:
            raise Exception(f"[AWS Request] {response.status_code} {response.text}")

        return json.loads(response.content.decode("utf-8"))
    except Exception as e:
        raise RuntimeError(e) from e

def get_aws_clock_skew_offset() -> int:
    """
    Returns the number of seconds by which local system clock is off from AWS server time.
    Positive = local clock is behind.
    Negative = local clock is ahead.
    """
    try:
        response = requests.head("https://sts.amazonaws.com", timeout=5)
        aws_time_str = response.headers["Date"]
        aws_time = datetime.strptime(aws_time_str, WEEKDAY_DATE_TIME_TIMEZONE_FORMAT).astimezone(timezone.utc)
        local_time = datetime.now(timezone.utc)
        offset = int((aws_time - local_time).total_seconds())
        return offset
    except Exception as e:
        print(f"[ClockSkew] Failed to calculate clock skew: {e}")
        return 0
