"""
GTME Content Supabase Sync

Syncs GTME content from coperniq-forge markdown files to Supabase tables.
This enables agents to query content from the database instead of file system.

Tables:
- dim_gtme_sequences: Email/SMS/LinkedIn sequences
- dim_gtme_campaigns: Campaign strategies
- dim_gtme_scripts: Phone scripts
- dim_gtme_resources: Value-add content
- dim_gtme_prospects: Flagship prospect research

Usage:
    from app.content.gtme_supabase_sync import GTMESupabaseSync

    sync = GTMESupabaseSync()
    await sync.sync_all()
"""
import os
import re
import json
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

# Path to GTME content repository
GTME_CONTENT_PATH = Path.home() / "Desktop" / "tk_projects" / "coperniq-forge" / "05-gtme-motions"


class GTMESupabaseSync:
    """
    Syncs GTME markdown content to Supabase tables.

    Workflow:
    1. Read markdown files from coperniq-forge
    2. Parse into structured data
    3. Upsert to Supabase tables
    4. Agents query Supabase instead of file system
    """

    def __init__(self, supabase_client=None, content_path: Optional[Path] = None):
        """
        Initialize sync client.

        Args:
            supabase_client: Supabase client (will auto-create if None)
            content_path: Path to GTME content (defaults to coperniq-forge)
        """
        self.content_path = content_path or GTME_CONTENT_PATH
        self._client = supabase_client

    @property
    def client(self):
        """Lazy-load Supabase client."""
        if self._client is None:
            from supabase import create_client
            url = os.environ.get("SUPABASE_URL")
            key = os.environ.get("SUPABASE_SERVICE_KEY") or os.environ.get("SUPABASE_KEY")
            if not url or not key:
                raise ValueError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set")
            self._client = create_client(url, key)
        return self._client

    # =========================================================================
    # MAIN SYNC METHODS
    # =========================================================================

    async def sync_all(self, dry_run: bool = False) -> Dict[str, Any]:
        """
        Sync all GTME content to Supabase.

        Args:
            dry_run: If True, preview changes without writing

        Returns:
            Summary of sync results
        """
        results = {
            "sequences": await self.sync_sequences(dry_run),
            "campaigns": await self.sync_campaigns(dry_run),
            "scripts": await self.sync_scripts(dry_run),
            "resources": await self.sync_resources(dry_run),
            "prospects": await self.sync_prospects(dry_run),
            "timestamp": datetime.utcnow().isoformat(),
            "dry_run": dry_run,
        }

        total = sum(r.get("synced", 0) for r in results.values() if isinstance(r, dict))
        errors = sum(r.get("errors", 0) for r in results.values() if isinstance(r, dict))

        logger.info(f"GTME sync complete: {total} items synced, {errors} errors")
        return results

    # =========================================================================
    # SEQUENCE SYNC
    # =========================================================================

    async def sync_sequences(self, dry_run: bool = False) -> Dict[str, Any]:
        """Sync all sequences to dim_gtme_sequences."""
        sequences_path = self.content_path / "sequences"
        synced = 0
        errors = 0
        items = []

        if not sequences_path.exists():
            return {"synced": 0, "errors": 0, "message": "sequences folder not found"}

        for filepath in sequences_path.glob("*.md"):
            try:
                data = self._parse_sequence_file(filepath)
                if data:
                    items.append(data)
                    if not dry_run:
                        self._upsert_sequence(data)
                    synced += 1
            except Exception as e:
                logger.error(f"Failed to sync sequence {filepath.name}: {e}")
                errors += 1

        return {
            "synced": synced,
            "errors": errors,
            "items": items if dry_run else None,
        }

    def _parse_sequence_file(self, filepath: Path) -> Optional[Dict[str, Any]]:
        """Parse a sequence markdown file."""
        content = filepath.read_text()

        # Extract sequence key from filename
        sequence_key = filepath.stem

        # Determine campaign and sequence type
        campaign_type = "general"
        sequence_type = "warm"

        if "solar" in sequence_key.lower():
            campaign_type = "solar_plus_plus"
        elif "frankenstack" in sequence_key.lower():
            campaign_type = "frankenstack"

        if "cold" in sequence_key.lower():
            sequence_type = "cold"
        elif "followup" in sequence_key.lower():
            sequence_type = "followup"
        elif "breakup" in sequence_key.lower():
            sequence_type = "breakup"

        # Extract name from first H1
        name_match = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
        name = name_match.group(1).strip() if name_match else sequence_key

        # Parse steps
        steps = self._parse_sequence_steps(content)

        # Determine channels used
        channels = list(set(step.get("channel", "email") for step in steps))

        return {
            "sequence_key": sequence_key,
            "name": name,
            "campaign_type": campaign_type,
            "sequence_type": sequence_type,
            "description": f"Synced from {filepath.name}",
            "steps": steps,
            "channels_used": channels,
            "is_active": True,
            "synced_from_file": str(filepath),
        }

    def _parse_sequence_steps(self, content: str) -> List[Dict[str, Any]]:
        """Parse sequence steps from markdown content."""
        steps = []

        # Pattern for ## TOUCH N: Type (Day X) or ## Email N: Title
        touch_patterns = [
            r"##\s+TOUCH\s+(\d+):\s*(.+?)\s*\(Day\s+(\d+)\)",
            r"##\s+Email\s+(\d+):\s*(.+)",
        ]

        for pattern in touch_patterns:
            matches = list(re.finditer(pattern, content, re.IGNORECASE))
            if matches:
                for i, match in enumerate(matches):
                    step_num = int(match.group(1))
                    touch_type = match.group(2).strip()

                    # Extract day if present
                    day = 0
                    if len(match.groups()) >= 3:
                        day = int(match.group(3))
                    else:
                        day = i * 3  # Default 3-day spacing

                    # Get content between this and next match
                    start = match.end()
                    end = matches[i + 1].start() if i + 1 < len(matches) else len(content)
                    step_content = content[start:end]

                    # Determine channel
                    channel = "email"
                    touch_lower = touch_type.lower()
                    if "sms" in touch_lower:
                        channel = "sms"
                    elif "linkedin" in touch_lower:
                        channel = "linkedin"
                    elif "phone" in touch_lower or "call" in touch_lower:
                        channel = "phone"

                    # Extract subject
                    subject = ""
                    subj_match = re.search(r"\*\*Subject[^:]*:\*\*\s*(.+?)(?:\n|$)", step_content)
                    if subj_match:
                        subject = subj_match.group(1).strip().strip("`'\"")

                    # Extract body
                    body = ""
                    body_match = re.search(r"\*\*(?:Body|Message|Script):\*\*\s*\n([\s\S]+?)(?=\n---|\n##|\n\*\*[A-Z]|\Z)", step_content)
                    if body_match:
                        body = body_match.group(1).strip()

                    steps.append({
                        "step_number": step_num - 1,
                        "day": day,
                        "channel": channel,
                        "subject": subject,
                        "body": body,
                        "delay_days": day if i == 0 else day - steps[-1]["day"] if steps else 0,
                    })
                break

        return steps

    def _upsert_sequence(self, data: Dict[str, Any]):
        """Upsert sequence to Supabase."""
        self.client.table("dim_gtme_sequences").upsert(
            data,
            on_conflict="sequence_key"
        ).execute()

    # =========================================================================
    # CAMPAIGN SYNC
    # =========================================================================

    async def sync_campaigns(self, dry_run: bool = False) -> Dict[str, Any]:
        """Sync campaigns to dim_gtme_campaigns."""
        campaigns_path = self.content_path / "campaigns"
        synced = 0
        errors = 0
        items = []

        if not campaigns_path.exists():
            return {"synced": 0, "errors": 0, "message": "campaigns folder not found"}

        for filepath in campaigns_path.glob("*.md"):
            try:
                data = self._parse_campaign_file(filepath)
                if data:
                    items.append(data)
                    if not dry_run:
                        self._upsert_campaign(data)
                    synced += 1
            except Exception as e:
                logger.error(f"Failed to sync campaign {filepath.name}: {e}")
                errors += 1

        return {"synced": synced, "errors": errors, "items": items if dry_run else None}

    def _parse_campaign_file(self, filepath: Path) -> Optional[Dict[str, Any]]:
        """Parse a campaign strategy markdown file."""
        content = filepath.read_text()
        campaign_key = filepath.stem

        # Extract name
        name_match = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
        name = name_match.group(1).strip() if name_match else campaign_key

        # Extract target segment
        target_match = re.search(r"\*\*Who:\*\*\s*(.+?)(?:\n|$)", content)
        target_segment = target_match.group(1).strip() if target_match else ""

        # Extract signals (look for bullet list after **Signals:**)
        signals = []
        signals_match = re.search(r"\*\*Signals:\*\*\s*\n((?:[-*]\s+.+\n)+)", content)
        if signals_match:
            for line in signals_match.group(1).strip().split("\n"):
                signal = line.strip().lstrip("-* ").strip()
                if signal:
                    signals.append({"signal": signal})

        # Extract messaging framework
        messaging = {}
        pain_match = re.search(r"\*\*Primary Pain:\*\*\s*[\"']?(.+?)[\"']?\s*\n", content)
        if pain_match:
            messaging["primary_pain"] = pain_match.group(1).strip()

        narrative_match = re.search(r"\*\*Core Narrative:\*\*\s*\n(.+?)(?=\n\*\*|\n##|\Z)", content, re.DOTALL)
        if narrative_match:
            messaging["core_narrative"] = narrative_match.group(1).strip()

        value_match = re.search(r"\*\*Value Prop:\*\*\s*(.+?)(?:\n|$)", content)
        if value_match:
            messaging["value_prop"] = value_match.group(1).strip()

        # Extract objection handling (look for table or list)
        objections = []
        objection_section = re.search(r"## Objection Handling\s*\n([\s\S]+?)(?=\n##|\Z)", content)
        if objection_section:
            table_rows = re.findall(r"\|\s*\"?([^|\"]+)\"?\s*\|\s*\"?([^|\"]+)\"?\s*\|", objection_section.group(1))
            for obj, resp in table_rows:
                if obj.strip() and resp.strip() and "Objection" not in obj:
                    objections.append({
                        "objection": obj.strip(),
                        "response": resp.strip()
                    })

        return {
            "campaign_key": campaign_key,
            "name": name,
            "target_segment": target_segment,
            "target_signals": signals,
            "messaging_framework": messaging,
            "objection_handling": objections,
            "is_active": True,
            "synced_from_file": str(filepath),
        }

    def _upsert_campaign(self, data: Dict[str, Any]):
        """Upsert campaign to Supabase."""
        self.client.table("dim_gtme_campaigns").upsert(
            data,
            on_conflict="campaign_key"
        ).execute()

    # =========================================================================
    # SCRIPTS SYNC
    # =========================================================================

    async def sync_scripts(self, dry_run: bool = False) -> Dict[str, Any]:
        """Sync phone scripts to dim_gtme_scripts."""
        scripts_path = self.content_path / "scripts"
        synced = 0
        errors = 0
        items = []

        if not scripts_path.exists():
            return {"synced": 0, "errors": 0, "message": "scripts folder not found"}

        for filepath in scripts_path.glob("*.md"):
            try:
                data = self._parse_script_file(filepath)
                if data:
                    items.append(data)
                    if not dry_run:
                        self._upsert_script(data)
                    synced += 1
            except Exception as e:
                logger.error(f"Failed to sync script {filepath.name}: {e}")
                errors += 1

        return {"synced": synced, "errors": errors, "items": items if dry_run else None}

    def _parse_script_file(self, filepath: Path) -> Optional[Dict[str, Any]]:
        """Parse a phone script markdown file."""
        content = filepath.read_text()
        script_key = filepath.stem

        # Extract name
        name_match = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
        name = name_match.group(1).strip() if name_match else script_key

        # Determine campaign key
        campaign_key = None
        if "solar" in script_key.lower():
            campaign_key = "solar-plus-plus"
        elif "frankenstack" in script_key.lower():
            campaign_key = "frankenstack"

        # Extract style
        style_match = re.search(r"\*\*Style:\*\*\s*(.+?)(?:\n|$)", content)
        style = style_match.group(1).strip() if style_match else ""

        # Extract cold openers
        cold_openers = []
        cold_section = re.search(r"## COLD OPENING[^\n]*\n([\s\S]+?)(?=\n## |\Z)", content)
        if cold_section:
            options = re.findall(r"\*\*Option ([A-Z])[^:]*:\*\*\s*\n>\s*[\"']?(.+?)[\"']?\s*\n", cold_section.group(1))
            for opt, script in options:
                cold_openers.append({"option": opt, "script": script.strip()})

        # Extract warm opener
        warm_opener = ""
        warm_section = re.search(r"## WARM OPENING[^\n]*\n([\s\S]+?)(?=\n## |\Z)", content)
        if warm_section:
            opener_match = re.search(r"[\"'](.+?)[\"']", warm_section.group(1))
            if opener_match:
                warm_opener = opener_match.group(1).strip()

        # Extract response paths
        response_paths = []
        paths_section = re.search(r"## RESPONSE PATHS\s*\n([\s\S]+?)(?=\n## VOICEMAIL|\Z)", content)
        if paths_section:
            path_matches = re.findall(r"### Path (\d+):\s*[\"']?(.+?)[\"']?\s*\n([\s\S]+?)(?=\n### Path |\n## |\Z)", paths_section.group(1))
            for num, trigger, script in path_matches:
                response_paths.append({
                    "path_name": f"Path {num}",
                    "trigger": trigger.strip(),
                    "script": script.strip()
                })

        # Extract voicemail
        voicemail = ""
        vm_section = re.search(r"## VOICEMAIL[^\n]*\n([\s\S]+?)(?=\n## |\Z)", content)
        if vm_section:
            vm_match = re.search(r"[\"'](.+?)[\"']", vm_section.group(1), re.DOTALL)
            if vm_match:
                voicemail = vm_match.group(1).strip()

        return {
            "script_key": script_key,
            "name": name,
            "campaign_key": campaign_key,
            "cold_openers": cold_openers,
            "warm_opener": warm_opener,
            "response_paths": response_paths,
            "voicemail": voicemail,
            "style": style,
            "is_active": True,
            "synced_from_file": str(filepath),
        }

    def _upsert_script(self, data: Dict[str, Any]):
        """Upsert script to Supabase."""
        self.client.table("dim_gtme_scripts").upsert(
            data,
            on_conflict="script_key"
        ).execute()

    # =========================================================================
    # RESOURCES SYNC
    # =========================================================================

    async def sync_resources(self, dry_run: bool = False) -> Dict[str, Any]:
        """Sync resources to dim_gtme_resources."""
        resources_path = self.content_path / "resources"
        synced = 0
        errors = 0
        items = []

        if not resources_path.exists():
            return {"synced": 0, "errors": 0, "message": "resources folder not found"}

        for filepath in resources_path.glob("*.md"):
            try:
                data = self._parse_resource_file(filepath)
                if data:
                    items.append(data)
                    if not dry_run:
                        self._upsert_resource(data)
                    synced += 1
            except Exception as e:
                logger.error(f"Failed to sync resource {filepath.name}: {e}")
                errors += 1

        return {"synced": synced, "errors": errors, "items": items if dry_run else None}

    def _parse_resource_file(self, filepath: Path) -> Optional[Dict[str, Any]]:
        """Parse a resource markdown file."""
        content = filepath.read_text()
        resource_key = filepath.stem

        # Extract title from first H1
        title_match = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
        title = title_match.group(1).strip() if title_match else resource_key

        # Extract summary (first paragraph after title)
        summary_match = re.search(r"^#.+\n\n(.+?)(?:\n\n|\Z)", content, re.MULTILINE)
        summary = summary_match.group(1).strip() if summary_match else ""

        return {
            "resource_key": resource_key,
            "title": title,
            "content_markdown": content,
            "summary": summary[:500],  # Truncate for summary field
            "use_case": "touch_3_value_add",
            "recommended_for": ["solar_plus_plus", "frankenstack"],
            "is_active": True,
            "synced_from_file": str(filepath),
        }

    def _upsert_resource(self, data: Dict[str, Any]):
        """Upsert resource to Supabase."""
        self.client.table("dim_gtme_resources").upsert(
            data,
            on_conflict="resource_key"
        ).execute()

    # =========================================================================
    # PROSPECTS SYNC
    # =========================================================================

    async def sync_prospects(self, dry_run: bool = False) -> Dict[str, Any]:
        """Sync prospect research to dim_gtme_prospects."""
        prospects_path = self.content_path / "prospects"
        synced = 0
        errors = 0
        items = []

        if not prospects_path.exists():
            return {"synced": 0, "errors": 0, "message": "prospects folder not found"}

        for filepath in prospects_path.glob("*-intel.md"):
            try:
                data = self._parse_prospect_file(filepath)
                if data:
                    items.append(data)
                    if not dry_run:
                        self._upsert_prospect(data)
                    synced += 1
            except Exception as e:
                logger.error(f"Failed to sync prospect {filepath.name}: {e}")
                errors += 1

        return {"synced": synced, "errors": errors, "items": items if dry_run else None}

    def _parse_prospect_file(self, filepath: Path) -> Optional[Dict[str, Any]]:
        """Parse a prospect intel markdown file."""
        content = filepath.read_text()
        prospect_key = filepath.stem.replace("-intel", "")

        # Extract company name from first H1
        name_match = re.search(r"^#\s+(.+?)(?:\s+-|\s*$)", content, re.MULTILINE)
        company_name = name_match.group(1).strip() if name_match else prospect_key

        # Extract intel sections as JSON
        intel = {}

        # Services
        services_match = re.search(r"\*\*Services:\*\*\s*(.+?)(?:\n|$)", content)
        if services_match:
            intel["services"] = services_match.group(1).strip()

        # Size/employees
        size_match = re.search(r"\*\*(?:Size|Employees):\*\*\s*(.+?)(?:\n|$)", content)
        if size_match:
            intel["size"] = size_match.group(1).strip()

        return {
            "prospect_key": prospect_key,
            "company_name": company_name,
            "intel": intel,
            "discovery_questions": [],
            "pain_indicators": [],
            "target_contacts": [],
            "status": "researched",
            "synced_from_file": str(filepath),
        }

    def _upsert_prospect(self, data: Dict[str, Any]):
        """Upsert prospect to Supabase."""
        self.client.table("dim_gtme_prospects").upsert(
            data,
            on_conflict="prospect_key"
        ).execute()


# =========================================================================
# CLI ENTRY POINT
# =========================================================================

async def main():
    """CLI entry point for syncing."""
    import sys
    import asyncio

    logging.basicConfig(level=logging.INFO)

    sync = GTMESupabaseSync()

    if "--dry-run" in sys.argv:
        print("\n🔍 DRY RUN - Preview only, no changes will be made\n")
        results = await sync.sync_all(dry_run=True)
    else:
        print("\n🚀 Syncing GTME content to Supabase...\n")
        results = await sync.sync_all(dry_run=False)

    print("\n" + "=" * 60)
    print("GTME SYNC RESULTS")
    print("=" * 60)

    for category, result in results.items():
        if isinstance(result, dict) and "synced" in result:
            status = "✅" if result["errors"] == 0 else "⚠️"
            print(f"{status} {category}: {result['synced']} synced, {result['errors']} errors")

    print("=" * 60 + "\n")


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
