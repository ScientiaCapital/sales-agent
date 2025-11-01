"""Quick verification script for Task 9 database tracking."""
from dotenv import load_dotenv
from pathlib import Path

# Load environment
load_dotenv(Path(__file__).parent.parent / ".env")

from app.models.database import SessionLocal
from app.models.ai_cost_tracking import AICostTracking

db = SessionLocal()

print('=' * 80)
print('Task 9 Verification: Database Cost Tracking Records')
print('=' * 80)

try:
    total = db.query(AICostTracking).count()
    print(f'\n✅ ai_cost_tracking table exists')
    print(f'Total records: {total}')

    # Check for qualification records
    qual_records = db.query(AICostTracking).filter_by(agent_type='qualification').count()
    print(f'Qualification records: {qual_records}')

    if qual_records > 0:
        print('\n📊 Sample Qualification Records:')
        records = db.query(AICostTracking).filter_by(agent_type='qualification').limit(3).all()
        for i, record in enumerate(records, 1):
            print(f'\n  Record {i}:')
            print(f'    Agent: {record.agent_type} ({record.agent_mode})')
            print(f'    Provider: {record.provider}/{record.model}')
            print(f'    Cost: ${record.cost_usd}')
            print(f'    Latency: {record.latency_ms}ms')
            print(f'    Lead ID: {record.lead_id}')
            print(f'    Tokens: {record.prompt_tokens} in, {record.completion_tokens} out')
            print(f'    Timestamp: {record.timestamp}')
    else:
        print('\n⚠️  No qualification records found yet')
        print('This is expected if agent has not been used since migration')

except Exception as e:
    print(f'\n❌ Error: {e}')
    import traceback
    traceback.print_exc()
finally:
    db.close()

print('\n' + '=' * 80)
