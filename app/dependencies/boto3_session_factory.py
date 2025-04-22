import boto3
import os
import threading

from datetime import datetime, timedelta, timezone

from ..internal.utilities.datetime_handler import UTC_DATETIME_FORMAT

class Boto3SessionFactory:
    _lock = threading.Lock()
    _session = None
    _expiration = None
    _creds = None

    @classmethod
    def get_session(cls) -> boto3.Session:
        now = datetime.now(timezone.utc)

        if cls._expiration is None or now >= cls._expiration:
            with cls._lock:
                if cls._expiration is None or datetime.now(timezone.utc) >= cls._expiration:
                    cls._refresh_credentials()

        return cls._session

    @classmethod
    def _refresh_credentials(cls):
        sts = boto3.client("sts")
        assumed = sts.assume_role(
            RoleArn=os.environ["AWS_CHARTWISE_ROLE_ARN"],
            RoleSessionName=os.environ["AWS_CHARTWISE_ROLE_SESSION_NAME"]
        )

        cls._creds = assumed["Credentials"]
        cls._expiration = datetime.strptime(
            cls._creds["Expiration"], UTC_DATETIME_FORMAT
        ) - timedelta(minutes=2)

        cls._session = boto3.Session(
            aws_access_key_id=cls._creds["AccessKeyId"],
            aws_secret_access_key=cls._creds["SecretAccessKey"],
            aws_session_token=cls._creds["SessionToken"],
            region_name=os.environ["AWS_SERVICES_REGION"]
        )

        print(f"[Boto3SessionFactory] Assumed ChartWise role, expires at {cls._expiration.isoformat()} UTC")
