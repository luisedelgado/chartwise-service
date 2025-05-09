import boto3
import os
import threading

from datetime import datetime, timedelta, timezone

from ...dependencies.api.resend_base_class import ResendBaseClass
from ...internal.alerting.internal_alert import EngineeringAlert
from ...internal.schemas import PROD_ENVIRONMENT, STAGING_ENVIRONMENT
from ...internal.session_container import session_container

class Boto3SessionFactory:
    _lock = threading.Lock()
    _session = None
    _expiration = None
    _creds = None

    @classmethod
    def get_session(
        cls,
        resend_client: ResendBaseClass,
    ) -> boto3.Session:
        try:
            now = datetime.now(timezone.utc)

            if os.environ.get("ENVIRONMENT") not in [STAGING_ENVIRONMENT, PROD_ENVIRONMENT] and (
                cls._expiration is None or now >= cls._expiration
            ):
                with cls._lock:
                    if cls._expiration is None or datetime.now(timezone.utc) >= cls._expiration:
                        cls._refresh_credentials(resend_client=resend_client)

            # If we're running in ECS and we have IAM creds, let's use them to create a new session.
            if cls._session is None:
                cls._session = boto3.Session(region_name=os.environ["AWS_SERVICES_REGION"])
            return cls._session
        except Exception as e:
            raise RuntimeError(e) from e

    @classmethod
    def _refresh_credentials(
        cls,
        resend_client: ResendBaseClass,
    ):
        try:
            sts = boto3.client("sts")
            assumed = sts.assume_role(
                RoleArn=os.environ["AWS_CHARTWISE_ROLE_ARN"],
                RoleSessionName=os.environ["AWS_CHARTWISE_ROLE_SESSION_NAME"]
            )

            cls._creds = assumed["Credentials"]
            cls._expiration = cls._creds["Expiration"] - timedelta(minutes=2)
            cls._session = boto3.Session(
                aws_access_key_id=cls._creds["AccessKeyId"],
                aws_secret_access_key=cls._creds["SecretAccessKey"],
                aws_session_token=cls._creds["SessionToken"],
                region_name=os.environ["AWS_SERVICES_REGION"]
            )

            print(f"[Boto3SessionFactory] Assumed ChartWise role, expires at {cls._expiration.isoformat()} UTC")
        except Exception as e:
            error_message = f"[Boto3SessionFactory] Error assuming ChartWise role: {e}"
            eng_alert = EngineeringAlert(
                description=error_message,
                session_id=session_container.session_id,
                exception=e,
                environment=session_container.environment,
                therapist_id=session_container.user_id,
            )
            resend_client.send_internal_alert(
                alert=eng_alert
            )
            raise RuntimeError(error_message) from e
