"""
Local Deduplication Cache - Final Safety Net

This is a BULLETPROOF local cache that tracks EVERY lead ever processed,
even if Close CRM API fails, even if leads are deleted from Close later.

Multiple matching strategies:
1. Exact company name match
2. Normalized name match (lowercase, no punctuation, no suffixes)
3. Phone number match (any format)
4. Email domain match (same company, different contact)

This cache NEVER expires unless manually cleared. It's your insurance policy.
"""

import sqlite3
import hashlib
import re
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Any
from dataclasses import dataclass


@dataclass
class CacheMatch:
    """Result of a cache lookup."""
    is_duplicate: bool
    match_type: str  # exact_name, normalized_name, phone, email_domain, none
    matched_record: Optional[Dict[str, Any]] = None
    confidence: float = 0.0


class DeduplicationCache:
    """
    Local SQLite cache for tracking processed leads.

    This is your FINAL SAFETY NET - independent of Close CRM API.
    """

    def __init__(self, db_path: str = "data/processed_leads_cache.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        """Create the database schema if it doesn't exist."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Main cache table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS processed_leads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                company_name TEXT NOT NULL,
                company_name_normalized TEXT NOT NULL,
                company_name_hash TEXT NOT NULL,
                phone TEXT,
                phone_normalized TEXT,
                email TEXT,
                email_domain TEXT,
                source_file TEXT,
                import_date TEXT NOT NULL,
                close_lead_id TEXT,
                status TEXT DEFAULT 'processed',
                notes TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Indexes for fast lookups
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_company_hash
            ON processed_leads(company_name_hash)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_phone_normalized
            ON processed_leads(phone_normalized)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_email_domain
            ON processed_leads(email_domain)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_import_date
            ON processed_leads(import_date)
        """)

        # Audit log table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS import_audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                import_date TEXT NOT NULL,
                source_file TEXT NOT NULL,
                total_records INTEGER,
                new_records INTEGER,
                duplicate_records INTEGER,
                notes TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        conn.commit()
        conn.close()

    def _normalize_company_name(self, name: str) -> str:
        """
        Normalize company name for fuzzy matching.

        Steps:
        1. Lowercase
        2. Remove suffixes (LLC, Inc, Corp, Co, Ltd, etc.)
        3. Remove punctuation
        4. Remove extra whitespace
        """
        if not name:
            return ""

        # Lowercase
        name = name.lower()

        # Remove common suffixes
        suffixes = [
            r'\s+llc\s*$', r'\s+inc\s*$', r'\s+corp\s*$', r'\s+corporation\s*$',
            r'\s+co\s*$', r'\s+ltd\s*$', r'\s+limited\s*$', r'\s+l\.?l\.?c\.?\s*$',
            r'\s+incorporated\s*$', r'\s+company\s*$'
        ]
        for suffix in suffixes:
            name = re.sub(suffix, '', name, flags=re.IGNORECASE)

        # Remove punctuation
        name = re.sub(r'[^\w\s]', '', name)

        # Remove extra whitespace
        name = ' '.join(name.split())

        return name.strip()

    def _hash_name(self, name: str) -> str:
        """Create a hash of the normalized name for fast lookups."""
        normalized = self._normalize_company_name(name)
        return hashlib.md5(normalized.encode()).hexdigest()

    def _normalize_phone(self, phone: str) -> str:
        """Normalize phone to digits only."""
        if not phone:
            return ""
        # Convert to string in case it's read as int from CSV
        return re.sub(r'\D', '', str(phone))

    def _extract_domain(self, email: str) -> str:
        """Extract domain from email."""
        # Handle NaN/None/non-string values from pandas
        if not email or (isinstance(email, float) and str(email) == 'nan'):
            return ""
        email_str = str(email)
        if '@' not in email_str:
            return ""
        return email_str.split('@')[1].lower()

    def check_duplicate(
        self,
        company_name: str,
        phone: Optional[str] = None,
        email: Optional[str] = None
    ) -> CacheMatch:
        """
        Check if lead already exists in cache.

        Returns CacheMatch with:
        - is_duplicate: True if found
        - match_type: How it was matched
        - matched_record: The existing record
        - confidence: 0-100%
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Strategy 1: Exact company name hash (100% confidence)
        company_hash = self._hash_name(company_name)
        cursor.execute(
            "SELECT * FROM processed_leads WHERE company_name_hash = ? LIMIT 1",
            (company_hash,)
        )
        row = cursor.fetchone()
        if row:
            conn.close()
            return CacheMatch(
                is_duplicate=True,
                match_type="normalized_name",
                matched_record=dict(row),
                confidence=100.0
            )

        # Strategy 2: Phone number match (95% confidence - high signal)
        if phone:
            phone_normalized = self._normalize_phone(phone)
            if phone_normalized:
                cursor.execute(
                    "SELECT * FROM processed_leads WHERE phone_normalized = ? LIMIT 1",
                    (phone_normalized,)
                )
                row = cursor.fetchone()
                if row:
                    conn.close()
                    return CacheMatch(
                        is_duplicate=True,
                        match_type="phone",
                        matched_record=dict(row),
                        confidence=95.0
                    )

        # Strategy 3: Email domain match (60% confidence - same company, different contact)
        if email:
            domain = self._extract_domain(email)
            if domain:
                cursor.execute(
                    "SELECT * FROM processed_leads WHERE email_domain = ? LIMIT 1",
                    (domain,)
                )
                row = cursor.fetchone()
                if row:
                    conn.close()
                    # Domain match is lower confidence (could be same company, new contact)
                    return CacheMatch(
                        is_duplicate=True,
                        match_type="email_domain",
                        matched_record=dict(row),
                        confidence=60.0
                    )

        conn.close()

        # No match found
        return CacheMatch(
            is_duplicate=False,
            match_type="none",
            matched_record=None,
            confidence=0.0
        )

    def add_lead(
        self,
        company_name: str,
        phone: Optional[str] = None,
        email: Optional[str] = None,
        source_file: Optional[str] = None,
        close_lead_id: Optional[str] = None,
        notes: Optional[str] = None
    ) -> int:
        """
        Add a lead to the cache.

        Returns: The ID of the inserted record.
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO processed_leads (
                company_name,
                company_name_normalized,
                company_name_hash,
                phone,
                phone_normalized,
                email,
                email_domain,
                source_file,
                import_date,
                close_lead_id,
                notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            company_name,
            self._normalize_company_name(company_name),
            self._hash_name(company_name),
            phone,
            self._normalize_phone(phone) if phone else None,
            email,
            self._extract_domain(email) if email else None,
            source_file,
            datetime.now().strftime("%Y-%m-%d"),
            close_lead_id,
            notes
        ))

        lead_id = cursor.lastrowid
        conn.commit()
        conn.close()

        return lead_id

    def log_import(
        self,
        source_file: str,
        total_records: int,
        new_records: int,
        duplicate_records: int,
        notes: Optional[str] = None
    ):
        """Log an import batch to the audit log."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO import_audit_log (
                import_date,
                source_file,
                total_records,
                new_records,
                duplicate_records,
                notes
            ) VALUES (?, ?, ?, ?, ?, ?)
        """, (
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            source_file,
            total_records,
            new_records,
            duplicate_records,
            notes
        ))

        conn.commit()
        conn.close()

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Total leads
        cursor.execute("SELECT COUNT(*) FROM processed_leads")
        total_leads = cursor.fetchone()[0]

        # Leads by date
        cursor.execute("""
            SELECT import_date, COUNT(*) as count
            FROM processed_leads
            GROUP BY import_date
            ORDER BY import_date DESC
            LIMIT 10
        """)
        recent_imports = [{"date": row[0], "count": row[1]} for row in cursor.fetchall()]

        # Total imports
        cursor.execute("SELECT COUNT(*) FROM import_audit_log")
        total_imports = cursor.fetchone()[0]

        # Recent imports
        cursor.execute("""
            SELECT import_date, source_file, total_records, new_records, duplicate_records
            FROM import_audit_log
            ORDER BY created_at DESC
            LIMIT 5
        """)
        recent_audit = [{
            "date": row[0],
            "file": row[1],
            "total": row[2],
            "new": row[3],
            "duplicates": row[4]
        } for row in cursor.fetchall()]

        conn.close()

        return {
            "total_leads_cached": total_leads,
            "total_imports": total_imports,
            "recent_imports": recent_imports,
            "recent_audit_log": recent_audit,
            "cache_file": str(self.db_path)
        }

    def search_cache(
        self,
        company_name: Optional[str] = None,
        phone: Optional[str] = None,
        email: Optional[str] = None,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Search the cache manually."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        conditions = []
        params = []

        if company_name:
            conditions.append("company_name LIKE ?")
            params.append(f"%{company_name}%")

        if phone:
            phone_normalized = self._normalize_phone(phone)
            conditions.append("phone_normalized = ?")
            params.append(phone_normalized)

        if email:
            conditions.append("email LIKE ?")
            params.append(f"%{email}%")

        where_clause = " AND ".join(conditions) if conditions else "1=1"
        query = f"SELECT * FROM processed_leads WHERE {where_clause} LIMIT ?"
        params.append(limit)

        cursor.execute(query, params)
        results = [dict(row) for row in cursor.fetchall()]

        conn.close()
        return results


if __name__ == "__main__":
    # Test the cache
    cache = DeduplicationCache()

    print("=" * 60)
    print("DEDUPLICATION CACHE TEST")
    print("=" * 60)

    # Test 1: Add a lead
    print("\n1. Adding test lead...")
    lead_id = cache.add_lead(
        company_name="Acme Roofing LLC",
        phone="404-555-1234",
        email="john@acmeroofing.com",
        source_file="test.csv"
    )
    print(f"   ✅ Added lead ID: {lead_id}")

    # Test 2: Check for duplicate (should find it)
    print("\n2. Checking for duplicate with exact match...")
    result = cache.check_duplicate("Acme Roofing LLC")
    print(f"   Is duplicate: {result.is_duplicate}")
    print(f"   Match type: {result.match_type}")
    print(f"   Confidence: {result.confidence}%")

    # Test 3: Check with name variation (should still find it!)
    print("\n3. Checking with name variation...")
    result = cache.check_duplicate("ACME ROOFING INC")  # Different suffix!
    print(f"   Is duplicate: {result.is_duplicate}")
    print(f"   Match type: {result.match_type}")
    print(f"   Confidence: {result.confidence}%")

    # Test 4: Check with phone (should find it)
    print("\n4. Checking with phone match...")
    result = cache.check_duplicate("Unknown Company", phone="(404) 555-1234")  # Different format!
    print(f"   Is duplicate: {result.is_duplicate}")
    print(f"   Match type: {result.match_type}")
    print(f"   Confidence: {result.confidence}%")

    # Test 5: Stats
    print("\n5. Cache statistics:")
    stats = cache.get_stats()
    print(f"   Total leads cached: {stats['total_leads_cached']}")
    print(f"   Cache file: {stats['cache_file']}")

    print("\n" + "=" * 60)
