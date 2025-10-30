"""
Dealer Scraper Data Importer

This module handles importing and processing data from the dealer-scraper-mvp project.
It maps the rich contractor data to the sales-agent lead format and enhances it with
AI-powered qualification and enrichment.

Key Features:
- Maps dealer scraper CSV format to sales-agent lead schema
- Preserves ICP scoring and multi-OEM analysis
- Enhances with AI qualification and enrichment
- Supports tiered prospect prioritization
"""

import pandas as pd
import asyncio
from typing import Dict, Any, List, Optional
from datetime import datetime
import logging

from app.core.logging import setup_logging
from app.services.leads import LeadService
from app.services.langgraph.agents.qualification_agent import QualificationAgent
from app.services.langgraph.agents.enrichment_agent import EnrichmentAgent

logger = setup_logging(__name__)


class DealerScraperImporter:
    """
    Imports and processes dealer scraper data for the sales-agent system.
    
    Maps contractor data from dealer-scraper-mvp to sales-agent lead format,
    preserving ICP scoring and adding AI-powered qualification.
    """
    
    def __init__(self):
        """Initialize the dealer scraper importer."""
        self.lead_service = LeadService()
        self.qualification_agent = QualificationAgent()
        self.enrichment_agent = EnrichmentAgent()
        
        # Field mapping from dealer scraper to sales-agent format
        self.field_mapping = {
            'name': 'company_name',
            'phone': 'phone',
            'website': 'website',
            'email': 'email',
            'street': 'address',
            'city': 'city',
            'state': 'state',
            'zip': 'zip_code',
            'domain': 'domain',
            'ICP_Score': 'icp_score',
            'ICP_Tier': 'icp_tier',
            'OEM_Count': 'oem_count',
            'OEMs_Certified': 'oem_certifications',
            'has_hvac': 'has_hvac',
            'has_solar': 'has_solar',
            'has_inverters': 'has_inverters',
            'has_generator': 'has_generator',
            'has_battery': 'has_battery',
            'has_plumbing': 'has_plumbing',
            'has_electrical': 'has_electrical',
            'has_roofing': 'has_roofing',
            'has_ops_maintenance': 'has_ops_maintenance',
            'is_mep_r_contractor': 'is_mep_r_contractor',
            'is_resimercial': 'is_resimercial',
            'is_commercial': 'is_commercial',
            'is_residential': 'is_residential',
            'is_self_performing': 'is_self_performing',
            'is_gc': 'is_gc',
            'is_sub': 'is_sub',
            'employee_count': 'employee_count',
            'estimated_revenue': 'estimated_revenue',
            'rating': 'rating',
            'review_count': 'review_count',
            'tier': 'oem_tier',
            'oem_source': 'oem_source',
            'scraped_from_zip': 'scraped_from_zip',
            'collection_date': 'collection_date',
            'srec_state_priority': 'srec_state_priority',
            'coperniq_score': 'coperniq_score',
            'linkedin_url': 'linkedin_url',
            'address_full': 'address_full',
            'distance_miles': 'distance_miles',
            'certifications': 'certifications',
            'adwords_keywords': 'adwords_keywords',
            'seo_keywords': 'seo_keywords',
            'meta_custom_audience': 'meta_custom_audience',
            'meta_ads_targeting': 'meta_ads_targeting'
        }
        
        # ICP tier priority mapping
        self.tier_priority = {
            'PLATINUM': 100,
            'GOLD': 80,
            'SILVER': 60,
            'BRONZE': 40
        }
    
    async def import_contractors_csv(
        self,
        file_path: str,
        batch_size: int = 50,
        qualification_enabled: bool = True,
        enrichment_enabled: bool = True
    ) -> Dict[str, Any]:
        """
        Import contractors from dealer scraper CSV file.
        
        Args:
            file_path: Path to the CSV file
            batch_size: Number of records to process per batch
            qualification_enabled: Whether to run AI qualification
            enrichment_enabled: Whether to run AI enrichment
            
        Returns:
            Import summary with statistics
        """
        try:
            logger.info(f"Starting dealer scraper import: {file_path}")
            
            # Load CSV data
            df = pd.read_csv(file_path)
            total_records = len(df)
            
            logger.info(f"Loaded {total_records} contractor records")
            
            # Process in batches
            processed = 0
            qualified = 0
            enriched = 0
            errors = 0
            
            for i in range(0, total_records, batch_size):
                batch_df = df.iloc[i:i + batch_size]
                batch_results = await self._process_batch(
                    batch_df,
                    qualification_enabled,
                    enrichment_enabled
                )
                
                processed += batch_results['processed']
                qualified += batch_results['qualified']
                enriched += batch_results['enriched']
                errors += batch_results['errors']
                
                logger.info(f"Processed batch {i//batch_size + 1}: {batch_results['processed']} records")
            
            # Generate summary
            summary = {
                'total_records': total_records,
                'processed': processed,
                'qualified': qualified,
                'enriched': enriched,
                'errors': errors,
                'success_rate': (processed - errors) / total_records * 100 if total_records > 0 else 0,
                'qualification_rate': qualified / processed * 100 if processed > 0 else 0,
                'enrichment_rate': enriched / processed * 100 if processed > 0 else 0,
                'import_timestamp': datetime.now().isoformat(),
                'source_file': file_path
            }
            
            logger.info(f"Dealer scraper import completed: {summary}")
            return summary
            
        except Exception as e:
            logger.error(f"Dealer scraper import failed: {e}")
            return {
                'error': str(e),
                'total_records': 0,
                'processed': 0,
                'qualified': 0,
                'enriched': 0,
                'errors': 1
            }
    
    async def _process_batch(
        self,
        batch_df: pd.DataFrame,
        qualification_enabled: bool,
        enrichment_enabled: bool
    ) -> Dict[str, int]:
        """Process a batch of contractor records."""
        processed = 0
        qualified = 0
        enriched = 0
        errors = 0
        
        for _, row in batch_df.iterrows():
            try:
                # Map contractor data to lead format
                lead_data = self._map_contractor_to_lead(row)
                
                # Create lead record
                lead = await self.lead_service.create_lead(lead_data)
                processed += 1
                
                # Run AI qualification if enabled
                if qualification_enabled:
                    try:
                        qualification_result = await self.qualification_agent.qualify_lead(lead_data)
                        if qualification_result.get('qualified', False):
                            qualified += 1
                            # Update lead with qualification results
                            await self.lead_service.update_lead(
                                lead.id,
                                {
                                    'qualification_score': qualification_result.get('score', 0),
                                    'qualification_reasoning': qualification_result.get('reasoning', ''),
                                    'qualified': True
                                }
                            )
                    except Exception as e:
                        logger.warning(f"Qualification failed for {lead_data.get('company_name')}: {e}")
                
                # Run AI enrichment if enabled
                if enrichment_enabled:
                    try:
                        enrichment_result = await self.enrichment_agent.enrich_lead(lead_data)
                        if enrichment_result.get('enriched', False):
                            enriched += 1
                            # Update lead with enrichment results
                            await self.lead_service.update_lead(
                                lead.id,
                                {
                                    'enrichment_data': enrichment_result.get('data', {}),
                                    'enriched': True
                                }
                            )
                    except Exception as e:
                        logger.warning(f"Enrichment failed for {lead_data.get('company_name')}: {e}")
                
            except Exception as e:
                logger.error(f"Failed to process contractor {row.get('name', 'Unknown')}: {e}")
                errors += 1
        
        return {
            'processed': processed,
            'qualified': qualified,
            'enriched': enriched,
            'errors': errors
        }
    
    def _map_contractor_to_lead(self, contractor_row: pd.Series) -> Dict[str, Any]:
        """Map contractor data from dealer scraper to sales-agent lead format."""
        lead_data = {}
        
        # Map basic fields
        for dealer_field, lead_field in self.field_mapping.items():
            if dealer_field in contractor_row and pd.notna(contractor_row[dealer_field]):
                lead_data[lead_field] = contractor_row[dealer_field]
        
        # Add derived fields
        lead_data['industry'] = self._determine_industry(contractor_row)
        lead_data['company_size'] = self._determine_company_size(contractor_row)
        lead_data['priority_score'] = self._calculate_priority_score(contractor_row)
        lead_data['lead_source'] = 'dealer_scraper'
        lead_data['import_timestamp'] = datetime.now().isoformat()
        
        # Parse OEM certifications
        if 'OEMs_Certified' in contractor_row and pd.notna(contractor_row['OEMs_Certified']):
            oem_certs = str(contractor_row['OEMs_Certified']).split(', ')
            lead_data['oem_certifications'] = oem_certs
            lead_data['oem_count'] = len(oem_certs)
        
        # Parse address components
        if 'address_full' in contractor_row and pd.notna(contractor_row['address_full']):
            lead_data['address'] = contractor_row['address_full']
        
        # Set qualification status based on ICP tier
        icp_tier = contractor_row.get('ICP_Tier', 'BRONZE')
        lead_data['qualified'] = icp_tier in ['PLATINUM', 'GOLD']
        lead_data['qualification_score'] = contractor_row.get('ICP_Score', 0)
        
        return lead_data
    
    def _determine_industry(self, contractor_row: pd.Series) -> str:
        """Determine primary industry based on contractor capabilities."""
        capabilities = []
        
        if contractor_row.get('has_hvac', False):
            capabilities.append('HVAC')
        if contractor_row.get('has_solar', False):
            capabilities.append('Solar')
        if contractor_row.get('has_generator', False):
            capabilities.append('Generator')
        if contractor_row.get('has_electrical', False):
            capabilities.append('Electrical')
        if contractor_row.get('has_plumbing', False):
            capabilities.append('Plumbing')
        
        if not capabilities:
            return 'General Contractor'
        elif len(capabilities) > 2:
            return 'Multi-Trade Contractor'
        else:
            return ', '.join(capabilities)
    
    def _determine_company_size(self, contractor_row: pd.Series) -> str:
        """Determine company size based on employee count."""
        employee_count = contractor_row.get('employee_count', 0)
        
        if employee_count == 0:
            return 'Unknown'
        elif employee_count <= 10:
            return 'Small (1-10)'
        elif employee_count <= 50:
            return 'Medium (11-50)'
        elif employee_count <= 200:
            return 'Large (51-200)'
        else:
            return 'Enterprise (200+)'
    
    def _calculate_priority_score(self, contractor_row: pd.Series) -> float:
        """Calculate priority score based on ICP tier and other factors."""
        base_score = contractor_row.get('ICP_Score', 0)
        
        # Bonus for multi-OEM contractors
        oem_count = contractor_row.get('OEM_Count', 0)
        if oem_count > 1:
            base_score += 10 * oem_count
        
        # Bonus for high-value capabilities
        if contractor_row.get('has_ops_maintenance', False):
            base_score += 5
        if contractor_row.get('is_mep_r_contractor', False):
            base_score += 5
        if contractor_row.get('is_resimercial', False):
            base_score += 5
        
        # Bonus for high ratings
        rating = contractor_row.get('rating', 0)
        if rating >= 4.5:
            base_score += 10
        elif rating >= 4.0:
            base_score += 5
        
        return min(base_score, 100)  # Cap at 100
    
    async def get_import_summary(self, file_path: str) -> Dict[str, Any]:
        """Get summary of contractor data before import."""
        try:
            df = pd.read_csv(file_path)
            
            summary = {
                'total_contractors': len(df),
                'tier_distribution': df['ICP_Tier'].value_counts().to_dict(),
                'oem_distribution': df['OEM_Count'].value_counts().to_dict(),
                'state_distribution': df['state'].value_counts().head(10).to_dict(),
                'capability_distribution': {
                    'has_hvac': df['has_hvac'].sum(),
                    'has_solar': df['has_solar'].sum(),
                    'has_generator': df['has_generator'].sum(),
                    'has_electrical': df['has_electrical'].sum(),
                    'has_plumbing': df['has_plumbing'].sum(),
                    'has_ops_maintenance': df['has_ops_maintenance'].sum()
                },
                'multi_oem_contractors': len(df[df['OEM_Count'] > 1]),
                'high_priority_contractors': len(df[df['ICP_Tier'].isin(['PLATINUM', 'GOLD'])]),
                'average_icp_score': df['ICP_Score'].mean(),
                'top_oem_certifications': df['OEMs_Certified'].value_counts().head(10).to_dict()
            }
            
            return summary
            
        except Exception as e:
            logger.error(f"Failed to generate import summary: {e}")
            return {'error': str(e)}
    
    async def validate_csv_format(self, file_path: str) -> Dict[str, Any]:
        """Validate that the CSV file has the expected dealer scraper format."""
        try:
            df = pd.read_csv(file_path)
            
            required_fields = [
                'name', 'phone', 'domain', 'website', 'ICP_Score', 'ICP_Tier',
                'OEM_Count', 'OEMs_Certified', 'street', 'city', 'state', 'zip'
            ]
            
            missing_fields = [field for field in required_fields if field not in df.columns]
            
            validation_result = {
                'valid': len(missing_fields) == 0,
                'missing_fields': missing_fields,
                'total_fields': len(df.columns),
                'total_records': len(df),
                'sample_record': df.iloc[0].to_dict() if len(df) > 0 else {}
            }
            
            return validation_result
            
        except Exception as e:
            logger.error(f"CSV validation failed: {e}")
            return {
                'valid': False,
                'error': str(e),
                'missing_fields': [],
                'total_fields': 0,
                'total_records': 0
            }
