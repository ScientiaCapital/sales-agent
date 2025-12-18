#!/usr/bin/env python3
"""
Example: Load GTME sequences and sync to database.

Run from sales-agent root:
    python -m backend.app.content.sync_sequences
"""
import asyncio
import logging
from app.content import GTMEContentLoader, get_sequence_for_engine, list_available_sequences

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def preview_sequences():
    """Preview all available sequences without database."""
    loader = GTMEContentLoader()
    sequences = loader.load_all_sequences()
    
    print(f"\n{'='*60}")
    print(f"GTME Sequences Available: {len(sequences)}")
    print(f"{'='*60}\n")
    
    for seq_id, seq in sequences.items():
        print(f"📧 {seq.name}")
        print(f"   ID: {seq_id}")
        print(f"   Steps: {len(seq.steps)}")
        for step in seq.steps:
            print(f"   └─ Day {step.day}: [{step.channel}] {step.subject[:50]}..." if step.subject else f"   └─ Day {step.day}: [{step.channel}]")
        print()
    
    # Show engine format for one
    print(f"{'='*60}")
    print("Engine Format Example (solar_plus_plus):")
    print(f"{'='*60}")
    engine_data = get_sequence_for_engine("solar-plus-plus")
    if engine_data:
        import json
        print(json.dumps(engine_data, indent=2, default=str)[:2000])


async def sync_to_database():
    """Sync sequences to database (requires running server)."""
    from app.models.database import get_session
    from app.services.sequences.engine import SequenceEngine
    
    async with get_session() as session:
        engine = SequenceEngine(session)
        
        for seq_name in list_available_sequences():
            seq_data = get_sequence_for_engine(seq_name)
            if seq_data and seq_data.get("steps"):
                try:
                    await engine.create_sequence(**seq_data)
                    logger.info(f"✓ Created sequence: {seq_name}")
                except Exception as e:
                    logger.warning(f"⚠ Sequence {seq_name} may already exist: {e}")


if __name__ == "__main__":
    import sys
    
    if "--sync" in sys.argv:
        asyncio.run(sync_to_database())
    else:
        asyncio.run(preview_sequences())
