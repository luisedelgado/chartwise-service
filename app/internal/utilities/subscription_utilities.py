from babel.numbers import format_currency, get_currency_precision
from datetime import datetime, timedelta
from fastapi import Request

from ..schemas import ENCRYPTED_SESSION_REPORTS_TABLE_NAME
from ...dependencies.dependency_container import AwsDbBaseClass

NUM_SESSIONS_IN_FREEMIUM_TIER = 25

async def reached_freemium_usage_limit(
    therapist_id: str,
    aws_db_client: AwsDbBaseClass,
    request: Request,
) -> bool:
    today = datetime.now().date()
    current_week_monday = today - timedelta(days=today.weekday())
    current_week_sunday = current_week_monday + timedelta(days=6)

    try:
        current_week_session_count = await aws_db_client.select_count(
            user_id=therapist_id,
            request=request,
            filters={
                "therapist_id": therapist_id,
                "created_at__gte": current_week_monday,
                "created_at__lte": current_week_sunday,
            },
            table_name=ENCRYPTED_SESSION_REPORTS_TABLE_NAME,
        )
        return current_week_session_count >= NUM_SESSIONS_IN_FREEMIUM_TIER
    except Exception as e:
        raise RuntimeError(e) from e

def map_stripe_product_name_to_chartwise_tier(
    stripe_plan: str
) -> str:
    """
    Map a given Stripe product to a ChartWise tier.
    """
    if stripe_plan == "premium_plan_yearly" or stripe_plan == "premium_plan_monthly":
        return "premium"
    else:
        raise Exception(f"Untracked Stripe product name: {stripe_plan}")

def format_currency_amount(
    amount: float,
    currency_code: str
) -> str:
    """
    Formats a currency amount based on the incoming currency code.
    """
    # Get the currency precision (e.g., 2 for USD, 0 for JPY)
    precision = get_currency_precision(currency_code.upper())

    # Convert the amount to the main currency unit
    divisor = 10 ** precision
    amount = amount / divisor

    # Format the currency
    return format_currency(number=amount, currency=currency_code.upper(), locale='en_US')
