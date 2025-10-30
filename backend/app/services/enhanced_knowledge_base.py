"""
Enhanced Knowledge Base with LangChain Integrations

This module enhances the existing knowledge base with:
- Advanced text splitting strategies
- Multiple embedding models
- Hybrid retrieval systems
- Real-time web search integration

Based on LangChain integrations for retrievers, splitters, and embeddings.
"""

import os
import asyncio
from typing import Dict, Any, List, Optional, Union
from datetime import datetime
from dataclasses import dataclass, field

from langchain_text_splitters import (
    RecursiveCharacterTextSplitter,
    MarkdownHeaderTextSplitter,
    CharacterTextSplitter
)
from langchain_community.retrievers import (
    TavilySearchAPIRetriever,
    WikipediaRetriever,
    ArxivRetriever
)
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.embeddings import HuggingFaceBgeEmbeddings
from langchain_ollama import OllamaEmbeddings
from langchain.retrievers import EnsembleRetriever
from langchain_core.documents import Document
from langchain_core.retrievers import BaseRetriever

from app.core.logging import setup_logging
from app.core.config import settings
from app.services.knowledge_base import KnowledgeBaseService

logger = setup_logging(__name__)


@dataclass
class DocumentChunk:
    """Enhanced document chunk with metadata."""
    content: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    chunk_id: str = ""
    source_document: str = ""
    chunk_index: int = 0
    embedding_model: str = ""
    retrieval_score: float = 0.0


class EnhancedKnowledgeBase:
    """
    Enhanced knowledge base with LangChain integrations.
    
    Features:
    - Multiple text splitting strategies
    - Hybrid retrieval (vector + web + wiki)
    - Multiple embedding models
    - Real-time information retrieval
    - Document structure preservation
    """
    
    def __init__(
        self,
        embedding_model: str = "bge-large",
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
        enable_web_search: bool = True,
        enable_wiki_search: bool = True
    ):
        """
        Initialize Enhanced Knowledge Base.
        
        Args:
            embedding_model: Embedding model to use (bge-large, local, openai)
            chunk_size: Size of document chunks
            chunk_overlap: Overlap between chunks
            enable_web_search: Enable real-time web search
            enable_wiki_search: Enable Wikipedia search
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.enable_web_search = enable_web_search
        self.enable_wiki_search = enable_wiki_search
        
        # Initialize text splitters
        self._setup_text_splitters()
        
        # Initialize embedding models
        self._setup_embedding_models(embedding_model)
        
        # Initialize retrievers
        self._setup_retrievers()
        
        # Initialize base knowledge base
        self.base_kb = KnowledgeBaseService()
        
        logger.info(f"Enhanced Knowledge Base initialized: model={embedding_model}")
    
    def _setup_text_splitters(self) -> None:
        """Setup text splitters for different document types."""
        # General text splitter
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap,
            separators=["\n\n", "\n", " ", ""],
            length_function=len
        )
        
        # Markdown splitter for structured documents
        self.markdown_splitter = MarkdownHeaderTextSplitter(
            headers_to_split_on=[
                ("#", "Header 1"),
                ("##", "Header 2"),
                ("###", "Header 3"),
                ("####", "Header 4")
            ]
        )
        
        # Code splitter for technical documents
        self.code_splitter = RecursiveCharacterTextSplitter.from_language(
            language="python",
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap
        )
        
        logger.info("Text splitters configured")
    
    def _setup_embedding_models(self, model_type: str) -> None:
        """Setup embedding models based on type."""
        if model_type == "bge-large":
            # BGE embeddings - best open-source option
            self.embeddings = HuggingFaceBgeEmbeddings(
                model_name="BAAI/bge-large-en-v1.5",
                model_kwargs={'device': 'cpu'},
                encode_kwargs={'normalize_embeddings': True}
            )
            self.embedding_model_name = "bge-large-en-v1.5"
            
        elif model_type == "local":
            # Local Ollama embeddings
            self.embeddings = OllamaEmbeddings(
                model="nomic-embed-text",
                base_url="http://localhost:11434"
            )
            self.embedding_model_name = "nomic-embed-text"
            
        elif model_type == "openai":
            # OpenAI embeddings (if available)
            from langchain_openai import OpenAIEmbeddings
            self.embeddings = OpenAIEmbeddings(
                model="text-embedding-3-small",
                openai_api_key=os.getenv("OPENAI_API_KEY")
            )
            self.embedding_model_name = "text-embedding-3-small"
            
        else:
            # Default to sentence-transformers
            self.embeddings = HuggingFaceEmbeddings(
                model_name="sentence-transformers/all-MiniLM-L6-v2",
                model_kwargs={'device': 'cpu'}
            )
            self.embedding_model_name = "all-MiniLM-L6-v2"
        
        logger.info(f"Embedding model configured: {self.embedding_model_name}")
    
    def _setup_retrievers(self) -> None:
        """Setup retrievers for different information sources."""
        self.retrievers = {}
        
        # Web search retriever
        if self.enable_web_search:
            try:
                api_key = os.getenv("TAVILY_API_KEY")
                if api_key:
                    self.retrievers["web"] = TavilySearchAPIRetriever(
                        k=5,
                        search_depth="advanced",
                        include_answer=True,
                        api_key=api_key
                    )
                    logger.info("Web search retriever configured")
            except Exception as e:
                logger.warning(f"Web search retriever not available: {e}")
        
        # Wikipedia retriever
        if self.enable_wiki_search:
            try:
                self.retrievers["wikipedia"] = WikipediaRetriever(
                    lang="en",
                    load_max_docs=3
                )
                logger.info("Wikipedia retriever configured")
            except Exception as e:
                logger.warning(f"Wikipedia retriever not available: {e}")
        
        # Arxiv retriever for research papers
        try:
            self.retrievers["arxiv"] = ArxivRetriever(
                load_max_docs=3,
                doc_content_chars_max=2000
            )
            logger.info("Arxiv retriever configured")
        except Exception as e:
            logger.warning(f"Arxiv retriever not available: {e}")
    
    async def process_document(
        self,
        document_path: str,
        document_type: str = "general",
        metadata: Optional[Dict[str, Any]] = None
    ) -> List[DocumentChunk]:
        """
        Process a document with enhanced text splitting.
        
        Args:
            document_path: Path to the document
            document_type: Type of document (general, markdown, code, pdf)
            metadata: Additional metadata for the document
            
        Returns:
            List of processed document chunks
        """
        try:
            # Load document content
            content = await self._load_document_content(document_path, document_type)
            
            # Choose appropriate splitter
            if document_type == "markdown":
                splits = self.markdown_splitter.split_text(content)
            elif document_type == "code":
                splits = self.code_splitter.split_text(content)
            else:
                splits = self.text_splitter.split_text(content)
            
            # Create document chunks
            chunks = []
            for i, split in enumerate(splits):
                chunk = DocumentChunk(
                    content=split,
                    metadata={
                        **(metadata or {}),
                        "document_path": document_path,
                        "document_type": document_type,
                        "chunk_index": i,
                        "total_chunks": len(splits),
                        "embedding_model": self.embedding_model_name,
                        "processed_at": datetime.now().isoformat()
                    },
                    chunk_id=f"{document_path}_{i}",
                    source_document=document_path,
                    chunk_index=i,
                    embedding_model=self.embedding_model_name
                )
                chunks.append(chunk)
            
            # Generate embeddings for chunks
            await self._generate_embeddings(chunks)
            
            # Store in knowledge base
            await self._store_chunks(chunks)
            
            logger.info(f"Document processed: {document_path}, {len(chunks)} chunks")
            return chunks
            
        except Exception as e:
            logger.error(f"Document processing failed: {document_path}, error: {e}")
            return []
    
    async def search_knowledge(
        self,
        query: str,
        search_type: str = "hybrid",
        max_results: int = 10
    ) -> List[DocumentChunk]:
        """
        Search knowledge base with enhanced retrieval.
        
        Args:
            query: Search query
            search_type: Type of search (vector, web, wiki, hybrid)
            max_results: Maximum number of results
            
        Returns:
            List of relevant document chunks
        """
        try:
            results = []
            
            if search_type == "vector" or search_type == "hybrid":
                # Vector search in knowledge base
                vector_results = await self._vector_search(query, max_results)
                results.extend(vector_results)
            
            if search_type == "web" or search_type == "hybrid":
                # Web search for real-time information
                if "web" in self.retrievers:
                    web_results = await self._web_search(query, max_results)
                    results.extend(web_results)
            
            if search_type == "wiki" or search_type == "hybrid":
                # Wikipedia search for background information
                if "wikipedia" in self.retrievers:
                    wiki_results = await self._wiki_search(query, max_results)
                    results.extend(wiki_results)
            
            # Remove duplicates and rank results
            unique_results = self._deduplicate_and_rank(results)
            
            logger.info(f"Knowledge search complete: {len(unique_results)} results")
            return unique_results[:max_results]
            
        except Exception as e:
            logger.error(f"Knowledge search failed: {e}")
            return []
    
    async def _load_document_content(self, document_path: str, document_type: str) -> str:
        """Load document content based on type."""
        if document_type == "pdf":
            import pdfplumber
            with pdfplumber.open(document_path) as pdf:
                content = "\n".join(filter(None, [page.extract_text() for page in pdf.pages]))
        elif document_type == "docx":
            from docx import Document
            doc = Document(document_path)
            content = "\n".join([paragraph.text for paragraph in doc.paragraphs])
        else:
            with open(document_path, 'r', encoding='utf-8') as file:
                content = file.read()
        
        return content
    
    async def _generate_embeddings(self, chunks: List[DocumentChunk]) -> None:
        """Generate embeddings for document chunks."""
        try:
            texts = [chunk.content for chunk in chunks]
            embeddings = await self.embeddings.aembed_documents(texts)
            
            for chunk, embedding in zip(chunks, embeddings):
                chunk.metadata["embedding"] = embedding
                chunk.metadata["embedding_dimension"] = len(embedding)
            
            logger.debug(f"Generated embeddings for {len(chunks)} chunks")
            
        except Exception as e:
            logger.error(f"Embedding generation failed: {e}")
    
    async def _store_chunks(self, chunks: List[DocumentChunk]) -> None:
        """Store document chunks in knowledge base."""
        try:
            for chunk in chunks:
                await self.base_kb.store_document(
                    content=chunk.content,
                    metadata=chunk.metadata,
                    document_id=chunk.chunk_id
                )
            
            logger.debug(f"Stored {len(chunks)} chunks in knowledge base")
            
        except Exception as e:
            logger.error(f"Chunk storage failed: {e}")
    
    async def _vector_search(self, query: str, max_results: int) -> List[DocumentChunk]:
        """Perform vector search in knowledge base."""
        try:
            # Generate query embedding
            query_embedding = await self.embeddings.aembed_query(query)
            
            # Search in knowledge base
            results = await self.base_kb.search_similar(
                query_embedding=query_embedding,
                limit=max_results
            )
            
            # Convert to DocumentChunk format
            chunks = []
            for result in results:
                chunk = DocumentChunk(
                    content=result["content"],
                    metadata=result["metadata"],
                    chunk_id=result["document_id"],
                    retrieval_score=result.get("similarity_score", 0.0)
                )
                chunks.append(chunk)
            
            return chunks
            
        except Exception as e:
            logger.error(f"Vector search failed: {e}")
            return []
    
    async def _web_search(self, query: str, max_results: int) -> List[DocumentChunk]:
        """Perform web search for real-time information."""
        try:
            web_retriever = self.retrievers["web"]
            documents = await web_retriever.ainvoke(query)
            
            chunks = []
            for doc in documents[:max_results]:
                chunk = DocumentChunk(
                    content=doc.page_content,
                    metadata={
                        **doc.metadata,
                        "source": "web_search",
                        "retrieval_type": "web"
                    },
                    retrieval_score=0.8  # Web results are generally relevant
                )
                chunks.append(chunk)
            
            return chunks
            
        except Exception as e:
            logger.error(f"Web search failed: {e}")
            return []
    
    async def _wiki_search(self, query: str, max_results: int) -> List[DocumentChunk]:
        """Perform Wikipedia search for background information."""
        try:
            wiki_retriever = self.retrievers["wikipedia"]
            documents = await wiki_retriever.ainvoke(query)
            
            chunks = []
            for doc in documents[:max_results]:
                chunk = DocumentChunk(
                    content=doc.page_content,
                    metadata={
                        **doc.metadata,
                        "source": "wikipedia",
                        "retrieval_type": "wiki"
                    },
                    retrieval_score=0.7  # Wikipedia is generally reliable
                )
                chunks.append(chunk)
            
            return chunks
            
        except Exception as e:
            logger.error(f"Wikipedia search failed: {e}")
            return []
    
    def _deduplicate_and_rank(self, results: List[DocumentChunk]) -> List[DocumentChunk]:
        """Remove duplicates and rank results by relevance."""
        # Remove duplicates based on content similarity
        unique_results = []
        seen_contents = set()
        
        for result in results:
            content_hash = hash(result.content[:100])  # Use first 100 chars as hash
            if content_hash not in seen_contents:
                seen_contents.add(content_hash)
                unique_results.append(result)
        
        # Sort by retrieval score (higher is better)
        unique_results.sort(key=lambda x: x.retrieval_score, reverse=True)
        
        return unique_results
    
    async def get_knowledge_summary(self) -> Dict[str, Any]:
        """Get summary of knowledge base contents."""
        try:
            # Get basic stats from base knowledge base
            base_stats = await self.base_kb.get_stats()
            
            return {
                "total_documents": base_stats.get("total_documents", 0),
                "total_chunks": base_stats.get("total_chunks", 0),
                "embedding_model": self.embedding_model_name,
                "chunk_size": self.chunk_size,
                "chunk_overlap": self.chunk_overlap,
                "retrievers_available": list(self.retrievers.keys()),
                "web_search_enabled": self.enable_web_search,
                "wiki_search_enabled": self.enable_wiki_search
            }
            
        except Exception as e:
            logger.error(f"Knowledge summary failed: {e}")
            return {"error": str(e)}
    
    async def health_check(self) -> Dict[str, Any]:
        """Perform health check on enhanced knowledge base."""
        try:
            health_status = {
                "status": "healthy",
                "timestamp": datetime.now().isoformat(),
                "components": {}
            }
            
            # Check embedding model
            try:
                test_embedding = await self.embeddings.aembed_query("test")
                health_status["components"]["embeddings"] = "healthy"
            except Exception as e:
                health_status["components"]["embeddings"] = f"error: {str(e)}"
                health_status["status"] = "degraded"
            
            # Check retrievers
            for name, retriever in self.retrievers.items():
                try:
                    # Test with a simple query
                    test_results = await retriever.ainvoke("test")
                    health_status["components"][f"retriever_{name}"] = "healthy"
                except Exception as e:
                    health_status["components"][f"retriever_{name}"] = f"error: {str(e)}"
                    health_status["status"] = "degraded"
            
            # Check base knowledge base
            try:
                await self.base_kb.health_check()
                health_status["components"]["base_knowledge_base"] = "healthy"
            except Exception as e:
                health_status["components"]["base_knowledge_base"] = f"error: {str(e)}"
                health_status["status"] = "degraded"
            
            return health_status
            
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
