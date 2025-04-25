import boto3
import os
import threading

from datetime import datetime, timedelta, timezone

from ...internal.utilities.datetime_handler import UTC_DATETIME_FORMAT

class Boto3ClientFactory:
    _lock = threading.Lock()
    _clients = {}
    _expiration = None

    @classmethod
    def get_client(
        cls,
        service_name: str
    ):
        now = datetime.now(timezone.utc)

        # Check if credentials are missing or expired.
        if cls._expiration is None or now >= cls._expiration:
            with cls._lock:
                # Re-check inside the lock in case another thread already refreshed.
                if cls._expiration is None or now >= cls._expiration:
                    # Credentials are missing or expired.
                    cls._refresh_credentials()

        if service_name not in cls._clients:
            cls._clients[service_name] = boto3.client(
                service_name,
                aws_access_key_id=cls._creds['AccessKeyId'],
                aws_secret_access_key=cls._creds['SecretAccessKey'],
                aws_session_token=cls._creds['SessionToken'],
                region_name=os.environ["AWS_SERVICES_REGION"]
            )
        return cls._clients[service_name]

    @classmethod
    def _refresh_credentials(cls):
        sts = boto3.client("sts")
        assumed = sts.assume_role(
            RoleArn=os.environ["AWS_CHARTWISE_ROLE_ARN"],
            RoleSessionName=os.environ["AWS_CHARTWISE_ROLE_SESSION_NAME"]
        )
        cls._creds = assumed["Credentials"]

        # Expires 2 minutes early to prevent "edge-case" failures if a request comes in while creds are expiring.
        cls._expiration = cls._creds["Expiration"] - timedelta(minutes=2)
        cls._clients = {}  # Clear old clients that were tied to old creds
