from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from pathlib import Path

from mcp_client import preguntar_mcp

BASE_DIR = Path(__file__).parent
STATIC_DIR = BASE_DIR / "static"

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ChatRequest(BaseModel):
    message: str


@app.get("/")
async def root():
    return FileResponse(STATIC_DIR / "index.html")


@app.post("/api/chat")
async def chat(request: ChatRequest):
    try:
        respuesta = await preguntar_mcp(request.message)

        return {
            "answer": respuesta
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )
    
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "web_frontend:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )