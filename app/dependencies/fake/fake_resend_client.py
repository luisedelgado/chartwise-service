from ..api.resend_base_class import ResendBaseClass

class FakeResendClient(ResendBaseClass):

    def send_new_subscription_welcome_email(self,
                                            user_first_name: str,
                                            language_code: str,
                                            to_address: str):
        pass

    def send_eng_team_internal_email(self,
                                     subject: str,
                                     body: str):
        pass
