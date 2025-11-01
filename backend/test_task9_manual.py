"""Manual test script for Task 9: QualificationAgent with cost tracking."""
import asyncio
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

from app.models.database import SessionLocal
from app.models.ai_cost_tracking import AICostTracking
from app.services.langgraph.agents.qualification_agent import QualificationAgent


async def test_qualification_with_cost_tracking():
    """Test QualificationAgent with cost tracking enabled."""

    print("=" * 80)
    print("Task 9 Manual Test: QualificationAgent with Cost Tracking")
    print("=" * 80)

    # Create database session
    db = SessionLocal()

    try:
        print("\n1. Creating QualificationAgent with db...")
        agent = QualificationAgent(db=db)
        print("   ✅ Agent created successfully")

        print("\n2. Qualifying test lead...")
        result, latency_ms, metadata = await agent.qualify(
            company_name="Task 9 Test Corp",
            industry="Commercial HVAC",
            company_size="100-500",
            contact_name="John Test",
            contact_title="Owner"
        )

        print(f"\n3. Qualification Results:")
        print(f"   Score: {result.qualification_score}")
        print(f"   Tier: {result.tier}")
        print(f"   Latency: {latency_ms}ms")
        print(f"   Provider: {metadata.get('provider')}")
        print(f"   Model: {metadata.get('model')}")

        # Performance check
        if latency_ms < 1000:
            print(f"   ✅ Performance target met: {latency_ms}ms < 1000ms")
        else:
            print(f"   ⚠️  Performance target exceeded: {latency_ms}ms >= 1000ms")

        print("\n4. Checking cost tracking in database...")
        tracking = db.query(AICostTracking).filter(
            AICostTracking.prompt_text.like("%Task 9 Test Corp%")
        ).order_by(AICostTracking.timestamp.desc()).first()

        if tracking:
            print(f"   ✅ Cost tracking record found:")
            print(f"      ID: {tracking.id}")
            print(f"      Agent Type: {tracking.agent_type}")
            print(f"      Agent Mode: {tracking.agent_mode}")
            print(f"      Provider: {tracking.provider}")
            print(f"      Model: {tracking.model}")
            print(f"      Cost: ${tracking.cost_usd}")
            print(f"      Latency: {tracking.latency_ms}ms")
            print(f"      Prompt Tokens: {tracking.prompt_tokens}")
            print(f"      Completion Tokens: {tracking.completion_tokens}")
            print(f"      Timestamp: {tracking.timestamp}")

            # Validate expectations
            errors = []
            if tracking.agent_type != "qualification":
                errors.append(f"Expected agent_type='qualification', got '{tracking.agent_type}'")
            if tracking.agent_mode != "passthrough":
                errors.append(f"Expected agent_mode='passthrough', got '{tracking.agent_mode}'")
            if tracking.provider != "cerebras":
                errors.append(f"Expected provider='cerebras', got '{tracking.provider}'")
            if tracking.model != "llama3.1-8b":
                errors.append(f"Expected model='llama3.1-8b', got '{tracking.model}'")
            if tracking.latency_ms >= 1000:
                errors.append(f"Latency too high: {tracking.latency_ms}ms >= 1000ms")

            if errors:
                print("\n   ⚠️  Validation errors:")
                for error in errors:
                    print(f"      - {error}")
            else:
                print("\n   ✅ All validation checks passed!")
        else:
            print("   ❌ No cost tracking record found in database")

        print("\n5. Testing backward compatibility (agent without db)...")
        agent_no_db = QualificationAgent()
        result2, latency2, metadata2 = await agent_no_db.qualify(
            company_name="Backward Compat Test",
            industry="HVAC",
            company_size="50-200"
        )
        print(f"   ✅ Backward compatibility works: {latency2}ms")

        print("\n6. Testing lead_id tracking...")
        result3, latency3, metadata3 = await agent.qualify(
            company_name="Lead ID Test Corp",
            lead_id=12345,  # Pass a lead_id
            industry="HVAC"
        )
        print(f"   Qualification complete: {latency3}ms")

        # Check database for lead_id
        tracking_with_lead = db.query(AICostTracking).filter_by(lead_id=12345).first()
        if tracking_with_lead:
            print(f"   ✅ lead_id captured: {tracking_with_lead.lead_id}")
        else:
            print("   ❌ lead_id NOT captured")

        print("\n" + "=" * 80)
        print("✅ Task 9 Manual Test Complete!")
        print("=" * 80)

    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()


if __name__ == "__main__":
    asyncio.run(test_qualification_with_cost_tracking())
