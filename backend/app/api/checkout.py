import stripe
from fastapi import APIRouter
from app.config import STRIPE_SECRET_KEY, STRIPE_SUCCESS_URL, STRIPE_CANCEL_URL

router = APIRouter()
stripe.api_key = STRIPE_SECRET_KEY

@router.post("/checkout/{file_id}")
def checkout(file_id: str):
    session = stripe.checkout.Session.create(
        mode="payment",
        payment_method_types=["card"],
        line_items=[{
            "price_data": {
                "currency": "usd",
                "product_data": {
                    "name": "CSV Processing",
                },
                "unit_amount": 500,  # $5.00
            },
            "quantity": 1,
        }],
        success_url=f"{STRIPE_SUCCESS_URL}?success=1",
        cancel_url=STRIPE_CANCEL_URL,
        metadata={
            "file_id": file_id
        }
    )

    return {
        "checkout_url": session.url
    }
