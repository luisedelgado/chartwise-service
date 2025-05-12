import boto3
import os
import threading

from datetime import datetime, timedelta, timezone

from ...internal.schemas import PROD_ENVIRONMENT, STAGING_ENVIRONMENT

class Boto3ClientFactory:
    _lock = threading.Lock()
    _clients = {}
    _expiration = None
    _creds = None

    @classmethod
    def get_client(
        cls,
        service_name: str,
    ):
        now = datetime.now(timezone.utc)
        client_region_name = (os.environ["AWS_SERVICES_REGION"])

        # Local dev: use assume_role with expiration check
        if os.environ.get("ENVIRONMENT") not in [STAGING_ENVIRONMENT, PROD_ENVIRONMENT]:
            if cls._expiration is None or now >= cls._expiration:
                with cls._lock:
                    if cls._expiration is None or now >= cls._expiration:
                        cls._refresh_credentials()

            if service_name not in cls._clients:
                cls._clients[service_name] = boto3.client(
                    service_name,
                    aws_access_key_id=cls._creds['AccessKeyId'],
                    aws_secret_access_key=cls._creds['SecretAccessKey'],
                    aws_session_token=cls._creds['SessionToken'],
                    region_name=client_region_name
                )
            return cls._clients[service_name]

        # ECS/staging/prod: use default creds
        if service_name not in cls._clients:
            cls._clients[service_name] = boto3.client(
                service_name,
                region_name=client_region_name
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
        cls._expiration = cls._creds["Expiration"] - timedelta(minutes=2)
        cls._clients = {}  # Clear old clients
