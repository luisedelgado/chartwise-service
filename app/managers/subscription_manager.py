from datetime import datetime, date
from fastapi import Request

from ..dependencies.dependency_container import AwsDbBaseClass, dependency_container
from ..internal.schemas import SUBSCRIPTION_STATUS_TABLE_NAME
from ..internal.utilities.subscription_utilities import reached_subscription_tier_usage_limit

class SubscriptionManager():

    REACHED_TIER_USAGE_LIMIT_KEY = "reached_tier_usage_limit"
    SUBSCRIPTION_STATUS_KEY = "subscription_status"

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

            # Check if this user is already a customer, and has subscription history
            if len(customer_data) == 0:
                is_subscription_active = False
                is_free_trial_active = False
                tier = None
                reached_tier_usage_limit = None
            else:
                is_subscription_active = customer_data[0]['is_active']
                tier = customer_data[0]['current_tier']

                # Determine if free trial is still active
                free_trial_end_date: date = customer_data[0]['free_trial_end_date']

                if free_trial_end_date is not None:
                    is_free_trial_active = (datetime.now().date() < free_trial_end_date)
                else:
                    is_free_trial_active = False

                reached_tier_usage_limit = await reached_subscription_tier_usage_limit(
                    tier=tier,
                    therapist_id=user_id,
                    aws_db_client=aws_db_client,
                    is_free_trial_active=is_free_trial_active
                )
            return {
                self.SUBSCRIPTION_STATUS_KEY : {
                    "is_free_trial_active": is_free_trial_active,
                    "is_subscription_active": is_subscription_active,
                    "tier": tier,
                    self.REACHED_TIER_USAGE_LIMIT_KEY: reached_tier_usage_limit
                }
            }
        except Exception as e:
            return {
                self.SUBSCRIPTION_STATUS_KEY: None
            }
