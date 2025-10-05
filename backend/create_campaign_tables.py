#!/usr/bin/env python3
"""
Database Migration: Create Campaign Tables

Creates the campaign, campaign_messages, and message_variant_analytics tables
for the outreach campaign system with A/B testing support.
"""

import sys
import os
from pathlib import Path
from sqlalchemy import create_engine, inspect

# Load environment variables from .env file
from dotenv import load_dotenv
env_path = Path(__file__).parent.parent / '.env'
load_dotenv(dotenv_path=env_path)

# Get DATABASE_URL from environment
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL environment variable is required")

# Convert postgresql:// to postgresql+psycopg://
if DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+psycopg://", 1)

# Create engine
engine = create_engine(DATABASE_URL, pool_pre_ping=True)

# Import campaign models directly to avoid importing other models that need pgvector
import sys
sys.path.insert(0, os.path.dirname(__file__))

# Import Base and campaign models without triggering __init__.py
from sqlalchemy.orm import declarative_base
from sqlalchemy import Column, Integer, String, Float, DateTime, Text, ForeignKey, JSON, Enum, Index, CheckConstraint
from datetime import datetime
import enum

# Define Base
Base = declarative_base()

# Define enums
class CampaignStatus(str, enum.Enum):
    draft = "draft"
    active = "active"
    paused = "paused"
    completed = "completed"

class CampaignChannel(str, enum.Enum):
    email = "email"
    linkedin = "linkedin"
    sms = "sms"

class MessageStatus(str, enum.Enum):
    pending = "pending"
    sent = "sent"
    opened = "opened"
    clicked = "clicked"
    replied = "replied"
    bounced = "bounced"
    failed = "failed"

class MessageTone(str, enum.Enum):
    professional = "professional"
    friendly = "friendly"
    direct = "direct"

# Define Campaign model
class Campaign(Base):
    __tablename__ = "campaigns"
    
    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    channel = Column(Enum(CampaignChannel), nullable=False)
    status = Column(Enum(CampaignStatus), default=CampaignStatus.draft, nullable=False)
    
    min_qualification_score = Column(Float)
    target_industries = Column(JSON)
    target_company_sizes = Column(JSON)
    message_template = Column(Text)
    custom_context = Column(Text)
    
    total_messages = Column(Integer, default=0)
    messages_sent = Column(Integer, default=0)
    messages_opened = Column(Integer, default=0)
    messages_clicked = Column(Integer, default=0)
    messages_replied = Column(Integer, default=0)
    total_cost = Column(Float, default=0.0)
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    
    __table_args__ = (
        Index("idx_campaigns_status", "status"),
        Index("idx_campaigns_channel", "channel"),
        Index("idx_campaigns_created_at", "created_at"),
    )

# Define CampaignMessage model
class CampaignMessage(Base):
    __tablename__ = "campaign_messages"
    
    id = Column(Integer, primary_key=True)
    campaign_id = Column(Integer, ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False)
    lead_id = Column(Integer, nullable=False)  # Foreign key to leads table (constraint added later)
    
    variants = Column(JSON, nullable=False)
    selected_variant = Column(Integer, default=0)
    status = Column(Enum(MessageStatus), default=MessageStatus.pending, nullable=False)
    
    sent_at = Column(DateTime)
    opened_at = Column(DateTime)
    clicked_at = Column(DateTime)
    replied_at = Column(DateTime)
    
    generation_cost = Column(Float, default=0.0)
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    __table_args__ = (
        Index("idx_campaign_messages_campaign_id", "campaign_id"),
        Index("idx_campaign_messages_lead_id", "lead_id"),
        Index("idx_campaign_messages_status", "status"),
        CheckConstraint("selected_variant >= 0 AND selected_variant <= 2", name="valid_variant_selection"),
    )

# Define MessageVariantAnalytics model
class MessageVariantAnalytics(Base):
    __tablename__ = "message_variant_analytics"
    
    id = Column(Integer, primary_key=True)
    message_id = Column(Integer, ForeignKey("campaign_messages.id", ondelete="CASCADE"), nullable=False)
    variant_number = Column(Integer, nullable=False)
    
    tone = Column(Enum(MessageTone), nullable=False)
    subject = Column(String(500))
    body = Column(Text, nullable=False)
    
    times_selected = Column(Integer, default=0)
    times_opened = Column(Integer, default=0)
    times_clicked = Column(Integer, default=0)
    times_replied = Column(Integer, default=0)
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    __table_args__ = (
        Index("idx_variant_analytics_message_id", "message_id"),
        Index("idx_variant_analytics_tone", "tone"),
        CheckConstraint("variant_number >= 0 AND variant_number <= 2", name="valid_variant_number"),
    )


def table_exists(table_name: str) -> bool:
    """Check if a table exists in the database."""
    inspector = inspect(engine)
    return table_name in inspector.get_table_names()


def create_campaign_tables():
    """
    Create campaign-related tables if they don't exist.
    
    Tables created:
    - campaigns: Main campaign configuration and metrics
    - campaign_messages: Individual messages with 3 variants per lead
    - message_variant_analytics: A/B testing performance tracking
    """
    print("🚀 Starting campaign tables migration...")
    print(f"📊 Database: {engine.url.database}")
    print()
    
    # Check existing tables
    print("🔍 Checking existing tables...")
    tables_to_create = []
    campaign_tables = ["campaigns", "campaign_messages", "message_variant_analytics"]
    
    for table_name in campaign_tables:
        exists = table_exists(table_name)
        status = "✅ EXISTS" if exists else "❌ MISSING"
        print(f"  {status}: {table_name}")
        if not exists:
            tables_to_create.append(table_name)
    
    print()
    
    if not tables_to_create:
        print("✨ All campaign tables already exist! No migration needed.")
        return True
    
    # Create missing tables
    print(f"📝 Creating {len(tables_to_create)} missing table(s)...")
    
    try:
        # Create only campaign-related tables
        Campaign.__table__.create(engine, checkfirst=True)
        print("  ✅ Created: campaigns")
        
        CampaignMessage.__table__.create(engine, checkfirst=True)
        print("  ✅ Created: campaign_messages")
        
        MessageVariantAnalytics.__table__.create(engine, checkfirst=True)
        print("  ✅ Created: message_variant_analytics")
        
        print()
        print("🎉 Campaign tables migration completed successfully!")
        print()
        
        # Display table details
        print("📋 Table Schema Summary:")
        print()
        
        print("1️⃣  campaigns:")
        print("   - Stores campaign configuration and targeting criteria")
        print("   - Tracks aggregate performance metrics (opens, clicks, replies)")
        print("   - Fields: name, channel, status, targeting filters, cost tracking")
        print()
        
        print("2️⃣  campaign_messages:")
        print("   - Stores individual messages with 3 variants per lead")
        print("   - Links to leads and campaigns")
        print("   - Fields: variants (JSON), selected_variant, status, timestamps")
        print()
        
        print("3️⃣  message_variant_analytics:")
        print("   - Tracks A/B testing performance per variant")
        print("   - Records opens, clicks, replies for each tone (professional/friendly/direct)")
        print("   - Fields: variant_number, tone, subject, body, performance counters")
        print()
        
        return True
        
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def verify_migration():
    """Verify all tables were created successfully."""
    print("🔬 Verifying migration...")
    
    all_exist = True
    for table_name in ["campaigns", "campaign_messages", "message_variant_analytics"]:
        exists = table_exists(table_name)
        status = "✅" if exists else "❌"
        print(f"  {status} {table_name}")
        if not exists:
            all_exist = False
    
    print()
    
    if all_exist:
        print("✅ All campaign tables verified successfully!")
        return True
    else:
        print("⚠️  Some tables are missing. Migration may have failed.")
        return False


if __name__ == "__main__":
    print("=" * 70)
    print("  CAMPAIGN TABLES MIGRATION")
    print("  Outreach Campaign System with A/B Testing")
    print("=" * 70)
    print()
    
    try:
        # Run migration
        success = create_campaign_tables()
        
        if success:
            # Verify migration
            verified = verify_migration()
            
            if verified:
                print("🎊 Migration complete! Campaign system is ready to use.")
                print()
                print("Next steps:")
                print("  1. Start the FastAPI server: python start_server.py")
                print("  2. Create a campaign: POST /api/v1/campaigns/create")
                print("  3. Generate messages: POST /api/v1/campaigns/{id}/generate-messages")
                print("  4. View analytics: GET /api/v1/campaigns/{id}/analytics")
                sys.exit(0)
            else:
                print("⚠️  Migration verification failed")
                sys.exit(1)
        else:
            print("❌ Migration failed")
            sys.exit(1)
            
    except Exception as e:
        print(f"💥 Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
