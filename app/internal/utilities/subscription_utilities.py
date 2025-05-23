from babel.numbers import format_currency, get_currency_precision
from datetime import datetime, timedelta

from .datetime_handler import DATE_FORMAT
from ..schemas import ENCRYPTED_SESSION_REPORTS_TABLE_NAME
from ...dependencies.dependency_container import AwsDbBaseClass

NUM_SESSIONS_IN_FREEMIUM_TIER = 25

async def reached_subscription_tier_usage_limit(
    tier: str,
    therapist_id: str,
    aws_db_client: AwsDbBaseClass,
) -> bool:
    if tier == "premium":
        return False

    today = datetime.now().date()
    current_monday = today - timedelta(days=today.weekday())
    today_formatted = today.strftime(DATE_FORMAT)
    current_monday_formatted = current_monday.strftime(DATE_FORMAT)

    try:
        session_reports_data = await aws_db_client.select(
            user_id=therapist_id,
            fields=["*"],
            filters={
                "therapist_id": therapist_id,
                "created_at__gte": current_monday_formatted,
                "created_at__lte": today_formatted,
            },
            table_name=ENCRYPTED_SESSION_REPORTS_TABLE_NAME,
            limit=20,
        )
        return len(session_reports_data) >= NUM_SESSIONS_IN_FREEMIUM_TIER
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
    elif stripe_plan == "basic_plan_yearly" or stripe_plan == "basic_plan_monthly":
        return "basic"
    else:
        raise Exception("Untracked Stripe product name")

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
