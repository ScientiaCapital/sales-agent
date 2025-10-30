"""
Enhanced Vector Store with LangChain Integrations

This module enhances the existing vector store with:
- Multiple vector store backends (PGVector, FAISS, Chroma, Qdrant)
- Advanced document loaders
- Key-value store integration
- Unified interface for all vector operations

Based on LangChain integrations for vector stores, stores, and document loaders.
"""

import os
import asyncio
from typing import Dict, Any, List, Optional, Union, Literal
from datetime import datetime
from dataclasses import dataclass, field
from enum import Enum

from langchain_core.documents import Document
from langchain_core.vectorstores import VectorStore
from langchain_core.embeddings import Embeddings
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.embeddings import HuggingFaceBgeEmbeddings
from langchain_ollama import OllamaEmbeddings
from langchain_postgres import PGVector
from langchain_community.vectorstores import FAISS, Chroma, Qdrant
from langchain_community.document_loaders import (
    PyPDFLoader,
    Docx2txtLoader,
    UnstructuredMarkdownLoader,
    WebBaseLoader,
    CSVLoader,
    TextLoader
)
from langchain_core.stores import BaseStore
from langchain_community.stores import RedisStore, InMemoryStore

from app.core.logging import setup_logging
from app.core.config import settings

logger = setup_logging(__name__)


class VectorStoreType(str, Enum):
    """Supported vector store types."""
    PGVECTOR = "pgvector"
    FAISS = "faiss"
    CHROMA = "chroma"
    QDRANT = "qdrant"
    IN_MEMORY = "in_memory"


class DocumentType(str, Enum):
    """Supported document types."""
    PDF = "pdf"
    DOCX = "docx"
    MD = "markdown"
    TXT = "text"
    CSV = "csv"
    WEB = "web"


@dataclass
class VectorStoreConfig:
    """Configuration for vector store setup."""
    store_type: VectorStoreType
    embedding_model: str = "bge-large"
    collection_name: str = "sales_documents"
    chunk_size: int = 1000
    chunk_overlap: int = 200
    distance_strategy: str = "cosine"
    persist_directory: Optional[str] = None


class EnhancedVectorStore:
    """
    Enhanced vector store with multiple backend support.
    
    Features:
    - Multiple vector store backends
    - Advanced document loaders
    - Key-value store integration
    - Unified interface for all operations
    - Automatic fallback between backends
    """
    
    def __init__(self, config: VectorStoreConfig):
        """
        Initialize Enhanced Vector Store.
        
        Args:
            config: Vector store configuration
        """
        self.config = config
        self.vector_store: Optional[VectorStore] = None
        self.embeddings: Optional[Embeddings] = None
        self.key_value_store: Optional[BaseStore] = None
        
        # Initialize components
        self._setup_embeddings()
        self._setup_vector_store()
        self._setup_key_value_store()
        
        # Document loaders
        self._setup_document_loaders()
        
        logger.info(f"Enhanced Vector Store initialized: {config.store_type}")
    
    def _setup_embeddings(self) -> None:
        """Setup embedding model based on configuration."""
        if self.config.embedding_model == "bge-large":
            self.embeddings = HuggingFaceBgeEmbeddings(
                model_name="BAAI/bge-large-en-v1.5",
                model_kwargs={'device': 'cpu'},
                encode_kwargs={'normalize_embeddings': True}
            )
        elif self.config.embedding_model == "local":
            self.embeddings = OllamaEmbeddings(
                model="nomic-embed-text",
                base_url="http://localhost:11434"
            )
        else:
            # Default to sentence-transformers
            self.embeddings = HuggingFaceEmbeddings(
                model_name="sentence-transformers/all-MiniLM-L6-v2",
                model_kwargs={'device': 'cpu'}
            )
        
        logger.info(f"Embeddings configured: {self.config.embedding_model}")
    
    def _setup_vector_store(self) -> None:
        """Setup vector store based on configuration."""
        try:
            if self.config.store_type == VectorStoreType.PGVECTOR:
                self._setup_pgvector()
            elif self.config.store_type == VectorStoreType.FAISS:
                self._setup_faiss()
            elif self.config.store_type == VectorStoreType.CHROMA:
                self._setup_chroma()
            elif self.config.store_type == VectorStoreType.QDRANT:
                self._setup_qdrant()
            elif self.config.store_type == VectorStoreType.IN_MEMORY:
                self._setup_in_memory()
            else:
                raise ValueError(f"Unsupported vector store type: {self.config.store_type}")
            
            logger.info(f"Vector store configured: {self.config.store_type}")
            
        except Exception as e:
            logger.error(f"Vector store setup failed: {e}")
            # Fallback to in-memory
            self._setup_in_memory()
    
    def _setup_pgvector(self) -> None:
        """Setup PGVector store."""
        connection_string = os.getenv("DATABASE_URL")
        if not connection_string:
            raise ValueError("DATABASE_URL environment variable not set")
        
        self.vector_store = PGVector(
            connection_string=connection_string,
            embeddings=self.embeddings,
            collection_name=self.config.collection_name,
            distance_strategy=self.config.distance_strategy
        )
    
    def _setup_faiss(self) -> None:
        """Setup FAISS store."""
        persist_dir = self.config.persist_directory or "./faiss_index"
        os.makedirs(persist_dir, exist_ok=True)
        
        self.vector_store = FAISS.from_texts(
            texts=[""],  # Empty initial texts
            embedding=self.embeddings,
            metadatas=[{}]
        )
    
    def _setup_chroma(self) -> None:
        """Setup Chroma store."""
        persist_dir = self.config.persist_directory or "./chroma_db"
        os.makedirs(persist_dir, exist_ok=True)
        
        self.vector_store = Chroma(
            collection_name=self.config.collection_name,
            embedding_function=self.embeddings,
            persist_directory=persist_dir
        )
    
    def _setup_qdrant(self) -> None:
        """Setup Qdrant store."""
        # Qdrant requires a running Qdrant server
        # For now, we'll use in-memory mode
        self.vector_store = Qdrant.from_texts(
            texts=[""],  # Empty initial texts
            embedding=self.embeddings,
            location=":memory:",
            collection_name=self.config.collection_name
        )
    
    def _setup_in_memory(self) -> None:
        """Setup in-memory store."""
        from langchain_core.vectorstores import InMemoryVectorStore
        self.vector_store = InMemoryVectorStore(embedding=self.embeddings)
    
    def _setup_key_value_store(self) -> None:
        """Setup key-value store for metadata and caching."""
        try:
            # Try Redis first
            redis_url = os.getenv("REDIS_URL")
            if redis_url:
                self.key_value_store = RedisStore(redis_url=redis_url)
                logger.info("Key-value store configured: Redis")
            else:
                # Fallback to in-memory
                self.key_value_store = InMemoryStore()
                logger.info("Key-value store configured: InMemory")
        except Exception as e:
            logger.warning(f"Key-value store setup failed: {e}, using in-memory")
            self.key_value_store = InMemoryStore()
    
    def _setup_document_loaders(self) -> None:
        """Setup document loaders for different file types."""
        self.document_loaders = {
            DocumentType.PDF: PyPDFLoader,
            DocumentType.DOCX: Docx2txtLoader,
            DocumentType.MD: UnstructuredMarkdownLoader,
            DocumentType.TXT: TextLoader,
            DocumentType.CSV: CSVLoader,
            DocumentType.WEB: WebBaseLoader
        }
        
        logger.info(f"Document loaders configured: {list(self.document_loaders.keys())}")
    
    async def add_documents(
        self,
        documents: List[Document],
        ids: Optional[List[str]] = None
    ) -> List[str]:
        """
        Add documents to the vector store.
        
        Args:
            documents: List of documents to add
            ids: Optional list of document IDs
            
        Returns:
            List of document IDs
        """
        try:
            if ids:
                result = await self.vector_store.aadd_documents(documents, ids=ids)
            else:
                result = await self.vector_store.aadd_documents(documents)
            
            # Store metadata in key-value store
            if self.key_value_store:
                for i, doc in enumerate(documents):
                    doc_id = ids[i] if ids else f"doc_{i}_{int(datetime.now().timestamp())}"
                    await self.key_value_store.aput(
                        f"doc_metadata:{doc_id}",
                        doc.metadata
                    )
            
            logger.info(f"Added {len(documents)} documents to vector store")
            return result if isinstance(result, list) else [str(result)]
            
        except Exception as e:
            logger.error(f"Failed to add documents: {e}")
            return []
    
    async def search_similar(
        self,
        query: str,
        k: int = 5,
        filter: Optional[Dict[str, Any]] = None
    ) -> List[Document]:
        """
        Search for similar documents.
        
        Args:
            query: Search query
            k: Number of results to return
            filter: Optional metadata filter
            
        Returns:
            List of similar documents
        """
        try:
            if filter:
                results = await self.vector_store.asimilarity_search(
                    query, k=k, filter=filter
                )
            else:
                results = await self.vector_store.asimilarity_search(query, k=k)
            
            logger.debug(f"Found {len(results)} similar documents")
            return results
            
        except Exception as e:
            logger.error(f"Similarity search failed: {e}")
            return []
    
    async def search_with_score(
        self,
        query: str,
        k: int = 5,
        filter: Optional[Dict[str, Any]] = None
    ) -> List[tuple[Document, float]]:
        """
        Search for similar documents with similarity scores.
        
        Args:
            query: Search query
            k: Number of results to return
            filter: Optional metadata filter
            
        Returns:
            List of (document, score) tuples
        """
        try:
            if filter:
                results = await self.vector_store.asimilarity_search_with_score(
                    query, k=k, filter=filter
                )
            else:
                results = await self.vector_store.asimilarity_search_with_score(query, k=k)
            
            logger.debug(f"Found {len(results)} similar documents with scores")
            return results
            
        except Exception as e:
            logger.error(f"Similarity search with score failed: {e}")
            return []
    
    async def delete_documents(self, ids: List[str]) -> bool:
        """
        Delete documents by IDs.
        
        Args:
            ids: List of document IDs to delete
            
        Returns:
            True if successful
        """
        try:
            await self.vector_store.adelete(ids)
            
            # Remove metadata from key-value store
            if self.key_value_store:
                for doc_id in ids:
                    await self.key_value_store.adelete(f"doc_metadata:{doc_id}")
            
            logger.info(f"Deleted {len(ids)} documents")
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete documents: {e}")
            return False
    
    async def load_document(
        self,
        file_path: str,
        document_type: DocumentType,
        metadata: Optional[Dict[str, Any]] = None
    ) -> List[Document]:
        """
        Load document using appropriate loader.
        
        Args:
            file_path: Path to the document
            document_type: Type of document
            metadata: Additional metadata
            
        Returns:
            List of loaded documents
        """
        try:
            loader_class = self.document_loaders.get(document_type)
            if not loader_class:
                raise ValueError(f"Unsupported document type: {document_type}")
            
            # Load document
            if document_type == DocumentType.WEB:
                loader = loader_class([file_path])
            else:
                loader = loader_class(file_path)
            
            documents = loader.load()
            
            # Add metadata
            if metadata:
                for doc in documents:
                    doc.metadata.update(metadata)
            
            # Add document type to metadata
            for doc in documents:
                doc.metadata["document_type"] = document_type.value
                doc.metadata["source"] = file_path
                doc.metadata["loaded_at"] = datetime.now().isoformat()
            
            logger.info(f"Loaded document: {file_path}, {len(documents)} pages")
            return documents
            
        except Exception as e:
            logger.error(f"Failed to load document: {file_path}, error: {e}")
            return []
    
    async def process_and_store_document(
        self,
        file_path: str,
        document_type: DocumentType,
        metadata: Optional[Dict[str, Any]] = None,
        chunk_size: Optional[int] = None,
        chunk_overlap: Optional[int] = None
    ) -> List[str]:
        """
        Process and store a document with chunking.
        
        Args:
            file_path: Path to the document
            document_type: Type of document
            metadata: Additional metadata
            chunk_size: Override default chunk size
            chunk_overlap: Override default chunk overlap
            
        Returns:
            List of document IDs
        """
        try:
            # Load document
            documents = await self.load_document(file_path, document_type, metadata)
            
            if not documents:
                return []
            
            # Chunk documents if needed
            if chunk_size or chunk_overlap:
                from langchain_text_splitters import RecursiveCharacterTextSplitter
                
                text_splitter = RecursiveCharacterTextSplitter(
                    chunk_size=chunk_size or self.config.chunk_size,
                    chunk_overlap=chunk_overlap or self.config.chunk_overlap,
                    separators=["\n\n", "\n", " ", ""]
                )
                
                documents = text_splitter.split_documents(documents)
            
            # Store documents
            document_ids = await self.add_documents(documents)
            
            logger.info(f"Processed and stored document: {file_path}, {len(document_ids)} chunks")
            return document_ids
            
        except Exception as e:
            logger.error(f"Failed to process and store document: {file_path}, error: {e}")
            return []
    
    async def get_document_metadata(self, doc_id: str) -> Optional[Dict[str, Any]]:
        """
        Get document metadata from key-value store.
        
        Args:
            doc_id: Document ID
            
        Returns:
            Document metadata or None
        """
        try:
            if not self.key_value_store:
                return None
            
            metadata = await self.key_value_store.aget(f"doc_metadata:{doc_id}")
            return metadata
            
        except Exception as e:
            logger.error(f"Failed to get document metadata: {e}")
            return None
    
    async def update_document_metadata(
        self,
        doc_id: str,
        metadata: Dict[str, Any]
    ) -> bool:
        """
        Update document metadata in key-value store.
        
        Args:
            doc_id: Document ID
            metadata: Updated metadata
            
        Returns:
            True if successful
        """
        try:
            if not self.key_value_store:
                return False
            
            await self.key_value_store.aput(f"doc_metadata:{doc_id}", metadata)
            logger.debug(f"Updated metadata for document: {doc_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to update document metadata: {e}")
            return False
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get vector store statistics."""
        try:
            # This is a simplified stats implementation
            # In production, you'd want more detailed statistics
            stats = {
                "store_type": self.config.store_type.value,
                "embedding_model": self.config.embedding_model,
                "collection_name": self.config.collection_name,
                "chunk_size": self.config.chunk_size,
                "chunk_overlap": self.config.chunk_overlap,
                "distance_strategy": self.config.distance_strategy,
                "key_value_store_available": self.key_value_store is not None,
                "document_loaders": list(self.document_loaders.keys())
            }
            
            return stats
            
        except Exception as e:
            logger.error(f"Failed to get stats: {e}")
            return {"error": str(e)}
    
    async def health_check(self) -> Dict[str, Any]:
        """Perform health check on vector store."""
        try:
            health_status = {
                "status": "healthy",
                "timestamp": datetime.now().isoformat(),
                "components": {}
            }
            
            # Check vector store
            try:
                # Test with a simple search
                test_results = await self.search_similar("test", k=1)
                health_status["components"]["vector_store"] = "healthy"
            except Exception as e:
                health_status["components"]["vector_store"] = f"error: {str(e)}"
                health_status["status"] = "degraded"
            
            # Check embeddings
            try:
                test_embedding = await self.embeddings.aembed_query("test")
                health_status["components"]["embeddings"] = "healthy"
            except Exception as e:
                health_status["components"]["embeddings"] = f"error: {str(e)}"
                health_status["status"] = "degraded"
            
            # Check key-value store
            if self.key_value_store:
                try:
                    await self.key_value_store.aput("health_check", "test")
                    await self.key_value_store.adelete("health_check")
                    health_status["components"]["key_value_store"] = "healthy"
                except Exception as e:
                    health_status["components"]["key_value_store"] = f"error: {str(e)}"
                    health_status["status"] = "degraded"
            
            return health_status
            
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
