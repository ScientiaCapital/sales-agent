import asyncio
import httpx
import os
import base64
from dotenv import load_dotenv

load_dotenv()

async def check():
    api_key = os.getenv("CLOSE_API_KEY")
    auth_header = f"Basic {base64.b64encode(f'{api_key}:'.encode()).decode()}"
    
    lead_id = "lead_DQoXeCmZOjle1ttuZ98JkBfclaYlJk7u3fGKRdq4QjI"
    
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"https://api.close.com/api/v1/lead/{lead_id}/",
            headers={"Authorization": auth_header},
            timeout=30.0
        )
        
        lead = response.json()
        
        print("\n🔍 Lead Creation Details:")
        print(f"   Company: {lead.get('name')}")
        print(f"   Status: {lead.get('status_label')}")
        print(f"   Status ID: {lead.get('status_id')}")
        print(f"   Created By: {lead.get('created_by')}")
        print()
        
        print("📋 Smart View Requires:")
        print(f"   Created By: user_RCfVbzPJJUMj6HDQ8JGtpBkouK7fMB25X15B08FUpt1")
        print(f"   Status ID: stat_KJzEuSMofAIQQf47CrtPl5o41RGFS325VeuzvtbJv0p")
        print()
        
        # Check if they match
        expected_user = "user_RCfVbzPJJUMj6HDQ8JGtpBkouK7fMB25X15B08FUpt1"
        actual_user = lead.get('created_by')
        
        expected_status = "stat_KJzEuSMofAIQQf47CrtPl5o41RGFS325VeuzvtbJv0p"
        actual_status = lead.get('status_id')
        
        print("✅ Matching:")
        if actual_user == expected_user:
            print(f"   ✅ Created By: MATCH!")
        else:
            print(f"   ❌ Created By: MISMATCH!")
            print(f"      Expected: {expected_user}")
            print(f"      Actual:   {actual_user}")
        
        if actual_status == expected_status:
            print(f"   ✅ Status: MATCH!")
        else:
            print(f"   ❌ Status: MISMATCH!")
        
        print()
        
        # Check env variable
        env_user = os.getenv("CLOSE_DEFAULT_OWNER_USER_ID")
        print(f"📝 .env has: CLOSE_DEFAULT_OWNER_USER_ID={env_user}")
        
        if env_user == expected_user:
            print(f"   ✅ .env matches smart view requirement!")
        else:
            print(f"   ❌ .env doesn't match!")
            print(f"      Smart view wants: {expected_user}")

asyncio.run(check())
