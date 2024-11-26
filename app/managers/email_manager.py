from ..internal.dependency_container import (dependency_container,
                                             ResendBaseClass,
                                             SupabaseBaseClass)

class EmailManager:

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
