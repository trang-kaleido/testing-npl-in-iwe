from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import httpx

LANGUAGETOOL_URL = "http://localhost:8081/v2/check"

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class AccuracyRequest(BaseModel):
    sentence: str


@app.post("/accuracy")
async def accuracy(req: AccuracyRequest):
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(
                LANGUAGETOOL_URL,
                data={"text": req.sentence, "language": "en-US"},
                timeout=10.0,
            )
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            raise HTTPException(status_code=502, detail=f"LanguageTool unreachable: {exc}")

    matches = resp.json().get("matches", [])
    return [
        {
            "span": {
                "from": m["offset"],
                "to": m["offset"] + m["length"],
            },
            "category": m["rule"]["category"]["id"],
            "message": m["message"],
            "replacements": [r["value"] for r in m.get("replacements", [])],
        }
        for m in matches
    ]
