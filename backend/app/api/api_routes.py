from app.core.bootstrap import chat_fn
from app.api.schemas import ChatRequest, FinalRecsRequest
from app.services.usage_logger import log_final_results
from fastapi import APIRouter, HTTPException
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
            session_id=req.session_id,
            query_id=req.query_id,
            device_info=req.device_info,
        )
        for chunk in generator:
            yield chunk

    return StreamingResponse(response_stream(), media_type="text/plain")


@router.post("/log/final_recs")
async def log_final_recommendations(req: FinalRecsRequest):
    rows = [
        {
            "query_id": req.query_id,
            "media_id": rec.media_id,
            "is_final_rec": True,
            "why_summary": rec.why
        }
        for rec in req.final_recs
    ]

    try:
        log_final_results(rows)
        return {"status": "ok"}
    except Exception as e:
        print(f"❌ Error logging final recs: {e}")
        raise HTTPException(status_code=500, detail="Failed to log final recommendations")

