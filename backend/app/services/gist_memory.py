"""
Gist Memory Pattern Implementation

Implements the gist memory pattern for efficient document processing using Cerebras.
Based on Google DeepMind's approach and Cerebras' ReadAgent implementation.

Key concepts:
1. Semantic Pagination - Break documents at natural boundaries
2. Dual Memory - Maintain both full text and compressed gists
3. Selective Expansion - Only retrieve full text for relevant sections
4. Iterative Processing - Build context incrementally
"""

import re
from typing import List, Dict, Tuple, Optional
from datetime import datetime

from app.services.cerebras import CerebrasService
from app.core.logging import logger


# Prompts for gist memory operations
PROMPT_PAGINATION_TEMPLATE = """You are helping to break a long document into logical pages.

Below is a text passage with numbered break points marked as [BREAK_1], [BREAK_2], etc.

{passage}

Choose ONE break point number that represents the most semantically coherent place to end the current page (around {target_words} words).
The break should occur at a natural transition between topics or sections.

Respond with ONLY the break number (e.g., "3" if you choose [BREAK_3]).
"""

PROMPT_SHORTEN_TEMPLATE = """Summarize the following text into a concise gist that captures the key information:

{text}

Provide a brief summary (2-4 sentences) focusing on:
- Main topics and concepts
- Key facts, dates, or entities
- Important actions or decisions

Summary:"""

PROMPT_LOOKUP_TEMPLATE = """Below is a summary (gist) of each page from a document:

{gists}

Question: {question}

Based on these summaries, which page numbers would be most relevant to answer this question?
List the page numbers separated by commas (e.g., "1, 3, 5").

Relevant pages:"""

PROMPT_ANSWER_TEMPLATE = """Based on the following document pages, answer the question.

{context}

Question: {question}

Answer:"""


class GistMemory:
    """
    Gist Memory implementation for processing long documents.

    Uses semantic chunking and dual-memory structure to efficiently
    process documents that exceed LLM context windows.
    """

    def __init__(self, target_page_words: int = 600):
        """
        Initialize GistMemory processor.

        Args:
            target_page_words: Target word count per page for pagination
        """
        self.cerebras = CerebrasService()
        self.target_page_words = target_page_words

        # Storage for dual memory
        self.pages: List[List[str]] = []  # Full text pages (list of paragraphs)
        self.gists: List[str] = []  # Page summaries
        self.page_metadata: List[Dict] = []  # Metadata per page

    def clear(self):
        """Clear all stored pages and gists."""
        self.pages = []
        self.gists = []
        self.page_metadata = []

    def paginate_document(self, text: str) -> List[List[str]]:
        """
        Break document into semantic pages using AI-guided pagination.

        Args:
            text: Full document text

        Returns:
            List of pages, where each page is a list of paragraphs
        """
        # Split into paragraphs
        paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]

        if not paragraphs:
            logger.warning("No paragraphs found in document")
            return []

        logger.info(f"Paginating document: {len(paragraphs)} paragraphs")

        pages = []
        current_position = 0

        while current_position < len(paragraphs):
            # Find next page break
            page, next_position = self._get_next_page_break(
                paragraphs,
                current_position
            )

            if page:
                pages.append(page)
                logger.debug(f"Created page {len(pages)}: {len(page)} paragraphs, ~{sum(len(p.split()) for p in page)} words")

            current_position = next_position

            # Safety check to prevent infinite loop
            if current_position == current_position:
                if next_position <= current_position:
                    current_position += 1

        self.pages = pages
        logger.info(f"Document paginated into {len(pages)} pages")
        return pages

    def _get_next_page_break(
        self,
        paragraphs: List[str],
        start_paragraph: int
    ) -> Tuple[List[str], int]:
        """
        Find the next semantic page break using Cerebras.

        Args:
            paragraphs: All document paragraphs
            start_paragraph: Index to start from

        Returns:
            Tuple of (page paragraphs, next start index)
        """
        passage = []
        word_count = 0
        break_candidates = []

        # Accumulate paragraphs until we have enough candidates
        for i in range(start_paragraph, len(paragraphs)):
            para = paragraphs[i]
            passage.append(para)
            word_count += len(para.split())

            # Mark this as a potential break point (every 2-3 paragraphs)
            if len(passage) >= 2:
                break_candidates.append(len(passage))

            # Stop once we have enough content
            if word_count >= self.target_page_words * 1.5:
                break

        if not passage:
            return [], start_paragraph + 1

        # If we have break candidates, use Cerebras to choose best one
        if len(break_candidates) >= 2:
            # Insert break markers
            marked_passage = []
            for idx, para in enumerate(passage):
                marked_passage.append(para)
                if (idx + 1) in break_candidates:
                    marked_passage.append(f"[BREAK_{idx + 1}]")

            # Ask Cerebras to choose break point
            prompt = PROMPT_PAGINATION_TEMPLATE.format(
                passage='\n\n'.join(marked_passage),
                target_words=self.target_page_words
            )

            try:
                # Use Cerebras for fast break point selection
                from openai import OpenAI
                import os

                client = OpenAI(
                    api_key=os.getenv("CEREBRAS_API_KEY"),
                    base_url="https://api.cerebras.ai/v1"
                )

                response = client.chat.completions.create(
                    model="llama3.1-8b",
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=50,
                    temperature=0.3
                )

                # Parse break number
                break_text = response.choices[0].message.content.strip()
                break_match = re.search(r'(\d+)', break_text)

                if break_match:
                    break_idx = int(break_match.group(1))
                    if break_idx <= len(passage):
                        page = passage[:break_idx]
                        next_start = start_paragraph + break_idx
                        return page, next_start

            except Exception as e:
                logger.warning(f"AI pagination failed, using word count: {e}")

        # Fallback: break at target word count
        accumulated_words = 0
        for idx, para in enumerate(passage):
            accumulated_words += len(para.split())
            if accumulated_words >= self.target_page_words:
                page = passage[:idx + 1]
                next_start = start_paragraph + idx + 1
                return page, next_start

        # Use all accumulated paragraphs
        return passage, start_paragraph + len(passage)

    def create_gists(self, pages: Optional[List[List[str]]] = None) -> List[str]:
        """
        Create compressed gists for each page.

        Args:
            pages: Pages to process (uses self.pages if None)

        Returns:
            List of gist summaries
        """
        if pages is None:
            pages = self.pages

        if not pages:
            logger.warning("No pages to create gists for")
            return []

        logger.info(f"Creating gists for {len(pages)} pages")
        gists = []

        for page_num, page in enumerate(pages, 1):
            page_text = '\n\n'.join(page)

            try:
                gist = self._create_summary(page_text)
                gists.append(gist)

                # Store metadata
                self.page_metadata.append({
                    'page_num': page_num,
                    'word_count': len(page_text.split()),
                    'paragraph_count': len(page),
                    'gist_length': len(gist.split())
                })

                logger.debug(f"Page {page_num}: {len(page_text.split())} words → {len(gist.split())} word gist")

            except Exception as e:
                logger.error(f"Failed to create gist for page {page_num}: {e}")
                gists.append(f"[Error creating summary for page {page_num}]")

        self.gists = gists
        logger.info(f"Created {len(gists)} gists successfully")
        return gists

    def _create_summary(self, text: str) -> str:
        """
        Generate a concise summary of text using Cerebras.

        Args:
            text: Text to summarize

        Returns:
            Summary text
        """
        prompt = PROMPT_SHORTEN_TEMPLATE.format(text=text[:2000])  # Limit input

        from openai import OpenAI
        import os

        client = OpenAI(
            api_key=os.getenv("CEREBRAS_API_KEY"),
            base_url="https://api.cerebras.ai/v1"
        )

        response = client.chat.completions.create(
            model="llama3.1-8b",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=200,
            temperature=0.3
        )

        summary = response.choices[0].message.content.strip()

        # Remove conversational prefixes
        summary = re.sub(r'^(Here is a summary|Summary|Here\'s|The text)', '', summary, flags=re.IGNORECASE)
        summary = summary.strip(':').strip()

        return summary

    def lookup_relevant_pages(self, question: str) -> List[int]:
        """
        Identify which pages are relevant to answer a question.

        Args:
            question: Question to answer

        Returns:
            List of relevant page numbers (1-indexed)
        """
        if not self.gists:
            logger.warning("No gists available for lookup")
            return []

        # Format gists with page numbers
        gists_text = '\n\n'.join([
            f"Page {i+1}: {gist}"
            for i, gist in enumerate(self.gists)
        ])

        prompt = PROMPT_LOOKUP_TEMPLATE.format(
            gists=gists_text,
            question=question
        )

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
                max_tokens=100,
                temperature=0.2
            )

            # Parse page numbers from response
            response_text = response.choices[0].message.content.strip()
            page_numbers = re.findall(r'\d+', response_text)
            relevant_pages = [int(p) for p in page_numbers if 1 <= int(p) <= len(self.pages)]

            logger.info(f"Lookup identified {len(relevant_pages)} relevant pages: {relevant_pages}")
            return relevant_pages

        except Exception as e:
            logger.error(f"Lookup failed: {e}")
            # Fallback: return first few pages
            return list(range(1, min(4, len(self.pages) + 1)))

    def answer_question(
        self,
        question: str,
        relevant_pages: Optional[List[int]] = None
    ) -> Dict:
        """
        Answer a question using relevant document pages.

        Args:
            question: Question to answer
            relevant_pages: Page numbers to use (auto-lookup if None)

        Returns:
            Dict with answer and metadata
        """
        start_time = datetime.now()

        # Lookup if not provided
        if relevant_pages is None:
            relevant_pages = self.lookup_relevant_pages(question)

        if not relevant_pages:
            return {
                'answer': 'No relevant pages found',
                'relevant_pages': [],
                'processing_time_ms': 0
            }

        # Gather context from relevant pages
        context_parts = []
        for page_num in relevant_pages:
            if 1 <= page_num <= len(self.pages):
                page_text = '\n\n'.join(self.pages[page_num - 1])
                context_parts.append(f"=== Page {page_num} ===\n{page_text}")

        context = '\n\n'.join(context_parts)

        # Generate answer using Cerebras
        prompt = PROMPT_ANSWER_TEMPLATE.format(
            context=context[:4000],  # Limit context size
            question=question
        )

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
                max_tokens=300,
                temperature=0.5
            )

            answer = response.choices[0].message.content.strip()

            end_time = datetime.now()
            processing_time = int((end_time - start_time).total_seconds() * 1000)

            return {
                'answer': answer,
                'relevant_pages': relevant_pages,
                'processing_time_ms': processing_time,
                'pages_used': len(relevant_pages)
            }

        except Exception as e:
            logger.error(f"Answer generation failed: {e}")
            return {
                'answer': f'Error generating answer: {str(e)}',
                'relevant_pages': relevant_pages,
                'processing_time_ms': 0
            }

    def process_document(self, text: str) -> Dict:
        """
        Complete end-to-end document processing with gist memory.

        Args:
            text: Full document text

        Returns:
            Processing results with statistics
        """
        start_time = datetime.now()

        # Clear previous state
        self.clear()

        # Step 1: Paginate
        pages = self.paginate_document(text)

        if not pages:
            return {
                'success': False,
                'error': 'Failed to paginate document',
                'pages': 0
            }

        # Step 2: Create gists
        gists = self.create_gists(pages)

        end_time = datetime.now()
        processing_time = int((end_time - start_time).total_seconds() * 1000)

        # Calculate statistics
        total_words = sum(len(' '.join(page).split()) for page in pages)
        total_gist_words = sum(len(gist.split()) for gist in gists)
        compression_ratio = total_gist_words / total_words if total_words > 0 else 0

        return {
            'success': True,
            'pages': len(pages),
            'total_words': total_words,
            'total_gist_words': total_gist_words,
            'compression_ratio': round(compression_ratio, 3),
            'processing_time_ms': processing_time,
            'avg_page_words': round(total_words / len(pages)) if pages else 0,
            'metadata': self.page_metadata
        }

    def get_summary(self) -> str:
        """
        Get a complete document summary from all gists.

        Returns:
            Combined summary text
        """
        if not self.gists:
            return ""

        # Combine all gists into a cohesive summary
        summary_parts = [f"Section {i+1}: {gist}" for i, gist in enumerate(self.gists)]
        return '\n\n'.join(summary_parts)

    def search_pages(self, query: str, max_results: int = 5) -> List[Dict]:
        """
        Search for pages containing query terms.

        Args:
            query: Search query
            max_results: Maximum number of results

        Returns:
            List of matching pages with relevance scores
        """
        if not self.pages or not self.gists:
            return []

        query_lower = query.lower()
        results = []

        for i, (page, gist) in enumerate(zip(self.pages, self.gists)):
            page_text = ' '.join(page).lower()
            gist_lower = gist.lower()

            # Simple relevance scoring
            page_matches = page_text.count(query_lower)
            gist_matches = gist_lower.count(query_lower)
            relevance = page_matches + (gist_matches * 2)  # Weight gist matches higher

            if relevance > 0:
                results.append({
                    'page_num': i + 1,
                    'relevance': relevance,
                    'gist': gist,
                    'snippet': page_text[:200] + '...' if len(page_text) > 200 else page_text
                })

        # Sort by relevance
        results.sort(key=lambda x: x['relevance'], reverse=True)

        return results[:max_results]
