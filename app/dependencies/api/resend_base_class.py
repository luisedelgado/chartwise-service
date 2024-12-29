from abc import ABC, abstractmethod

from ...internal.internal_alert import InternalAlertCategory

class ResendBaseClass(ABC):

    """
    Sends a welcome email in a new-subscription context

    Arguments:
    user_first_name – the customer's first name.
    language_code – the language code to be used.
    to_address – the email address to send the email to.
    """
    @abstractmethod
    def send_new_subscription_welcome_email(user_first_name: str,
                                            language_code: str,
                                            to_address: str):
        pass

    """
    Sends an internal notification email to our engineering team.

    Arguments:
    subject – the email subject.
    body – the email body.
    alert_category – the alert category.
    """
    @abstractmethod
    def send_eng_team_internal_alert_email(self,
                                           subject: str,
                                           body: str,
                                           alert_category: InternalAlertCategory):
        pass
