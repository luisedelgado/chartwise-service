from abc import ABC
from enum import Enum

class InternalAlertCategory(Enum):
    PAYMENTS_ACTIVITY = "payments activity"

class InternalAlert(ABC):
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
        super.__init__(session_id=session_id,
                       description=description,
                       therapist_id=therapist_id,
                       exception=exception)
        self.subscription_id = subscription_id
        self.customer_id = customer_id
        self.payment_method_id = payment_method_id
        self.category = InternalAlertCategory.PAYMENTS_ACTIVITY
