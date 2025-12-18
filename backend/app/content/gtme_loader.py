"""
GTME Content Loader

Loads email sequences, SMS templates, and campaign content from coperniq-forge.
This bridges the GTME playbook (human-readable markdown) to the sequence engine (structured JSON).

Source: ~/Desktop/tk_projects/coperniq-forge/05-gtme-motions/
Target: sales-agent sequence engine format
"""
import os
import re
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# Path to GTME content repository
GTME_CONTENT_PATH = Path.home() / "Desktop" / "tk_projects" / "coperniq-forge" / "05-gtme-motions"


@dataclass
class SequenceStep:
    """Single step in an email sequence."""
    step_number: int
    day: int
    channel: str  # email, linkedin, phone, sms
    subject: str
    body: str
    delay_days: int = 0


@dataclass
class EmailSequence:
    """Full email sequence definition."""
    sequence_id: str
    name: str
    description: str
    target_segment: str
    steps: List[SequenceStep] = field(default_factory=list)
    
    def to_engine_format(self) -> Dict[str, Any]:
        """Convert to sequence engine format."""
        return {
            "sequence_id": self.sequence_id,
            "name": self.name,
            "steps": [
                {
                    "step_number": step.step_number,
                    "subject": step.subject,
                    "body": step.body,
                    "delay_days": step.delay_days,
                    "channel": step.channel,
                }
                for step in self.steps
                if step.channel == "email"  # Engine only handles email for now
            ],
            "stop_on_reply": True,
            "stop_on_bounce": True,
        }


class GTMEContentLoader:
    """
    Loads and parses GTME content from coperniq-forge.
    
    Supports:
    - Email sequences (markdown -> structured steps)
    - Value-add resources (markdown content)
    - Competitive intel (for battle cards)
    - Prospect research (for personalization)
    """
    
    def __init__(self, content_path: Optional[Path] = None):
        self.content_path = content_path or GTME_CONTENT_PATH
        self._sequences_cache: Dict[str, EmailSequence] = {}
        self._resources_cache: Dict[str, str] = {}
    
    def get_sequences_path(self) -> Path:
        return self.content_path / "sequences"
    
    def get_prospects_path(self) -> Path:
        return self.content_path / "prospects"
    
    def get_resources_path(self) -> Path:
        return self.content_path / "resources"
    
    def get_competitive_intel_path(self) -> Path:
        return self.content_path / "competitive-intel"
    
    # =========================================================================
    # SEQUENCE LOADING
    # =========================================================================
    
    def load_sequence(self, filename: str) -> Optional[EmailSequence]:
        """
        Load a sequence from markdown file.
        
        Args:
            filename: e.g., 'solar-plus-plus-sequence.md' or 'norrell-construction-sequence.md'
        
        Returns:
            EmailSequence object or None if not found
        """
        # Check sequences folder first, then prospects folder
        for folder in [self.get_sequences_path(), self.get_prospects_path()]:
            filepath = folder / filename
            if filepath.exists():
                return self._parse_sequence_markdown(filepath)
        
        logger.warning(f"Sequence file not found: {filename}")
        return None
    
    def load_all_sequences(self) -> Dict[str, EmailSequence]:
        """Load all available sequences."""
        sequences = {}
        
        for folder in [self.get_sequences_path(), self.get_prospects_path()]:
            if folder.exists():
                for filepath in folder.glob("*-sequence.md"):
                    seq = self._parse_sequence_markdown(filepath)
                    if seq:
                        sequences[seq.sequence_id] = seq
        
        self._sequences_cache = sequences
        logger.info(f"Loaded {len(sequences)} sequences from GTME content")
        return sequences
    
    def _parse_sequence_markdown(self, filepath: Path) -> Optional[EmailSequence]:
        """Parse a markdown sequence file into structured format."""
        try:
            content = filepath.read_text()
            
            # Extract sequence ID from filename
            sequence_id = filepath.stem.replace("-sequence", "").replace("-", "_")
            
            # Extract name from first H1
            name_match = re.search(r"^#\s+(.+?)(?:\s+-|$)", content, re.MULTILINE)
            name = name_match.group(1) if name_match else sequence_id
            
            # Parse steps - look for ## TOUCH N: patterns
            steps = []
            touch_pattern = r"##\s+TOUCH\s+(\d+):\s*(.+?)\s*\(Day\s+(\d+)\)"
            subject_pattern = r"\*\*Subject(?:\s+Options)?(?:\s*\(A/B test\))?:\*\*\s*\n(?:[-*]\s*[`'\"]?([^`'\"\n]+)[`'\"]?\n?)+"
            
            # Find all touches
            touches = list(re.finditer(touch_pattern, content, re.IGNORECASE))
            
            for i, touch_match in enumerate(touches):
                touch_num = int(touch_match.group(1))
                touch_type = touch_match.group(2).strip()
                day = int(touch_match.group(3))
                
                # Get content between this touch and next (or end)
                start = touch_match.end()
                end = touches[i + 1].start() if i + 1 < len(touches) else len(content)
                touch_content = content[start:end]
                
                # Determine channel
                channel = "email"
                if "linkedin" in touch_type.lower():
                    channel = "linkedin"
                elif "phone" in touch_type.lower():
                    channel = "phone"
                elif "sms" in touch_type.lower():
                    channel = "sms"
                
                # Extract subject for email touches
                subject = ""
                if channel == "email":
                    subj_match = re.search(r"\*\*Subject[^:]*:\*\*\s*[`'\"]?([^`'\"\n]+)", touch_content)
                    if subj_match:
                        subject = subj_match.group(1).strip()
                
                # Extract body - look for **Body:** section or code blocks
                body = ""
                body_match = re.search(r"\*\*(?:Email\s+)?Body:\*\*\s*\n([\s\S]+?)(?=\n---|\n##|\n\*\*[A-Z]|\Z)", touch_content)
                if body_match:
                    body = body_match.group(1).strip()
                else:
                    # Try finding content after subject
                    body_alt = re.search(r"(?:Subject[^\n]+\n\n)([\s\S]+?)(?=\n---|\n##|\Z)", touch_content)
                    if body_alt:
                        body = body_alt.group(1).strip()
                
                # Calculate delay from previous step
                delay_days = day if i == 0 else day - int(touches[i-1].group(3))
                
                steps.append(SequenceStep(
                    step_number=touch_num - 1,  # 0-indexed
                    day=day,
                    channel=channel,
                    subject=subject,
                    body=body,
                    delay_days=delay_days,
                ))
            
            return EmailSequence(
                sequence_id=sequence_id,
                name=name,
                description=f"Loaded from {filepath.name}",
                target_segment=sequence_id.split("_")[0],
                steps=steps,
            )
            
        except Exception as e:
            logger.error(f"Failed to parse sequence {filepath}: {e}")
            return None
    
    # =========================================================================
    # RESOURCE LOADING
    # =========================================================================
    
    def load_resource(self, filename: str) -> Optional[str]:
        """Load a value-add resource content."""
        filepath = self.get_resources_path() / filename
        if filepath.exists():
            return filepath.read_text()
        return None
    
    def get_field_to_office_gap(self) -> Optional[str]:
        """Load the Field-to-Office Gap resource."""
        return self.load_resource("field-to-office-gap.md")
    
    # =========================================================================
    # COMPETITIVE INTEL
    # =========================================================================
    
    def load_competitive_intel(self, competitor: str) -> Optional[str]:
        """Load competitive intel for a specific competitor."""
        filepath = self.get_competitive_intel_path() / f"{competitor.lower()}.md"
        if filepath.exists():
            return filepath.read_text()
        return None
    
    def get_buildops_intel(self) -> Optional[str]:
        """Load BuildOps competitive intelligence."""
        return self.load_competitive_intel("buildops")
    
    def get_market_data(self) -> Optional[str]:
        """Load market data and industry stats."""
        return self.load_competitive_intel("market-data")
    
    # =========================================================================
    # PROSPECT RESEARCH
    # =========================================================================
    
    def load_prospect_intel(self, company_slug: str) -> Optional[str]:
        """Load prospect research for a specific company."""
        filepath = self.get_prospects_path() / f"{company_slug}-intel.md"
        if filepath.exists():
            return filepath.read_text()
        return None
    
    def get_norrell_intel(self) -> Optional[str]:
        """Load Norrell Construction prospect intel."""
        return self.load_prospect_intel("norrell-construction")


# =========================================================================
# CONVENIENCE FUNCTIONS
# =========================================================================

def get_sequence_for_engine(sequence_name: str) -> Optional[Dict[str, Any]]:
    """
    Get a sequence in the format expected by SequenceEngine.create_sequence().
    
    Args:
        sequence_name: e.g., 'solar-plus-plus' or 'frankenstack' or 'norrell-construction'
    
    Returns:
        Dict ready to pass to create_sequence(), or None
    """
    loader = GTMEContentLoader()
    
    # Try different filename patterns
    for pattern in [f"{sequence_name}-sequence.md", f"{sequence_name.replace('_', '-')}-sequence.md"]:
        seq = loader.load_sequence(pattern)
        if seq:
            return seq.to_engine_format()
    
    return None


def list_available_sequences() -> List[str]:
    """List all available sequence IDs."""
    loader = GTMEContentLoader()
    sequences = loader.load_all_sequences()
    return list(sequences.keys())


def get_personalization_context(company_slug: str) -> Dict[str, str]:
    """
    Get personalization context for a prospect.
    
    Returns dict with keys like 'company_intel', 'competitive_context', 'value_add_resource'
    """
    loader = GTMEContentLoader()
    
    return {
        "prospect_intel": loader.load_prospect_intel(company_slug) or "",
        "competitive_context": loader.get_buildops_intel() or "",
        "market_data": loader.get_market_data() or "",
        "value_add_resource": loader.get_field_to_office_gap() or "",
    }
