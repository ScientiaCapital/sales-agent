#!/usr/bin/env python3
"""
Comprehensive ATL Contact Discovery Workflow

Multi-source approach:
1. Company website scraping (About Us, Team, Company pages)
2. LinkedIn company page fallback
3. Extract executive contacts (CEO, COO, CFO, CTO, VP Finance, VP Operations)
4. Capture individual LinkedIn profile URLs
5. Store in lead records for enrichment

Usage:
    python3 scripts/discover_atl_contacts.py [--limit N] [--company-name "Company Name"]
"""
import asyncio
import sys
import os
import re
import argparse
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime
from urllib.parse import urljoin, urlparse
import requests
from bs4 import BeautifulSoup

# Add backend to path
backend_path = Path(__file__).parent.parent / 'backend'
sys.path.insert(0, str(backend_path))

from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from app.models.database import SessionLocal
from app.models.lead import Lead
from app.services.linkedin_scraper import LinkedInScraper
from app.core.logging import setup_logging

logger = setup_logging(__name__)


class ATLContactDiscovery:
    """Comprehensive ATL contact discovery from multiple sources"""
    
    # Target executive titles (matches user requirements)
    ATL_TITLES = [
        "CEO", "Chief Executive Officer",
        "COO", "Chief Operating Officer",
        "CFO", "Chief Financial Officer",
        "CTO", "Chief Technology Officer",
        "VP Finance", "Vice President Finance", "VP of Finance",
        "VP Operations", "Vice President Operations", "VP of Operations"
    ]
    
    def __init__(self, db: Session):
        self.db = db
        self.linkedin_scraper = LinkedInScraper()
        self.stats = {
            'processed': 0,
            'website_found': 0,
            'linkedin_found': 0,
            'contacts_discovered': 0,
            'failed': 0,
            'start_time': datetime.now()
        }
    
    def extract_domain(self, website: Optional[str], notes: Optional[str]) -> Optional[str]:
        """Extract domain from website URL or notes"""
        if website:
            domain = website.replace('https://', '').replace('http://', '').replace('www.', '')
            domain = domain.split('/')[0].split('?')[0].strip()
            if domain:
                return domain
        
        if notes:
            for line in notes.split('|'):
                if 'Domain:' in line:
                    domain = line.split('Domain:')[1].strip()
                    if domain:
                        return domain.split()[0]
        
        return None
    
    def find_team_pages(self, base_url: str, domain: str) -> List[str]:
        """Find About Us, Company, or Team pages on website (exact match to user requirements)"""
        team_page_patterns = [
            '/about', '/about-us', '/aboutus',
            '/company', '/company/', '/our-company',
            '/team', '/team/', '/our-team', '/leadership-team'
        ]
        
        team_pages = []
        base_domain = f"https://{domain}"
        
        # Try common team page paths
        for pattern in team_page_patterns:
            url = urljoin(base_domain, pattern)
            try:
                response = requests.get(url, timeout=5, allow_redirects=True)
                if response.status_code == 200:
                    # Check if page contains team/executive keywords
                    content = response.text.lower()
                    if any(keyword in content for keyword in ['team', 'executive', 'leadership', 'founder', 'ceo', 'coo', 'cfo']):
                        team_pages.append(url)
                        logger.info(f"Found team page: {url}")
            except:
                continue
        
        return team_pages
    
    def scrape_team_page(self, url: str) -> List[Dict[str, Any]]:
        """Scrape team page for executive contacts"""
        try:
            response = requests.get(url, timeout=10, headers={
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
            })
            
            if response.status_code != 200:
                return []
            
            soup = BeautifulSoup(response.text, 'html.parser')
            contacts = []
            
            # Look for common team member structures
            # Pattern 1: Cards with name, title, LinkedIn
            team_cards = soup.find_all(['div', 'article', 'section'], 
                                      class_=re.compile(r'team|member|executive|leadership', re.I))
            
            for card in team_cards:
                # Extract name
                name_elem = card.find(['h1', 'h2', 'h3', 'h4', 'h5', 'p'], 
                                     class_=re.compile(r'name|title', re.I))
                if not name_elem:
                    name_elem = card.find('strong')
                
                name = name_elem.get_text(strip=True) if name_elem else None
                
                # Extract title
                title_elem = card.find(['p', 'span', 'div'], 
                                      class_=re.compile(r'title|position|role', re.I))
                if not title_elem:
                    # Try to find text that matches ATL titles
                    text = card.get_text()
                    for title in self.ATL_TITLES:
                        if title.lower() in text.lower():
                            title_elem = card
                            break
                
                title = title_elem.get_text(strip=True) if title_elem else None
                
                # Extract LinkedIn URL
                linkedin_elem = card.find('a', href=re.compile(r'linkedin\.com/in/'))
                linkedin_url = linkedin_elem.get('href') if linkedin_elem else None
                
                # Check if title matches ATL criteria (exact match)
                if name and title:
                    title_lower = title.lower()
                    is_atl = any(at_title.lower() in title_lower for at_title in self.ATL_TITLES)
                    
                    if is_atl:
                        contacts.append({
                            'name': name,
                            'title': title,
                            'linkedin_url': linkedin_url,
                            'source': 'website',
                            'source_url': url
                        })
            
            # Pattern 2: Text-based extraction (fallback)
            if not contacts:
                page_text = soup.get_text()
                # Look for patterns like "John Doe, CEO" or "CEO: John Doe"
                for title in self.ATL_TITLES:
                    pattern = rf'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s*[,:]\s*{re.escape(title)}'
                    matches = re.finditer(pattern, page_text, re.IGNORECASE)
                    for match in matches:
                        name = match.group(1).strip()
                        contacts.append({
                            'name': name,
                            'title': title,
                            'linkedin_url': None,
                            'source': 'website',
                            'source_url': url
                        })
            
            logger.info(f"Found {len(contacts)} contacts on {url}")
            return contacts
            
        except Exception as e:
            logger.error(f"Error scraping team page {url}: {e}")
            return []
    
    def find_linkedin_company_url(self, company_name: str, domain: Optional[str] = None) -> Optional[str]:
        """Find LinkedIn company page URL"""
        # Try to construct from company name
        # Format: https://linkedin.com/company/company-name
        company_slug = company_name.lower()
        company_slug = re.sub(r'[^a-z0-9]+', '-', company_slug)
        company_slug = re.sub(r'^-+|-+$', '', company_slug)  # Remove leading/trailing dashes
        
        linkedin_url = f"https://linkedin.com/company/{company_slug}"
        
        # In production, you might want to verify this URL exists
        # For now, return the constructed URL
        return linkedin_url
    
    async def discover_linkedin_contacts(self, linkedin_url: str) -> List[Dict[str, Any]]:
        """Discover ATL contacts from LinkedIn company page"""
        try:
            result = self.linkedin_scraper.discover_atl_contacts(
                company_linkedin_url=linkedin_url,
                include_titles=self.ATL_TITLES
            )
            
            contacts = []
            for contact in result.get('contacts', []):
                contacts.append({
                    'name': contact.get('name'),
                    'title': contact.get('title'),
                    'linkedin_url': contact.get('profile_url'),
                    'decision_maker_score': contact.get('decision_maker_score'),
                    'contact_priority': contact.get('contact_priority'),
                    'source': 'linkedin',
                    'source_url': linkedin_url
                })
            
            return contacts
            
        except Exception as e:
            logger.error(f"Error discovering LinkedIn contacts: {e}")
            return []
    
    async def discover_atl_for_lead(self, lead: Lead) -> Dict[str, Any]:
        """Discover ATL contacts for a single lead using multi-source approach"""
        contacts_found = []
        sources_used = []
        
        # Step 1: Try company website first
        domain = self.extract_domain(lead.company_website, lead.notes)
        
        if domain:
            self.stats['website_found'] += 1
            
            # Find team pages
            base_url = lead.company_website or f"https://{domain}"
            team_pages = self.find_team_pages(base_url, domain)
            
            # Scrape each team page
            for team_page in team_pages:
                page_contacts = self.scrape_team_page(team_page)
                contacts_found.extend(page_contacts)
                if page_contacts:
                    sources_used.append(f"website:{team_page}")
        
        # Step 2: LinkedIn company page (whether website found contacts or not)
        # User requirement: "if exists or doesn't exist on domain, then look up linkedin company page"
        linkedin_url = None
        
        # Check if LinkedIn URL already in additional_data
        if lead.additional_data and lead.additional_data.get('linkedin_url'):
            linkedin_url = lead.additional_data['linkedin_url']
        else:
            # Try to find LinkedIn URL
            linkedin_url = self.find_linkedin_company_url(lead.company_name, domain)
        
        if linkedin_url:
            self.stats['linkedin_found'] += 1
            linkedin_contacts = await self.discover_linkedin_contacts(linkedin_url)
            
            # Extract personal LinkedIn profile URLs for each contact
            # User requirement: "capture their personal linkedin profile page"
            for contact in linkedin_contacts:
                if contact.get('linkedin_url'):
                    # Store individual profile URLs
                    if 'linkedin_profile_urls' not in lead.additional_data:
                        lead.additional_data['linkedin_profile_urls'] = []
                    if contact['linkedin_url'] not in lead.additional_data['linkedin_profile_urls']:
                        lead.additional_data['linkedin_profile_urls'].append(contact['linkedin_url'])
            
            contacts_found.extend(linkedin_contacts)
            if linkedin_contacts:
                sources_used.append(f"linkedin:{linkedin_url}")
            
            # Also capture company page info (employee count, etc.)
            # User requirement: "company linkedin page gives an idea of employee count"
            try:
                company_info = self.linkedin_scraper.scrape_company_page(linkedin_url)
                if company_info and not company_info.get('error'):
                    if not lead.additional_data:
                        lead.additional_data = {}
                    lead.additional_data['linkedin_company_info'] = {
                        'employee_count': company_info.get('employee_count'),
                        'industry': company_info.get('industry'),
                        'description': company_info.get('description'),
                        'scraped_at': datetime.now().isoformat()
                    }
            except:
                pass  # Continue even if company page scraping fails
        
        # Deduplicate contacts by name
        unique_contacts = {}
        for contact in contacts_found:
            name = contact.get('name', '').lower()
            if name and name not in unique_contacts:
                unique_contacts[name] = contact
        
        contacts_found = list(unique_contacts.values())
        
        # Sort by decision_maker_score (if available) or title priority
        def sort_key(contact):
            score = contact.get('decision_maker_score', 0)
            title = contact.get('title', '').lower()
            # Boost C-level contacts
            if any(c in title for c in ['ceo', 'coo', 'cfo', 'cto', 'cmo', 'chief']):
                score = max(score, 100)
            return -score  # Negative for descending sort
        
        contacts_found.sort(key=sort_key, reverse=True)
        
        # Store results in lead
        if contacts_found:
            if not lead.additional_data:
                lead.additional_data = {}
            
            lead.additional_data['atl_contacts'] = contacts_found
            lead.additional_data['atl_discovered_at'] = datetime.now().isoformat()
            lead.additional_data['atl_sources'] = sources_used
            
            # Update lead with top contact info
            top_contact = contacts_found[0]
            if top_contact.get('name'):
                lead.contact_name = top_contact['name']
            if top_contact.get('title'):
                lead.contact_title = top_contact['title']
            if top_contact.get('linkedin_url'):
                if 'linkedin_urls' not in lead.additional_data:
                    lead.additional_data['linkedin_urls'] = []
                lead.additional_data['linkedin_urls'].append(top_contact['linkedin_url'])
            
            self.db.commit()
            self.stats['contacts_discovered'] += len(contacts_found)
            
            return {
                'status': 'success',
                'lead_id': lead.id,
                'company': lead.company_name,
                'contacts_found': len(contacts_found),
                'top_contact': contacts_found[0].get('name'),
                'sources': sources_used
            }
        else:
            return {
                'status': 'no_contacts',
                'lead_id': lead.id,
                'company': lead.company_name,
                'sources_tried': sources_used
            }
    
    async def discover_batch(
        self,
        limit: int = 0,
        company_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """Discover ATL contacts for multiple leads"""
        
        # Get leads to process
        query = self.db.query(Lead)
        
        if company_name:
            query = query.filter(Lead.company_name.ilike(f"%{company_name}%"))
        
        if limit > 0:
            query = query.limit(limit)
        
        leads = query.all()
        
        if not leads:
            print("✅ No leads found")
            return {'status': 'no_leads'}
        
        print(f"\n🔍 Processing {len(leads)} companies...\n")
        
        results = []
        for i, lead in enumerate(leads, 1):
            print(f"[{i}/{len(leads)}] Processing: {lead.company_name}")
            result = await self.discover_atl_for_lead(lead)
            results.append(result)
            
            if result['status'] == 'success':
                print(f"   ✅ Found {result['contacts_found']} ATL contacts")
                print(f"   Top contact: {result['top_contact']}")
            elif result['status'] == 'no_contacts':
                print(f"   ⚠️  No contacts found")
                if result.get('sources_tried'):
                    print(f"   Tried: {', '.join(result['sources_tried'])}")
            
            self.stats['processed'] += 1
            
            # Small delay to avoid rate limiting
            await asyncio.sleep(1)
        
        # Print summary
        duration = (datetime.now() - self.stats['start_time']).total_seconds()
        
        print(f"\n{'='*60}")
        print(f"📊 ATL Discovery Summary")
        print(f"{'='*60}")
        print(f"Companies processed:  {self.stats['processed']}")
        print(f"Website sources:      {self.stats['website_found']}")
        print(f"LinkedIn sources:     {self.stats['linkedin_found']}")
        print(f"Contacts discovered:  {self.stats['contacts_discovered']}")
        print(f"Failed:               {self.stats['failed']}")
        print(f"⏱️  Duration:           {duration:.2f}s")
        print(f"{'='*60}\n")
        
        return {
            'status': 'complete',
            'stats': self.stats,
            'results': results
        }


async def main():
    parser = argparse.ArgumentParser(description='Discover ATL contacts from company websites and LinkedIn')
    parser.add_argument(
        '--limit',
        type=int,
        default=10,
        help='Limit number of companies to process (0 = all)'
    )
    parser.add_argument(
        '--company-name',
        type=str,
        help='Process specific company by name'
    )
    
    args = parser.parse_args()
    
    # Check server
    try:
        response = requests.get("http://localhost:8001/api/health", timeout=2)
        if response.status_code != 200:
            print("⚠️  Server not healthy, but continuing...")
    except:
        print("⚠️  Server not running, but continuing with discovery...")
    
    # Initialize database
    db = SessionLocal()
    
    try:
        discovery = ATLContactDiscovery(db)
        result = await discovery.discover_batch(
            limit=args.limit,
            company_name=args.company_name
        )
        
        if result['status'] == 'complete':
            print("✅ ATL discovery completed!")
        elif result['status'] == 'no_leads':
            print("ℹ️  No leads found")
        
    except Exception as e:
        logger.error(f"ATL discovery failed: {e}", exc_info=True)
        print(f"❌ Error: {e}")
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    asyncio.run(main())

