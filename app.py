from pathlib import Path
import traceback
import uvicorn

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from backend import resume_travel_agent, run_travel_agent
# this is used for handle mutlievent loop in asyncio 
import nest_asyncio
nest_asyncio.apply()

BASE_DIR = Path(__file__).resolve().parent
app = FastAPI(
    title="AI Travel Planning System",
    description="LangGraph multi-Agent Travel planning system",
    version="1.0",
)


app.mount(
    "/static",
    StaticFiles(directory=str(BASE_DIR / "static")),
     name="static")
templates = Jinja2Templates(directory=str(BASE_DIR/"templates"))

class TravelRequest(BaseModel):
    message: str
    thread_id: str | None = None


class ResumeRequest(BaseModel):
    thread_id: str
    approved: bool
    feedback: str = ""


def _plan_response(result: dict):
    """Wrap a backend result in the success flag the page expects."""
    return {"success": True, **result}

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """Serve the TripMate page."""
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={}
    )
@app.post("/api/travel")
async def travel_planner(request_data: TravelRequest):
    """Start a trip. The graph pauses when the draft is ready for review."""
    try:
        user_message = request_data.message.strip()

        if not user_message:
            return JSONResponse(
                status_code=400,
                content={
                    "success": False,
                    "error": "Message cannot be empty."
                }
            )

        result = run_travel_agent(
            user_input=user_message,
            thread_id=request_data.thread_id
        )

        return JSONResponse(content=_plan_response(result))

    except Exception as e:
        print("ERROR:", e)
        traceback.print_exc()

        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": str(e)
            }
        )



@app.post("/api/travel/resume")
async def resume_planner(request_data: ResumeRequest):
    """Continue a paused trip after the user approves or requests changes."""
    try:
        thread_id = request_data.thread_id.strip()
        if not thread_id:
            return JSONResponse(
                status_code=400,
                content={
                    "success": False,
                    "error": "thread_id is required to resume a travel plan.",
                },
            )

        result = resume_travel_agent(
            thread_id=thread_id,
            approved=request_data.approved,
            feedback=request_data.feedback,
        )
        return JSONResponse(content=_plan_response(result))
    except Exception as e:
        print("ERROR:", e)
        traceback.print_exc()
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)},
        )


@app.get("/health")
async def health_check():
    return {
        "status": "ok",
        "message": "AI Travel Planner API is running"
    }


@app.get("/favicon.ico")
async def favicon():
    return JSONResponse(content={})



if __name__ == "__main__":
    uvicorn.run(
        "app:app",
        host="127.0.0.1",
        port=8000,
        reload=True
    )
