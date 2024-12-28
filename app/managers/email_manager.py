from enum import Enum

from ..internal.dependency_container import (dependency_container,
                                             ResendBaseClass,
                                             SupabaseBaseClass)

class InternalAlertCategory(Enum):
    PAYMENTS = "payments"

class InternalAlert:
    def __init__(self,
                 category: InternalAlertCategory,
                 description: str,
                 session_id: str = None,
                 exception: Exception = None):
        self.session_id = session_id
        self.category = category
        self.description = description
        self.exception = exception

class EmailManager:

    PAYMENT_ALERT_HEADER = ("This is an automated alert from ChartWise's monitoring system "
                            "indicating a potential issue related to payments activity "
                            "that requires immediate attention. "
                            "Below are the specific details of the detected issue:\n\n")

    ALERT_DETAILS = ("• Therapist ID: {therapist_id}\n• Session ID: {session_id}\n")

    async def send_new_user_welcome_email(self,
                                          therapist_id: str,
                                          supabase_client: SupabaseBaseClass):
        try:
            therapist_query = supabase_client.select(fields="*",
                                                        filters={
                                                            "id": therapist_id
                                                        },
                                                        table_name="therapists")
            therapist_response_data = therapist_query.dict()['data'][0]
            therapist_first_name = therapist_response_data['first_name']
            language_code = therapist_response_data['language_preference']
            therapist_email = therapist_response_data['email']

            resend_client: ResendBaseClass = dependency_container.inject_resend_client()
            resend_client.send_new_subscription_welcome_email(user_first_name=therapist_first_name,
                                                              language_code=language_code,
                                                              to_address=therapist_email)
        except Exception as e:
            raise Exception(e)

    async def send_internal_eng_alert(self,
                                      alert: InternalAlert,
                                      therapist_id: str = None):
        try:
            resend_client: ResendBaseClass = dependency_container.inject_resend_client()

            if alert.category == InternalAlertCategory.PAYMENTS:
                subject = self.PAYMENT_ALERT_HEADER
            else:
                raise Exception("Unrecognized alert category")

            therapist_id = therapist_id if therapist_id is not None else "N/A"
            body = self.ALERT_DETAILS.format(therapist_id=therapist_id,
                                             session_id=alert.session_id) + "\n"
            body += alert.description

            if alert.exception is not None:
                body += f"\n\nThe following exception was raised: {str(alert.exception)}"

            resend_client.send_eng_team_internal_email(subject=subject,
                                                       body=body)
        except Exception as e:
            raise Exception(e)
