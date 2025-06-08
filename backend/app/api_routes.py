from app.bootstrap import chat_fn
from app.schemas import ChatRequest
from fastapi import APIRouter
from fastapi.responses import StreamingResponse

router = APIRouter()


@router.post("/chat")
async def chat_endpoint(req: ChatRequest):
    def response_stream():
        generator = chat_fn(
            question=req.question,
            history=req.history,
            media_type=req.media_type,
            genres=req.genres,
            providers=req.providers,
            year_range=tuple(req.year_range),
        )
        for chunk in generator:
            yield chunk

    return StreamingResponse(response_stream(), media_type="text/plain")
