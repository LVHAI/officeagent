from fastapi import FastAPI

app = FastAPI(title="OfficeAgent")


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/api/v1/chat")
async def chat(payload: dict):
    return {
        "answer": "Agent runtime initialized",
        "query": payload.get("query"),
        "sources": [],
    }
