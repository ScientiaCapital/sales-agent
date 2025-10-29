"""
Document Analysis Service

Orchestrates comprehensive document analysis using:
- Gist memory pattern for efficient processing
- Cerebras AI for summarization
- Key item extraction (entities, dates, phrases)
- Document search capabilities

Integrates with existing DocumentProcessor for file parsing.
"""

import json
import re
from typing import Dict, List, Optional, Any
from datetime import datetime

from app.services.gist_memory import GistMemory
from app.services.document_processor import DocumentProcessor
from app.services.cerebras import CerebrasService
from app.core.logging import logger


# Prompts for extraction
PROMPT_KEY_EXTRACTION = """Analyze the following text and extract key information in JSON format.

Text:
{text}

Extract and return ONLY a valid JSON object with this structure:
{{
    "entities": {{
        "people": ["list of person names"],
        "organizations": ["list of company/organization names"],
        "locations": ["list of place names"]
    }},
    "dates": ["list of dates mentioned"],
    "key_phrases": ["list of important terms/concepts (max 10)"],
    "actions": ["list of main actions or decisions (max 5)"],
    "topics": ["list of main topics discussed (max 5)"]
}}

JSON:"""

PROMPT_DOCUMENT_SUMMARY = """Provide a comprehensive summary of this document.

{content}

Create a summary that includes:
1. Main purpose and topic
2. Key points (3-5 bullet points)
3. Important findings or conclusions
4. Recommended actions (if any)

Summary:"""


class DocumentAnalyzer:
    """
    Service for comprehensive document analysis using gist memory and AI.

    Features:
    - Intelligent document pagination and processing
    - AI-powered summarization with gist memory
    - Structured key item extraction
    - Document search and highlighting
    - Support for PDF, DOCX, TXT formats
    """

    def __init__(self):
        """Initialize the document analyzer with required services."""
        self.gist_memory = GistMemory()
        self.doc_processor = DocumentProcessor()
        # Initialize Cerebras service (optional - may fail if SDK not installed)
        try:
            self.cerebras = CerebrasService()
        except (ImportError, MissingAPIKeyError):
            self.cerebras = None
            logger.warning("CerebrasService unavailable. Document analysis features will be limited.")

    def analyze_document(
        self,
        filename: str,
        file_content: bytes,
        extract_keys: bool = True,
        create_summary: bool = True
    ) -> Dict[str, Any]:
        """
        Perform complete document analysis.

        Args:
            filename: Original filename with extension
            file_content: Raw file bytes
            extract_keys: Whether to extract key items
            create_summary: Whether to generate summary

        Returns:
            Comprehensive analysis results
        """
        start_time = datetime.now()
        logger.info(f"Starting analysis of document: {filename}")

        try:
            # Step 1: Extract text from document
            text = self.doc_processor.extract_text(filename, file_content)
            logger.info(f"Extracted {len(text)} characters from {filename}")

            # Step 2: Process with gist memory
            gist_result = self.gist_memory.process_document(text)

            if not gist_result['success']:
                return {
                    'success': False,
                    'error': gist_result.get('error', 'Processing failed'),
                    'filename': filename
                }

            # Initialize results
            results = {
                'success': True,
                'filename': filename,
                'text_length': len(text),
                'word_count': len(text.split()),
                'pages': gist_result['pages'],
                'compression_ratio': gist_result['compression_ratio'],
                'processing_metadata': {
                    'avg_page_words': gist_result['avg_page_words'],
                    'total_gist_words': gist_result['total_gist_words']
                }
            }

            # Step 3: Generate summary (if requested)
            if create_summary:
                logger.info("Generating document summary")
                summary_result = self.generate_summary()
                results['summary'] = summary_result['summary']
                results['summary_length'] = summary_result['summary_length']

            # Step 4: Extract key items (if requested)
            if extract_keys:
                logger.info("Extracting key items from document")
                key_items = self.extract_key_items(text[:5000])  # Use first 5000 chars
                results['key_items'] = key_items

            # Step 5: Store page gists for later queries
            results['page_gists'] = self.gist_memory.gists
            results['page_metadata'] = self.gist_memory.page_metadata

            # Calculate total processing time
            end_time = datetime.now()
            total_processing_time = int((end_time - start_time).total_seconds() * 1000)
            results['total_processing_time_ms'] = total_processing_time

            logger.info(f"Document analysis completed in {total_processing_time}ms")
            return results

        except Exception as e:
            logger.error(f"Document analysis failed: {str(e)}", exc_info=True)
            return {
                'success': False,
                'error': str(e),
                'filename': filename
            }

    def generate_summary(self, max_length: int = 500) -> Dict[str, Any]:
        """
        Generate a comprehensive document summary using gist memory.

        Args:
            max_length: Maximum summary length in words

        Returns:
            Summary results
        """
        if not self.gist_memory.gists:
            return {
                'summary': '',
                'summary_length': 0,
                'error': 'No gists available'
            }

        try:
            # Option 1: Use pre-computed gist summary
            gist_summary = self.gist_memory.get_summary()

            # Option 2: Generate enhanced summary using Cerebras
            if len(gist_summary.split()) < max_length:
                # Use gist summary directly
                summary = gist_summary
            else:
                # Ask Cerebras to create a more concise summary
                prompt = PROMPT_DOCUMENT_SUMMARY.format(content=gist_summary[:2000])

                from openai import OpenAI
                import os

                client = OpenAI(
                    api_key=os.getenv("CEREBRAS_API_KEY"),
                    base_url="https://api.cerebras.ai/v1"
                )

                response = client.chat.completions.create(
                    model="llama3.1-8b",
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=400,
                    temperature=0.4
                )

                summary = response.choices[0].message.content.strip()

            return {
                'summary': summary,
                'summary_length': len(summary.split()),
                'pages_summarized': len(self.gist_memory.pages)
            }

        except Exception as e:
            logger.error(f"Summary generation failed: {str(e)}")
            return {
                'summary': self.gist_memory.get_summary(),
                'summary_length': 0,
                'error': str(e)
            }

    def extract_key_items(self, text: str) -> Dict[str, Any]:
        """
        Extract structured key items from text using Cerebras.

        Args:
            text: Text to analyze (should be limited to avoid token limits)

        Returns:
            Extracted key items in structured format
        """
        prompt = PROMPT_KEY_EXTRACTION.format(text=text[:3000])  # Limit input

        try:
            from openai import OpenAI
            import os

            client = OpenAI(
                api_key=os.getenv("CEREBRAS_API_KEY"),
                base_url="https://api.cerebras.ai/v1"
            )

            response = client.chat.completions.create(
                model="llama3.1-8b",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=500,
                temperature=0.3
            )

            # Parse JSON response
            content = response.choices[0].message.content.strip()

            # Try to extract JSON from response
            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            if json_match:
                json_str = json_match.group(0)
                key_items = json.loads(json_str)
            else:
                # Try direct parse
                key_items = json.loads(content)

            # Validate structure
            if not isinstance(key_items, dict):
                raise ValueError("Response is not a dictionary")

            # Ensure all expected keys exist
            default_structure = {
                "entities": {"people": [], "organizations": [], "locations": []},
                "dates": [],
                "key_phrases": [],
                "actions": [],
                "topics": []
            }

            # Merge with defaults
            for key in default_structure:
                if key not in key_items:
                    key_items[key] = default_structure[key]

            logger.info(f"Extracted key items: {len(key_items.get('entities', {}).get('people', []))} people, "
                       f"{len(key_items.get('dates', []))} dates")

            return key_items

        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse key extraction JSON: {e}")
            return {
                "entities": {"people": [], "organizations": [], "locations": []},
                "dates": [],
                "key_phrases": [],
                "actions": [],
                "topics": [],
                "extraction_error": str(e)
            }
        except Exception as e:
            logger.error(f"Key extraction failed: {str(e)}")
            return {
                "entities": {"people": [], "organizations": [], "locations": []},
                "dates": [],
                "key_phrases": [],
                "actions": [],
                "topics": [],
                "extraction_error": str(e)
            }

    def search_document(
        self,
        query: str,
        max_results: int = 5,
        highlight: bool = True
    ) -> List[Dict]:
        """
        Search document for query terms with optional highlighting.

        Args:
            query: Search query
            max_results: Maximum number of results
            highlight: Whether to highlight query terms

        Returns:
            List of matching page results with snippets
        """
        if not self.gist_memory.pages:
            logger.warning("No document loaded for search")
            return []

        # Use gist memory's search functionality
        results = self.gist_memory.search_pages(query, max_results)

        # Add highlighting if requested
        if highlight:
            for result in results:
                result['highlighted_snippet'] = self._highlight_text(
                    result['snippet'],
                    query
                )

        return results

    def _highlight_text(self, text: str, query: str) -> str:
        """
        Highlight query terms in text with markers.

        Args:
            text: Text to highlight
            query: Query terms to highlight

        Returns:
            Text with highlight markers
        """
        # Use case-insensitive highlighting with markers
        pattern = re.compile(f'({re.escape(query)})', re.IGNORECASE)
        highlighted = pattern.sub(r'**\1**', text)
        return highlighted

    def answer_question(
        self,
        question: str,
        relevant_pages: Optional[List[int]] = None
    ) -> Dict:
        """
        Answer a question about the document using gist memory.

        Args:
            question: Question to answer
            relevant_pages: Specific pages to use (auto-lookup if None)

        Returns:
            Answer with metadata
        """
        if not self.gist_memory.pages:
            return {
                'answer': 'No document loaded',
                'relevant_pages': [],
                'error': 'No document available'
            }

        return self.gist_memory.answer_question(question, relevant_pages)

    def get_page_content(self, page_num: int) -> Optional[str]:
        """
        Get full text content of a specific page.

        Args:
            page_num: Page number (1-indexed)

        Returns:
            Page text content or None
        """
        if 1 <= page_num <= len(self.gist_memory.pages):
            page = self.gist_memory.pages[page_num - 1]
            return '\n\n'.join(page)
        return None

    def get_document_stats(self) -> Dict[str, Any]:
        """
        Get comprehensive statistics about the loaded document.

        Returns:
            Document statistics
        """
        if not self.gist_memory.pages:
            return {'error': 'No document loaded'}

        total_words = sum(
            len(' '.join(page).split())
            for page in self.gist_memory.pages
        )

        total_gist_words = sum(
            len(gist.split())
            for gist in self.gist_memory.gists
        )

        return {
            'total_pages': len(self.gist_memory.pages),
            'total_words': total_words,
            'total_gist_words': total_gist_words,
            'compression_ratio': round(total_gist_words / total_words, 3) if total_words > 0 else 0,
            'avg_page_words': round(total_words / len(self.gist_memory.pages)) if self.gist_memory.pages else 0,
            'page_metadata': self.gist_memory.page_metadata
        }

    def export_analysis(self) -> Dict[str, Any]:
        """
        Export complete analysis results for storage.

        Returns:
            Exportable analysis data
        """
        return {
            'pages': len(self.gist_memory.pages),
            'gists': self.gist_memory.gists,
            'page_metadata': self.gist_memory.page_metadata,
            'statistics': self.get_document_stats(),
            'timestamp': datetime.now().isoformat()
        }

    def clear(self):
        """Clear all stored document data."""
        self.gist_memory.clear()
        logger.info("Document analyzer cleared")
