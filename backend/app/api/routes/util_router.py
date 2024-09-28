from fastapi import APIRouter

router = APIRouter(
    prefix = "/api/util"
)


@router.get("/health-check/")
async def health_check() -> bool:
    return True
