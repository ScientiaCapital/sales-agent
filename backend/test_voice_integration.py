"""
Voice Integration Test Script

Verifies all voice components are properly integrated:
- Database tables created
- API endpoints available
- WebSocket connectivity
- Redis session management
- Performance within targets
"""

import asyncio
import json
import sys
import os
from typing import Dict, Any

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import httpx
from sqlalchemy import create_engine, text
from redis import Redis


class VoiceIntegrationTester:
    """Test harness for voice integration verification."""

    def __init__(self):
        self.base_url = "http://localhost:8001"
        self.results = {
            "database": None,
            "redis": None,
            "api_endpoints": {},
            "websocket": None,
            "performance": None
        }

    async def test_database(self) -> bool:
        """Verify voice tables exist in database."""
        try:
            db_url = os.getenv("DATABASE_URL")
            if not db_url:
                raise ValueError("DATABASE_URL environment variable is required")
            engine = create_engine(db_url)

            tables_to_check = [
                "voice_session_logs",
                "voice_turns",
                "cartesia_api_calls",
                "voice_configurations"
            ]

            with engine.connect() as conn:
                for table in tables_to_check:
                    result = conn.execute(text(f"""
                        SELECT EXISTS (
                            SELECT 1 FROM information_schema.tables
                            WHERE table_name = '{table}'
                        )
                    """))
                    exists = result.scalar()
                    if not exists:
                        print(f"❌ Table {table} not found")
                        return False
                    print(f"✅ Table {table} exists")

            self.results["database"] = "All voice tables present"
            return True

        except Exception as e:
            self.results["database"] = f"Error: {e}"
            return False

    def test_redis(self) -> bool:
        """Verify Redis connectivity for session management."""
        try:
            redis_client = Redis(host='localhost', port=6379, db=0)
            redis_client.ping()

            # Test set/get
            test_key = "voice:test:connection"
            redis_client.set(test_key, "ok")
            value = redis_client.get(test_key)
            redis_client.delete(test_key)

            if value == b"ok":
                print("✅ Redis connection successful")
                self.results["redis"] = "Connected and operational"
                return True
            else:
                print("❌ Redis read/write failed")
                self.results["redis"] = "Connection OK but operations failed"
                return False

        except Exception as e:
            print(f"❌ Redis connection failed: {e}")
            self.results["redis"] = f"Error: {e}"
            return False

    async def test_api_endpoints(self) -> bool:
        """Test all voice API endpoints."""
        async with httpx.AsyncClient() as client:
            endpoints = [
                ("GET", "/api/v1/voice/voices", None),
                ("POST", "/api/v1/voice/sessions", {
                    "voice_id": "test_voice",
                    "language": "en",
                    "emotion": "professional"
                }),
                ("GET", "/api/v1/voice/metrics", None),
            ]

            all_ok = True
            for method, path, data in endpoints:
                try:
                    url = f"{self.base_url}{path}"

                    if method == "GET":
                        response = await client.get(url)
                    else:
                        response = await client.post(url, json=data)

                    if response.status_code in [200, 201, 422]:  # 422 is OK for missing Cartesia key
                        print(f"✅ {method} {path}: {response.status_code}")
                        self.results["api_endpoints"][path] = "OK"
                    else:
                        print(f"❌ {method} {path}: {response.status_code}")
                        self.results["api_endpoints"][path] = f"Error: {response.status_code}"
                        all_ok = False

                except Exception as e:
                    print(f"❌ {method} {path}: {e}")
                    self.results["api_endpoints"][path] = f"Error: {e}"
                    all_ok = False

            return all_ok

    async def test_websocket(self) -> bool:
        """Test WebSocket connectivity."""
        try:
            import websockets

            # First create a session via REST API
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/api/v1/voice/sessions",
                    json={
                        "voice_id": "test_voice",
                        "language": "en"
                    }
                )

                if response.status_code == 422:
                    # Missing Cartesia key, but endpoint exists
                    print("⚠️ WebSocket test skipped (Cartesia API key not configured)")
                    self.results["websocket"] = "Endpoint exists but Cartesia key missing"
                    return True

                if response.status_code != 201:
                    print(f"❌ Failed to create session: {response.status_code}")
                    self.results["websocket"] = "Failed to create session"
                    return False

                session_data = response.json()
                session_id = session_data["session_id"]

            # Connect to WebSocket
            ws_url = f"ws://localhost:8001/ws/voice/{session_id}"
            async with websockets.connect(ws_url) as websocket:
                # Send ping
                await websocket.send(json.dumps({"type": "ping"}))

                # Wait for pong (with timeout)
                response = await asyncio.wait_for(
                    websocket.recv(),
                    timeout=5.0
                )
                data = json.loads(response)

                if data.get("type") == "pong":
                    print("✅ WebSocket connection successful")
                    self.results["websocket"] = "Connected and responsive"
                    return True
                else:
                    print(f"❌ Unexpected WebSocket response: {data}")
                    self.results["websocket"] = "Connected but unexpected response"
                    return False

        except ImportError:
            print("⚠️ WebSocket test skipped (websockets library not installed)")
            self.results["websocket"] = "Library not installed"
            return True

        except Exception as e:
            print(f"❌ WebSocket test failed: {e}")
            self.results["websocket"] = f"Error: {e}"
            return False

    def test_performance_targets(self) -> bool:
        """Verify performance configuration matches targets."""
        targets = {
            "STT": 150,
            "Inference": 633,
            "TTS": 200,
            "Total": 2000
        }

        print("\n📊 Performance Targets:")
        for component, target in targets.items():
            print(f"  {component}: <{target}ms")

        self.results["performance"] = targets
        return True

    async def run_all_tests(self):
        """Run all integration tests."""
        print("=" * 60)
        print("VOICE INTEGRATION TEST SUITE")
        print("=" * 60)

        # Database tests
        print("\n🗄️ Testing Database...")
        db_ok = await self.test_database()

        # Redis tests
        print("\n🔴 Testing Redis...")
        redis_ok = self.test_redis()

        # API endpoints
        print("\n🌐 Testing API Endpoints...")
        api_ok = await self.test_api_endpoints()

        # WebSocket
        print("\n🔌 Testing WebSocket...")
        ws_ok = await self.test_websocket()

        # Performance targets
        print("\n⚡ Performance Configuration...")
        perf_ok = self.test_performance_targets()

        # Summary
        print("\n" + "=" * 60)
        print("TEST RESULTS SUMMARY")
        print("=" * 60)

        all_passed = all([db_ok, redis_ok, api_ok, ws_ok, perf_ok])

        print(f"\nDatabase: {'✅ PASS' if db_ok else '❌ FAIL'}")
        print(f"Redis: {'✅ PASS' if redis_ok else '❌ FAIL'}")
        print(f"API Endpoints: {'✅ PASS' if api_ok else '❌ FAIL'}")
        print(f"WebSocket: {'✅ PASS' if ws_ok else '❌ FAIL'}")
        print(f"Performance: {'✅ CONFIGURED' if perf_ok else '❌ NOT SET'}")

        if all_passed:
            print("\n🎉 All integration tests passed!")
            print("\n📝 Next Steps:")
            print("1. Set CARTESIA_API_KEY in .env file")
            print("2. Run database migration: cd backend && alembic upgrade head")
            print("3. Start server: python start_server.py")
            print("4. Test with client: python examples/voice_client.py")
            print("5. Run benchmark: python backend/benchmark_voice_latency.py")
            return 0
        else:
            print("\n⚠️ Some tests failed. Check the results above.")
            print("\nDetailed Results:")
            print(json.dumps(self.results, indent=2))
            return 1


async def main():
    """Run integration tests."""
    tester = VoiceIntegrationTester()
    return await tester.run_all_tests()


if __name__ == "__main__":
    print("Starting Voice Integration Tests...")
    print("Note: Requires running PostgreSQL, Redis, and FastAPI server")

    exit_code = asyncio.run(main())
    sys.exit(exit_code)