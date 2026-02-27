from fastapi import APIRouter

router = APIRouter()


@router.get("/success")
async def success():
    return {"status": "paid"}
