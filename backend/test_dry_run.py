import asyncio
import httpx
import json

async def test():
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:8001/api/v1/leads/dry-run/test",
            json={
                "lead": {
                    "name": "GENERATOR SUPERCENTER OF ORLANDO",
                    "website": "https://www.generatorsupercenter.com/",
                    "domain": "generatorsupercenter.com",
                    "industry": "Generator Services"
                },
                "options": {
                    "stop_on_duplicate": False,
                    "skip_enrichment": False,
                    "create_in_crm": False,
                    "dry_run": True
                }
            },
            timeout=60.0
        )
        
        print(json.dumps(response.json(), indent=2))

asyncio.run(test())
