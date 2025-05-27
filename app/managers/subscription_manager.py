from datetime import datetime, date
from fastapi import Request

from ..dependencies.dependency_container import AwsDbBaseClass, dependency_container
from ..internal.schemas import SUBSCRIPTION_STATUS_TABLE_NAME
from ..internal.utilities.subscription_utilities import reached_freemium_usage_limit

class SubscriptionManager():

    REACHED_FREEMIUM_USAGE_LIMIT_KEY = "reached_freemium_usage_limit"
    SUBSCRIPTION_STATUS_KEY = "subscription_status"
    IS_SUBSCRIPTION_ACTIVE_KEY = "is_subscription_active"

    async def subscription_data(
        self,
        user_id: str,
        request: Request
    ):
        """
        Returns a JSON object representing the subscription status of the user.
        Arguments:
        user_id – the id of the user.
        request – the upstream request object.
        """
        try:
            aws_db_client: AwsDbBaseClass = dependency_container.inject_aws_db_client()
            customer_data = await aws_db_client.select(
                user_id=user_id,
                request=request,
                fields=["*"],
                filters={
                    'therapist_id': user_id,
                },
                table_name=SUBSCRIPTION_STATUS_TABLE_NAME
            )

            if len(customer_data) == 0:
                # User is not subscribed, return freemium tier status
                reached_limit = await reached_freemium_usage_limit(
                    therapist_id=user_id,
                    aws_db_client=aws_db_client,
                    request=request,
                )
                return {
                    self.SUBSCRIPTION_STATUS_KEY : {
                        self.IS_SUBSCRIPTION_ACTIVE_KEY: False,
                        self.REACHED_FREEMIUM_USAGE_LIMIT_KEY: reached_limit
                    }
                }

            return {
                self.SUBSCRIPTION_STATUS_KEY : {
                    self.IS_SUBSCRIPTION_ACTIVE_KEY: customer_data[0]['is_active'],
                    "tier": customer_data[0]['current_tier'],
                }
            }
        except Exception as e:
            return {
                self.SUBSCRIPTION_STATUS_KEY: None
            }
