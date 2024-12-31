from abc import ABC, abstractmethod
from enum import Enum

from ..internal.schemas import MediaType

class InternalAlertCategory(Enum):
    PAYMENTS_ACTIVITY = "payments activity"
    AUDIO_JOB_PROCESSING = "audio job processing"
    IMAGE_JOB_PROCESSING = "image job processing"
    CUSTOMER_RELATIONS = "customer relations"

class InternalAlert(ABC):
    @abstractmethod
    def __init__(self,
                 description: str,
                 therapist_id: str = None,
                 session_id: str = None,
                 exception: Exception = None):
        self.session_id = session_id
        self.therapist_id = therapist_id
        self.description = description
        self.exception = exception

class PaymentsActivityAlert(InternalAlert):
    def __init__(self,
                 description: str,
                 session_id: str = None,
                 exception: Exception = None,
                 therapist_id: str = None,
                 subscription_id: str = None,
                 customer_id: str = None,
                 payment_method_id: str = None):
        super().__init__(description=description,
                         therapist_id=therapist_id,
                         session_id=session_id,
                         exception=exception)
        self.subscription_id = subscription_id
        self.customer_id = customer_id
        self.payment_method_id = payment_method_id
        self.category = InternalAlertCategory.PAYMENTS_ACTIVITY

class MediaJobProcessingAlert(InternalAlert):
    def __init__(self,
                 description: str,
                 media_type: MediaType,
                 session_id: str = None,
                 exception: Exception = None,
                 therapist_id: str = None,
                 storage_filepath: str = None,
                 session_report_id: str = None):
        super().__init__(description=description,
                         therapist_id=therapist_id,
                         session_id=session_id,
                         exception=exception)
        self.storage_filepath = storage_filepath
        self.session_report_id = session_report_id
        self.category = InternalAlertCategory.AUDIO_JOB_PROCESSING if media_type == MediaType.AUDIO else InternalAlertCategory.IMAGE_JOB_PROCESSING

class CustomerRelationsAlert(InternalAlert):
    def __init__(self,
                 description: str,
                 session_id: str = None,
                 exception: Exception = None,
                 therapist_id: str = None,
                 therapist_name: str = None,
                 therapist_email: str = None):
        super().__init__(description=description,
                         therapist_id=therapist_id,
                         session_id=session_id,
                         exception=exception)
        self.category = InternalAlertCategory.CUSTOMER_RELATIONS
        self.therapist_name = therapist_name
        self.therapist_email = therapist_email
