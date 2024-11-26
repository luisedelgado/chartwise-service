from abc import ABC, abstractmethod

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
