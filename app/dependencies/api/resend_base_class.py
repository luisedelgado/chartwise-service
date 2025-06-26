from abc import ABC, abstractmethod

from ...internal.alerting.internal_alert import InternalAlert

class ResendBaseClass(ABC):

    @abstractmethod
    def send_internal_alert(
        self,
        alert: InternalAlert
    ):
        """
        Sends an internal alert through the Resend service.
        """
        pass

    @abstractmethod
    def send_customer_relations_alert(
        self,
        alert: InternalAlert
    ):
        """
        Sends a customer relations alert through the Resend service.
        """
        pass
