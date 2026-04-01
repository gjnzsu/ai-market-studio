import httpx
from backend.config import settings

class RAGConnector:
    def __init__(self, url: str = settings.rag_service_url):
        self.url = url

    async def query_research(self, question: str) -> dict:
        async with httpx.AsyncClient() as client:
            try:
                resp = await client.post(f"{self.url}/query", json={"question": question}, timeout=10.0)
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                return {"error": str(e)}
