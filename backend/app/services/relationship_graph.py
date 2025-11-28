"""
Relationship Graph Service - Neo4j-powered warm path discovery

Enables "dot-connecting" for sales outreach:
- Find shared past companies between leads and known contacts
- Discover warm introduction paths
- Generate personalized openers based on relationships

Schema:
    (:Person {linkedin_url, name, email, is_our_contact})
    (:Company {name, domain, linkedin_url})

    (:Person)-[:WORKS_AT {title, since}]->(:Company)
    (:Person)-[:WORKED_AT {title, from, to}]->(:Company)  # Past companies!
    (:Person)-[:KNOWS {relationship, strength}]->(:Person)
    (:Company)-[:HAS_DEAL {status, value}]->(:Deal)
"""

import os
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime
from dataclasses import dataclass, asdict

logger = logging.getLogger(__name__)

# Neo4j driver import
try:
    from neo4j import GraphDatabase, AsyncGraphDatabase
    NEO4J_AVAILABLE = True
except ImportError:
    NEO4J_AVAILABLE = False
    logger.warning("neo4j package not installed - pip install neo4j")


@dataclass
class WarmPath:
    """A warm introduction path through shared companies/connections."""
    target_name: str
    target_linkedin_url: str
    via_company: str
    known_contact_name: str
    known_contact_email: Optional[str]
    relationship_type: str  # "past_colleague", "current_colleague", "deal_closed"
    warmth_score: int  # 0-100, higher = warmer
    suggested_opener: str

    def to_dict(self) -> dict:
        return asdict(self)


class RelationshipGraphService:
    """
    Neo4j-powered relationship mapping for warm outreach.

    Key Features:
    - Index contacts and their past companies
    - Find warm paths between new leads and known contacts
    - Generate personalized openers based on shared history
    - Track relationship strength and deal history

    Usage:
        graph = RelationshipGraphService()
        await graph.connect()

        # Add a contact with their work history
        await graph.add_person_with_experience(
            linkedin_url="https://linkedin.com/in/johndoe",
            name="John Doe",
            email="john@company.com",
            is_our_contact=True,
            experience=[
                {"company": "ABC Corp", "title": "VP Sales", "current": False},
                {"company": "TechCorp", "title": "CEO", "current": True}
            ]
        )

        # Find warm paths to a new lead
        paths = await graph.find_warm_paths("https://linkedin.com/in/newlead")
    """

    def __init__(
        self,
        uri: Optional[str] = None,
        user: Optional[str] = None,
        password: Optional[str] = None
    ):
        """
        Initialize the relationship graph service.

        Args:
            uri: Neo4j Bolt URI (default: from NEO4J_URI env var or localhost)
            user: Neo4j username (default: from NEO4J_USER env var or 'neo4j')
            password: Neo4j password (default: from NEO4J_PASSWORD env var)
        """
        self.uri = uri or os.getenv("NEO4J_URI", "bolt://localhost:7687")
        self.user = user or os.getenv("NEO4J_USER", "neo4j")
        self.password = password or os.getenv("NEO4J_PASSWORD", "coperniq_graph_2024")

        self._driver = None
        self._async_driver = None

        if not NEO4J_AVAILABLE:
            logger.error("Neo4j driver not available - install with: pip install neo4j")

    # ========================================================================
    # CONNECTION MANAGEMENT
    # ========================================================================

    def connect(self) -> bool:
        """Connect to Neo4j (sync driver for scripts)."""
        if not NEO4J_AVAILABLE:
            return False

        try:
            self._driver = GraphDatabase.driver(
                self.uri,
                auth=(self.user, self.password)
            )
            self._driver.verify_connectivity()
            logger.info(f"Connected to Neo4j at {self.uri}")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to Neo4j: {e}")
            return False

    async def connect_async(self) -> bool:
        """Connect to Neo4j (async driver for API endpoints)."""
        if not NEO4J_AVAILABLE:
            return False

        try:
            self._async_driver = AsyncGraphDatabase.driver(
                self.uri,
                auth=(self.user, self.password)
            )
            await self._async_driver.verify_connectivity()
            logger.info(f"Connected to Neo4j (async) at {self.uri}")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to Neo4j (async): {e}")
            return False

    def close(self):
        """Close the sync driver."""
        if self._driver:
            self._driver.close()

    async def close_async(self):
        """Close the async driver."""
        if self._async_driver:
            await self._async_driver.close()

    # ========================================================================
    # SCHEMA INITIALIZATION
    # ========================================================================

    def init_schema(self):
        """Initialize Neo4j constraints and indexes for optimal performance."""
        if not self._driver:
            raise RuntimeError("Not connected to Neo4j - call connect() first")

        with self._driver.session() as session:
            # Constraints for uniqueness
            constraints = [
                "CREATE CONSTRAINT person_linkedin IF NOT EXISTS FOR (p:Person) REQUIRE p.linkedin_url IS UNIQUE",
                "CREATE CONSTRAINT company_domain IF NOT EXISTS FOR (c:Company) REQUIRE c.domain IS UNIQUE",
            ]

            # Indexes for fast lookups
            indexes = [
                "CREATE INDEX person_name IF NOT EXISTS FOR (p:Person) ON (p.name)",
                "CREATE INDEX person_email IF NOT EXISTS FOR (p:Person) ON (p.email)",
                "CREATE INDEX company_name IF NOT EXISTS FOR (c:Company) ON (c.name)",
                "CREATE INDEX person_is_our_contact IF NOT EXISTS FOR (p:Person) ON (p.is_our_contact)",
            ]

            for query in constraints + indexes:
                try:
                    session.run(query)
                except Exception as e:
                    logger.debug(f"Schema query note: {e}")

            logger.info("Neo4j schema initialized (constraints + indexes)")

    # ========================================================================
    # DATA INGESTION
    # ========================================================================

    def add_person_with_experience(
        self,
        linkedin_url: str,
        name: str,
        email: Optional[str] = None,
        is_our_contact: bool = False,
        experience: List[Dict[str, Any]] = None,
        current_company: Optional[str] = None,
        current_title: Optional[str] = None
    ) -> bool:
        """
        Add a person and their work experience to the graph.

        Args:
            linkedin_url: LinkedIn profile URL (unique identifier)
            name: Full name
            email: Email address
            is_our_contact: True if this is someone we know/sold to
            experience: List of work history entries:
                [{"company": "ABC Corp", "title": "VP Sales", "current": False, "domain": "abc.com"}]
            current_company: Current employer name
            current_title: Current job title

        Returns:
            True if successful
        """
        if not self._driver:
            raise RuntimeError("Not connected to Neo4j - call connect() first")

        experience = experience or []

        with self._driver.session() as session:
            # Create or update Person node
            session.run("""
                MERGE (p:Person {linkedin_url: $linkedin_url})
                SET p.name = $name,
                    p.email = $email,
                    p.is_our_contact = $is_our_contact,
                    p.current_company = $current_company,
                    p.current_title = $current_title,
                    p.updated_at = datetime()
            """,
                linkedin_url=linkedin_url,
                name=name,
                email=email,
                is_our_contact=is_our_contact,
                current_company=current_company,
                current_title=current_title
            )

            # Add work experience relationships
            for exp in experience:
                company_name = exp.get("company", "").strip()
                if not company_name:
                    continue

                # Normalize company name for matching
                company_key = company_name.lower().replace(" ", "_").replace(",", "")
                domain = exp.get("domain", f"{company_key}.com")

                is_current = exp.get("current", False)
                title = exp.get("title", "")

                if is_current:
                    # WORKS_AT relationship (current job)
                    session.run("""
                        MERGE (c:Company {domain: $domain})
                        SET c.name = $company_name, c.normalized_name = $company_key
                        WITH c
                        MATCH (p:Person {linkedin_url: $linkedin_url})
                        MERGE (p)-[r:WORKS_AT]->(c)
                        SET r.title = $title, r.since = datetime()
                    """,
                        linkedin_url=linkedin_url,
                        domain=domain,
                        company_name=company_name,
                        company_key=company_key,
                        title=title
                    )
                else:
                    # WORKED_AT relationship (past job) - THE GOLD!
                    session.run("""
                        MERGE (c:Company {domain: $domain})
                        SET c.name = $company_name, c.normalized_name = $company_key
                        WITH c
                        MATCH (p:Person {linkedin_url: $linkedin_url})
                        MERGE (p)-[r:WORKED_AT]->(c)
                        SET r.title = $title, r.indexed_at = datetime()
                    """,
                        linkedin_url=linkedin_url,
                        domain=domain,
                        company_name=company_name,
                        company_key=company_key,
                        title=title
                    )

        logger.info(f"Added person to graph: {name} ({len(experience)} companies)")
        return True

    def mark_as_our_contact(
        self,
        linkedin_url: str,
        relationship_type: str = "deal_closed",
        notes: Optional[str] = None
    ):
        """Mark a person as one of our contacts (someone we know/sold to)."""
        if not self._driver:
            raise RuntimeError("Not connected to Neo4j")

        with self._driver.session() as session:
            session.run("""
                MATCH (p:Person {linkedin_url: $linkedin_url})
                SET p.is_our_contact = true,
                    p.relationship_type = $relationship_type,
                    p.contact_notes = $notes,
                    p.marked_at = datetime()
            """,
                linkedin_url=linkedin_url,
                relationship_type=relationship_type,
                notes=notes
            )

    # ========================================================================
    # WARM PATH DISCOVERY - THE MAGIC!
    # ========================================================================

    def find_warm_paths(
        self,
        target_linkedin_url: str,
        max_paths: int = 5
    ) -> List[WarmPath]:
        """
        Find warm introduction paths to a target lead.

        This is the GOLD - finds shared past companies between the target
        and people we know, enabling warm openers like:
        "Sarah from ABC Corp mentioned I should give you a call"

        Args:
            target_linkedin_url: LinkedIn URL of the lead
            max_paths: Maximum number of paths to return

        Returns:
            List of WarmPath objects, sorted by warmth score (highest first)
        """
        if not self._driver:
            raise RuntimeError("Not connected to Neo4j")

        warm_paths = []

        with self._driver.session() as session:
            # Query 1: Find paths through PAST companies (WORKED_AT)
            result = session.run("""
                MATCH (target:Person {linkedin_url: $target_url})
                MATCH (target)-[:WORKED_AT]->(company:Company)<-[:WORKED_AT|WORKS_AT]-(known:Person {is_our_contact: true})
                WHERE target <> known
                RETURN
                    target.name AS target_name,
                    target.linkedin_url AS target_linkedin,
                    company.name AS company_name,
                    known.name AS known_name,
                    known.email AS known_email,
                    known.relationship_type AS rel_type,
                    'past_colleague' AS path_type
                ORDER BY known.relationship_type DESC
                LIMIT $max_paths
            """, target_url=target_linkedin_url, max_paths=max_paths)

            for record in result:
                warmth = self._calculate_warmth(record["path_type"], record["rel_type"])
                opener = self._generate_opener(
                    record["known_name"],
                    record["company_name"],
                    record["path_type"]
                )

                warm_paths.append(WarmPath(
                    target_name=record["target_name"] or "Lead",
                    target_linkedin_url=record["target_linkedin"],
                    via_company=record["company_name"],
                    known_contact_name=record["known_name"],
                    known_contact_email=record["known_email"],
                    relationship_type=record["path_type"],
                    warmth_score=warmth,
                    suggested_opener=opener
                ))

            # Query 2: Find paths through CURRENT company (WORKS_AT)
            if len(warm_paths) < max_paths:
                result = session.run("""
                    MATCH (target:Person {linkedin_url: $target_url})
                    MATCH (target)-[:WORKS_AT]->(company:Company)<-[:WORKED_AT]-(known:Person {is_our_contact: true})
                    WHERE target <> known
                    AND NOT EXISTS {
                        MATCH (target)-[:WORKED_AT]->(c)<-[:WORKED_AT|WORKS_AT]-(known)
                    }
                    RETURN
                        target.name AS target_name,
                        target.linkedin_url AS target_linkedin,
                        company.name AS company_name,
                        known.name AS known_name,
                        known.email AS known_email,
                        known.relationship_type AS rel_type,
                        'current_company_past_employee' AS path_type
                    ORDER BY known.relationship_type DESC
                    LIMIT $remaining
                """, target_url=target_linkedin_url, remaining=max_paths - len(warm_paths))

                for record in result:
                    warmth = self._calculate_warmth(record["path_type"], record["rel_type"])
                    opener = self._generate_opener(
                        record["known_name"],
                        record["company_name"],
                        record["path_type"]
                    )

                    warm_paths.append(WarmPath(
                        target_name=record["target_name"] or "Lead",
                        target_linkedin_url=record["target_linkedin"],
                        via_company=record["company_name"],
                        known_contact_name=record["known_name"],
                        known_contact_email=record["known_email"],
                        relationship_type=record["path_type"],
                        warmth_score=warmth,
                        suggested_opener=opener
                    ))

        # Sort by warmth score (highest first)
        warm_paths.sort(key=lambda p: p.warmth_score, reverse=True)

        logger.info(f"Found {len(warm_paths)} warm paths for {target_linkedin_url}")
        return warm_paths

    def _calculate_warmth(self, path_type: str, relationship_type: Optional[str]) -> int:
        """Calculate warmth score (0-100) based on path type and relationship."""
        base_scores = {
            "deal_referral": 95,
            "past_colleague": 80,
            "current_company_past_employee": 70,
            "same_company_different_time": 60,
            "industry_connection": 40,
        }

        score = base_scores.get(path_type, 50)

        # Boost for stronger relationships
        if relationship_type == "deal_closed":
            score = min(100, score + 15)
        elif relationship_type == "active_customer":
            score = min(100, score + 10)

        return score

    def _generate_opener(
        self,
        known_name: str,
        company_name: str,
        path_type: str
    ) -> str:
        """Generate a warm opener based on the relationship path."""
        first_name = known_name.split()[0] if known_name else "A colleague"

        openers = {
            "past_colleague": f"{first_name} from {company_name} mentioned I should give you a call about your energy costs...",
            "current_company_past_employee": f"I work with {first_name} who used to be at {company_name} - they mentioned you're the person to talk to about solar...",
            "deal_referral": f"{first_name} at {company_name} said you'd be the perfect person to connect with about what we did for them...",
            "same_company_different_time": f"I noticed you worked at {company_name} - we've helped a lot of folks from there with their energy needs...",
        }

        return openers.get(path_type, f"I'm reaching out based on your experience at {company_name}...")

    # ========================================================================
    # BULK OPERATIONS
    # ========================================================================

    def import_from_hunter_contacts(self, contacts: List[Dict[str, Any]]) -> int:
        """
        Bulk import contacts from Hunter.io domain search results.

        Args:
            contacts: List of Hunter.io contact dicts with:
                - email, first_name, last_name, position, linkedin

        Returns:
            Number of contacts imported
        """
        count = 0
        for contact in contacts:
            linkedin_url = contact.get("linkedin")
            if not linkedin_url:
                continue

            name = f"{contact.get('first_name', '')} {contact.get('last_name', '')}".strip()
            if not name:
                continue

            # Extract company from email domain
            email = contact.get("email", "")
            company_domain = email.split("@")[1] if "@" in email else None
            company_name = company_domain.split(".")[0].title() if company_domain else None

            self.add_person_with_experience(
                linkedin_url=linkedin_url,
                name=name,
                email=email,
                is_our_contact=False,  # These are leads, not our contacts
                current_company=company_name,
                current_title=contact.get("position"),
                experience=[{
                    "company": company_name,
                    "domain": company_domain,
                    "title": contact.get("position"),
                    "current": True
                }] if company_name else []
            )
            count += 1

        logger.info(f"Imported {count} contacts to graph from Hunter.io data")
        return count

    def import_linkedin_profile(self, profile: Dict[str, Any], is_our_contact: bool = False) -> bool:
        """
        Import a LinkedIn profile (from Browserbase scrape) with full experience.

        Args:
            profile: Browserbase profile scrape result with 'experience' array
            is_our_contact: Mark as someone we know

        Returns:
            True if successful
        """
        linkedin_url = profile.get("profile_url") or profile.get("linkedin_url")
        if not linkedin_url:
            return False

        name = profile.get("name", "Unknown")

        # Convert experience format from Browserbase to our format
        experience = []
        for exp in profile.get("experience", []):
            experience.append({
                "company": exp.get("company", ""),
                "title": exp.get("title", ""),
                "current": "present" in exp.get("duration", "").lower() or exp.get("current", False),
                "domain": exp.get("company_domain", f"{exp.get('company', '').lower().replace(' ', '')}.com")
            })

        return self.add_person_with_experience(
            linkedin_url=linkedin_url,
            name=name,
            email=profile.get("email"),
            is_our_contact=is_our_contact,
            experience=experience,
            current_company=profile.get("current_company"),
            current_title=profile.get("current_title")
        )

    # ========================================================================
    # STATISTICS & REPORTING
    # ========================================================================

    def get_stats(self) -> Dict[str, Any]:
        """Get graph statistics for monitoring."""
        if not self._driver:
            return {"error": "Not connected"}

        with self._driver.session() as session:
            result = session.run("""
                MATCH (p:Person)
                WITH count(p) as total_people,
                     sum(CASE WHEN p.is_our_contact THEN 1 ELSE 0 END) as our_contacts
                MATCH (c:Company)
                WITH total_people, our_contacts, count(c) as total_companies
                MATCH ()-[w:WORKED_AT]->()
                WITH total_people, our_contacts, total_companies, count(w) as work_history_edges
                MATCH ()-[c:WORKS_AT]->()
                RETURN total_people, our_contacts, total_companies, work_history_edges, count(c) as current_job_edges
            """)

            record = result.single()
            if record:
                return {
                    "total_people": record["total_people"],
                    "our_contacts": record["our_contacts"],
                    "total_companies": record["total_companies"],
                    "work_history_edges": record["work_history_edges"],
                    "current_job_edges": record["current_job_edges"],
                    "warm_path_potential": record["work_history_edges"] * record["our_contacts"]
                }

            return {"total_people": 0, "our_contacts": 0, "total_companies": 0}


# Singleton instance
_graph_service: Optional[RelationshipGraphService] = None


def get_relationship_graph() -> RelationshipGraphService:
    """Get or create the relationship graph service singleton."""
    global _graph_service
    if _graph_service is None:
        _graph_service = RelationshipGraphService()
    return _graph_service
