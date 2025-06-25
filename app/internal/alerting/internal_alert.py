from abc import ABC, abstractmethod
from enum import Enum

from ...internal.schemas import MediaType

class InternalAlertCategory(Enum):
    UNKNOWN = "unknown"
    PAYMENTS_ACTIVITY = "payments activity"
    AUDIO_JOB_PROCESSING = "audio job processing"
    IMAGE_JOB_PROCESSING = "image job processing"
    CUSTOMER_RELATIONS = "customer relations"
    ENGINEERING_ALERT = "engineering"

class InternalAlert(ABC):
    @abstractmethod
    def __init__(
        self,
        description: str,
        category: str,
        environment: str | None = None,
        therapist_id: str | None = None,
        session_id: str | None= None,
        exception: Exception | None = None
    ):
        self.environment = environment
        self.session_id = session_id
        self.therapist_id = therapist_id
        self.description = description
        self.exception = exception
        self.category = category

class PaymentsActivityAlert(InternalAlert):
    def __init__(
        self,
        environment: str,
        description: str,
        session_id: str | None = None,
        exception: Exception | None = None,
        therapist_id: str | None = None,
        subscription_id: str | None = None,
        customer_id: str | None = None,
        payment_method_id: str | None = None
    ):
        super().__init__(
            description=description,
            environment=environment,
            therapist_id=therapist_id,
            session_id=session_id,
            exception=exception,
            category=InternalAlertCategory.PAYMENTS_ACTIVITY.value,
        )
        self.subscription_id = subscription_id
        self.customer_id = customer_id
        self.payment_method_id = payment_method_id
        self.category = InternalAlertCategory.PAYMENTS_ACTIVITY

class MediaJobProcessingAlert(InternalAlert):
    def __init__(
        self,
        environment: str,
        description: str,
        media_type: MediaType,
        session_id: str | None = None,
        exception: Exception | None = None,
        therapist_id: str | None = None,
        storage_filepath: str | None = None,
        session_report_id: str | None = None
    ):
        job_category = (
            InternalAlertCategory.AUDIO_JOB_PROCESSING.value if media_type == MediaType.AUDIO
            else InternalAlertCategory.IMAGE_JOB_PROCESSING.value
        )
        super().__init__(
            description=description,
            environment=environment,
            therapist_id=therapist_id,
            session_id=session_id,
            exception=exception,
            category=job_category,
        )
        self.storage_filepath = storage_filepath
        self.session_report_id = session_report_id

class CustomerRelationsAlert(InternalAlert):
    def __init__(
        self,
        environment: str,
        description: str,
        session_id: str | None = None,
        exception: Exception | None = None,
        therapist_id: str | None = None,
        therapist_name: str | None = None,
        therapist_email: str | None = None
    ):
        super().__init__(
            environment=environment,
            description=description,
            therapist_id=therapist_id,
            session_id=session_id,
            exception=exception,
            category=InternalAlertCategory.CUSTOMER_RELATIONS.value,
        )
        self.category = InternalAlertCategory.CUSTOMER_RELATIONS
        self.therapist_name = therapist_name
        self.therapist_email = therapist_email

class EngineeringAlert(InternalAlert):
    def __init__(
        self,
        description: str,
        environment: str | None = None,
        session_id: str | None = None,
        exception: Exception | None = None,
        therapist_id: str | None = None,
        patient_id: str | None = None
    ):
        super().__init__(
            environment=environment,
            description=description,
            therapist_id=therapist_id,
            session_id=session_id,
            exception=exception,
            category=InternalAlertCategory.ENGINEERING_ALERT.value,
        )
        self.patient_id = patient_id
        self.category = InternalAlertCategory.ENGINEERING_ALERT
