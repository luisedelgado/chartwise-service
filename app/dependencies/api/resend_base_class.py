from abc import ABC, abstractmethod

from ...internal.internal_alert import InternalAlertCategory

class ResendBaseClass(ABC):

    @abstractmethod
    def send_eng_team_internal_alert_email(self,
                                           subject: str,
                                           body: str,
                                           alert_category: InternalAlertCategory):
        """
        Sends an internal notification email to our engineering team.

        Arguments:
        subject – the email subject.
        body – the email body.
        alert_category – the alert category.
        """
        pass

    @abstractmethod
    def send_customer_relations_alert_email(subject: str,
                                            body: str,
                                            alert_category: InternalAlertCategory):
        """
        Sends an internal notification email regarding customer relations.

        Arguments:
        subject – the email subject.
        body – the email body.
        alert_category – the alert category.
        """
        pass
