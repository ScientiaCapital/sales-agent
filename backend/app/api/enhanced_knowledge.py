"""
Enhanced Knowledge Base API Endpoints

This module provides API endpoints for the enhanced knowledge base system
with LangChain integrations for vector stores, document loaders, and retrievers.

Features:
- Multiple vector store backends
- Advanced document processing
- Hybrid search capabilities
- Real-time web and Wikipedia search
"""

from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Query
from typing import List, Optional, Dict, Any, Literal
from pydantic import BaseModel, Field
import asyncio

from app.services.enhanced_knowledge_base import EnhancedKnowledgeBase
from app.services.enhanced_vector_store import (
    EnhancedVectorStore,
    VectorStoreConfig,
    VectorStoreType,
    DocumentType
)
from app.core.logging import setup_logging

logger = setup_logging(__name__)

router = APIRouter(prefix="/api/v1/enhanced-knowledge", tags=["enhanced-knowledge"])

# Global instances (in production, use dependency injection)
enhanced_kb: Optional[EnhancedKnowledgeBase] = None
vector_store: Optional[EnhancedVectorStore] = None


@router.on_event("startup")
async def startup_event():
    """Initialize enhanced knowledge base on startup."""
    global enhanced_kb, vector_store
    
    try:
        # Initialize enhanced knowledge base
        enhanced_kb = EnhancedKnowledgeBase(
            embedding_model="bge-large",
            chunk_size=1000,
            chunk_overlap=200,
            enable_web_search=True,
            enable_wiki_search=True
        )
        
        # Initialize vector store
        vector_config = VectorStoreConfig(
            store_type=VectorStoreType.PGVECTOR,
            embedding_model="bge-large",
            collection_name="sales_documents"
        )
        vector_store = EnhancedVectorStore(vector_config)
        
        logger.info("Enhanced knowledge base initialized")
        
    except Exception as e:
        logger.error(f"Failed to initialize enhanced knowledge base: {e}")


# ========== Request/Response Models ==========

class DocumentUploadRequest(BaseModel):
    """Request model for document upload."""
    document_type: DocumentType = Field(..., description="Type of document")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")
    chunk_size: Optional[int] = Field(None, description="Override chunk size")
    chunk_overlap: Optional[int] = Field(None, description="Override chunk overlap")


class DocumentUploadResponse(BaseModel):
    """Response model for document upload."""
    success: bool
    document_ids: List[str]
    chunks_created: int
    processing_time_ms: int
    message: str


class SearchRequest(BaseModel):
    """Request model for knowledge search."""
    query: str = Field(..., description="Search query")
    search_type: Literal["vector", "web", "wiki", "hybrid"] = Field("hybrid", description="Type of search")
    max_results: int = Field(10, description="Maximum number of results")
    filter: Optional[Dict[str, Any]] = Field(None, description="Metadata filter")


class SearchResponse(BaseModel):
    """Response model for knowledge search."""
    query: str
    search_type: str
    results: List[Dict[str, Any]]
    total_results: int
    search_time_ms: int


class VectorStoreStatsResponse(BaseModel):
    """Response model for vector store statistics."""
    store_type: str
    embedding_model: str
    collection_name: str
    chunk_size: int
    chunk_overlap: int
    distance_strategy: str
    key_value_store_available: bool
    document_loaders: List[str]


# ========== Document Processing Endpoints ==========

@router.post("/documents/upload", response_model=DocumentUploadResponse)
async def upload_document(
    file: UploadFile = File(...),
    document_type: DocumentType = Form(...),
    metadata: Optional[str] = Form(None),
    chunk_size: Optional[int] = Form(None),
    chunk_overlap: Optional[int] = Form(None)
):
    """
    Upload and process a document.
    
    Supports multiple document types:
    - PDF: PyPDFLoader
    - DOCX: Docx2txtLoader  
    - Markdown: UnstructuredMarkdownLoader
    - Text: TextLoader
    - CSV: CSVLoader
    - Web: WebBaseLoader
    """
    if not vector_store:
        raise HTTPException(status_code=500, detail="Vector store not initialized")
    
    try:
        import tempfile
        import json
        
        # Parse metadata
        parsed_metadata = {}
        if metadata:
            try:
                parsed_metadata = json.loads(metadata)
            except json.JSONDecodeError:
                raise HTTPException(status_code=400, detail="Invalid metadata JSON")
        
        # Save uploaded file temporarily
        with tempfile.NamedTemporaryFile(delete=False, suffix=f".{document_type.value}") as temp_file:
            content = await file.read()
            temp_file.write(content)
            temp_file_path = temp_file.name
        
        # Process document
        start_time = asyncio.get_event_loop().time()
        document_ids = await vector_store.process_and_store_document(
            file_path=temp_file_path,
            document_type=document_type,
            metadata={
                **parsed_metadata,
                "original_filename": file.filename,
                "content_type": file.content_type
            },
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap
        )
        end_time = asyncio.get_event_loop().time()
        
        # Clean up temp file
        import os
        os.unlink(temp_file_path)
        
        processing_time_ms = int((end_time - start_time) * 1000)
        
        return DocumentUploadResponse(
            success=True,
            document_ids=document_ids,
            chunks_created=len(document_ids),
            processing_time_ms=processing_time_ms,
            message=f"Document processed successfully: {len(document_ids)} chunks created"
        )
        
    except Exception as e:
        logger.error(f"Document upload failed: {e}")
        raise HTTPException(status_code=500, detail=f"Document processing failed: {str(e)}")


@router.post("/documents/load-url", response_model=DocumentUploadResponse)
async def load_web_document(
    url: str = Form(...),
    metadata: Optional[str] = Form(None)
):
    """
    Load and process a document from a URL.
    
    Uses WebBaseLoader to fetch and process web content.
    """
    if not vector_store:
        raise HTTPException(status_code=500, detail="Vector store not initialized")
    
    try:
        import json
        
        # Parse metadata
        parsed_metadata = {}
        if metadata:
            try:
                parsed_metadata = json.loads(metadata)
            except json.JSONDecodeError:
                raise HTTPException(status_code=400, detail="Invalid metadata JSON")
        
        # Process web document
        start_time = asyncio.get_event_loop().time()
        document_ids = await vector_store.process_and_store_document(
            file_path=url,
            document_type=DocumentType.WEB,
            metadata={
                **parsed_metadata,
                "source_url": url
            }
        )
        end_time = asyncio.get_event_loop().time()
        
        processing_time_ms = int((end_time - start_time) * 1000)
        
        return DocumentUploadResponse(
            success=True,
            document_ids=document_ids,
            chunks_created=len(document_ids),
            processing_time_ms=processing_time_ms,
            message=f"Web document processed successfully: {len(document_ids)} chunks created"
        )
        
    except Exception as e:
        logger.error(f"Web document loading failed: {e}")
        raise HTTPException(status_code=500, detail=f"Web document loading failed: {str(e)}")


# ========== Search Endpoints ==========

@router.post("/search", response_model=SearchResponse)
async def search_knowledge(request: SearchRequest):
    """
    Search the knowledge base with enhanced retrieval.
    
    Search types:
    - vector: Vector similarity search only
    - web: Real-time web search only
    - wiki: Wikipedia search only
    - hybrid: Combined search across all sources
    """
    if not enhanced_kb:
        raise HTTPException(status_code=500, detail="Enhanced knowledge base not initialized")
    
    try:
        start_time = asyncio.get_event_loop().time()
        
        # Perform search
        results = await enhanced_kb.search_knowledge(
            query=request.query,
            search_type=request.search_type,
            max_results=request.max_results
        )
        
        end_time = asyncio.get_event_loop().time()
        search_time_ms = int((end_time - start_time) * 1000)
        
        # Format results
        formatted_results = []
        for chunk in results:
            formatted_results.append({
                "content": chunk.content,
                "metadata": chunk.metadata,
                "chunk_id": chunk.chunk_id,
                "source_document": chunk.source_document,
                "retrieval_score": chunk.retrieval_score,
                "embedding_model": chunk.embedding_model
            })
        
        return SearchResponse(
            query=request.query,
            search_type=request.search_type,
            results=formatted_results,
            total_results=len(formatted_results),
            search_time_ms=search_time_ms
        )
        
    except Exception as e:
        logger.error(f"Knowledge search failed: {e}")
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")


@router.get("/search/similar")
async def search_similar(
    query: str = Query(..., description="Search query"),
    k: int = Query(5, description="Number of results"),
    filter: Optional[str] = Query(None, description="Metadata filter as JSON string")
):
    """
    Perform vector similarity search.
    
    Returns documents similar to the query with similarity scores.
    """
    if not vector_store:
        raise HTTPException(status_code=500, detail="Vector store not initialized")
    
    try:
        import json
        
        # Parse filter
        parsed_filter = None
        if filter:
            try:
                parsed_filter = json.loads(filter)
            except json.JSONDecodeError:
                raise HTTPException(status_code=400, detail="Invalid filter JSON")
        
        # Perform search
        results = await vector_store.search_with_score(
            query=query,
            k=k,
            filter=parsed_filter
        )
        
        # Format results
        formatted_results = []
        for doc, score in results:
            formatted_results.append({
                "content": doc.page_content,
                "metadata": doc.metadata,
                "similarity_score": score
            })
        
        return {
            "query": query,
            "results": formatted_results,
            "total_results": len(formatted_results)
        }
        
    except Exception as e:
        logger.error(f"Similarity search failed: {e}")
        raise HTTPException(status_code=500, detail=f"Similarity search failed: {str(e)}")


# ========== Management Endpoints ==========

@router.get("/stats", response_model=VectorStoreStatsResponse)
async def get_vector_store_stats():
    """Get vector store statistics and configuration."""
    if not vector_store:
        raise HTTPException(status_code=500, detail="Vector store not initialized")
    
    try:
        stats = await vector_store.get_stats()
        return VectorStoreStatsResponse(**stats)
        
    except Exception as e:
        logger.error(f"Failed to get stats: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get stats: {str(e)}")


@router.get("/health")
async def health_check():
    """Perform health check on enhanced knowledge base."""
    if not enhanced_kb or not vector_store:
        raise HTTPException(status_code=500, detail="Enhanced knowledge base not initialized")
    
    try:
        # Check both components
        kb_health = await enhanced_kb.health_check()
        vs_health = await vector_store.health_check()
        
        return {
            "status": "healthy" if kb_health["status"] == "healthy" and vs_health["status"] == "healthy" else "degraded",
            "timestamp": kb_health["timestamp"],
            "components": {
                "enhanced_knowledge_base": kb_health,
                "vector_store": vs_health
            }
        }
        
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": asyncio.get_event_loop().time()
        }


@router.delete("/documents/{document_id}")
async def delete_document(document_id: str):
    """Delete a document by ID."""
    if not vector_store:
        raise HTTPException(status_code=500, detail="Vector store not initialized")
    
    try:
        success = await vector_store.delete_documents([document_id])
        
        if success:
            return {"message": f"Document {document_id} deleted successfully"}
        else:
            raise HTTPException(status_code=500, detail="Failed to delete document")
        
    except Exception as e:
        logger.error(f"Document deletion failed: {e}")
        raise HTTPException(status_code=500, detail=f"Document deletion failed: {str(e)}")


@router.get("/documents/{document_id}/metadata")
async def get_document_metadata(document_id: str):
    """Get document metadata by ID."""
    if not vector_store:
        raise HTTPException(status_code=500, detail="Vector store not initialized")
    
    try:
        metadata = await vector_store.get_document_metadata(document_id)
        
        if metadata:
            return {"document_id": document_id, "metadata": metadata}
        else:
            raise HTTPException(status_code=404, detail="Document not found")
        
    except Exception as e:
        logger.error(f"Failed to get document metadata: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get document metadata: {str(e)}")


@router.put("/documents/{document_id}/metadata")
async def update_document_metadata(
    document_id: str,
    metadata: Dict[str, Any]
):
    """Update document metadata by ID."""
    if not vector_store:
        raise HTTPException(status_code=500, detail="Vector store not initialized")
    
    try:
        success = await vector_store.update_document_metadata(document_id, metadata)
        
        if success:
            return {"message": f"Metadata updated for document {document_id}"}
        else:
            raise HTTPException(status_code=500, detail="Failed to update metadata")
        
    except Exception as e:
        logger.error(f"Failed to update document metadata: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to update document metadata: {str(e)}")
