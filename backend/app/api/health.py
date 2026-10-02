from fastapi import APIRouter, Request, Response
from .db import make_engine
from .cache import make_redis

router = APIRouter()

@router.get("/health")
async def health_check(request: Request, response: Response) -> dict[str, str]:
    """
    Health check endpoint to verify the API is running.
    """
    try: 
        make_engine(request.app.state.engine.url)
    except Exception as e:
        response.status_code = 503
        return {"status": "Database not ready", "error": str(e)}
    
    try:
        make_redis(request.app.state.redis.url)
    except Exception as e:
        response.status_code = 503
        return {"status": "Redis not ready", "error": str(e)}

    return {"status": "healthy"}