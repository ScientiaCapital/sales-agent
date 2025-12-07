"""
Knowledge Base API endpoints for document management
"""
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session
from typing import List, Optional

from app.models import get_db
from app.schemas.customer import (
    DocumentUploadResponse,
    DocumentSearchRequest,
    DocumentSearchResult,
    DocumentListResponse
)
from app.services.knowledge_base import KnowledgeBaseService
from app.core.logging import setup_logging

logger = setup_logging(__name__)

router = APIRouter(prefix="/knowledge", tags=["knowledge"])

# Initialize Knowledge Base service
knowledge_service = KnowledgeBaseService()


@router.post("/upload", response_model=DocumentUploadResponse, status_code=201)
async def upload_document(
    customer_id: str = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """
    Upload a document to customer knowledge base
    
    This endpoint:
    1. Accepts PDF, DOCX, or TXT files
    2. Uploads to Firebase Storage
    3. Extracts text content
    4. Generates vector embeddings
    5. Extracts ICP (Ideal Customer Profile) criteria
    6. Stores metadata in Firestore
    
    Returns document metadata and ICP criteria.
    """
    try:
        # Validate file type
        allowed_types = {
            'application/pdf',
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            'application/msword',
            'text/plain'
        }
        
        if file.content_type not in allowed_types:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file type: {file.content_type}. "
                       "Supported types: PDF, DOCX, TXT"
            )
        
        # Read file content
        file_content = await file.read()
        
        # Validate file size (max 50MB)
        max_size = 50 * 1024 * 1024  # 50MB
        if len(file_content) > max_size:
            raise HTTPException(
                status_code=400,
                detail=f"File too large ({len(file_content)} bytes). Maximum size: 50MB"
            )
        
        logger.info(f"Uploading document: {file.filename} for customer {customer_id}")
        
        # Upload and process document
        result = knowledge_service.upload_document(
            file_content=file_content,
            filename=file.filename,
            customer_id=customer_id,
            content_type=file.content_type,
            db=db
        )
        
        logger.info(f"Document uploaded successfully: {result['document_id']}")
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to upload document: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Document upload failed: {str(e)}"
        )


@router.post("/search", response_model=List[DocumentSearchResult])
async def search_documents(
    customer_id: str,
    request: DocumentSearchRequest,
    db: Session = Depends(get_db)
):
    """
    Search for similar documents using vector similarity
    
    This endpoint:
    1. Generates embedding for the search query
    2. Performs vector similarity search
    3. Returns documents with similarity scores
    
    Useful for finding relevant ICP examples and market insights.
    """
    try:
        logger.info(f"Searching documents for customer {customer_id}: query='{request.query[:50]}'")
        
        results = knowledge_service.search_similar_documents(
            query_text=request.query,
            customer_id=customer_id,
            limit=request.limit,
            similarity_threshold=request.similarity_threshold
        )
        
        logger.info(f"Found {len(results)} similar documents")
        
        return results
        
    except Exception as e:
        logger.error(f"Failed to search documents: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Document search failed: {str(e)}"
        )


@router.get("/docs/{customer_id}", response_model=List[DocumentListResponse])
async def get_customer_documents(
    customer_id: str,
    limit: Optional[int] = 50,
    db: Session = Depends(get_db)
):
    """
    Get all documents for a customer
    
    Returns a list of document metadata with:
    - Document IDs and filenames
    - ICP criteria extracted from each document
    - Processing status
    - Creation timestamps
    
    Use this to display the customer's knowledge base library.
    """
    try:
        logger.info(f"Retrieving documents for customer {customer_id}")
        
        documents = knowledge_service.get_customer_documents(
            customer_id=customer_id,
            limit=limit
        )
        
        logger.info(f"Retrieved {len(documents)} documents")
        
        # Convert Firestore documents to API response format
        response = []
        for doc in documents:
            response.append({
                'document_id': doc.get('document_id'),
                'customer_id': int(customer_id),
                'filename': doc.get('filename'),
                'content_type': doc.get('content_type'),
                'file_size': None,  # Retrieved separately
                'runpod_url': doc.get('file_url'),
                'text_length': doc.get('text_length'),
                'icp_data': doc.get('icp_criteria'),
                'processing_status': 'completed',
                'created_at': doc.get('created_at')
            })
        
        return response
        
    except Exception as e:
        logger.error(f"Failed to retrieve documents: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve documents: {str(e)}"
        )


@router.delete("/docs/{customer_id}/{document_id}", status_code=204)
async def delete_document(
    customer_id: str,
    document_id: str,
    db: Session = Depends(get_db)
):
    """
    Delete a customer document
    
    This endpoint:
    1. Verifies customer ownership
    2. Deletes from Firebase Storage
    3. Removes from Firestore
    4. Updates customer quotas
    
    Returns 204 No Content on success.
    """
    try:
        logger.info(f"Deleting document {document_id} for customer {customer_id}")
        
        knowledge_service.delete_document(
            document_id=document_id,
            customer_id=customer_id
        )
        
        logger.info(f"Document {document_id} deleted successfully")
        
        return None
        
    except PermissionError as e:
        logger.warning(f"Permission denied: {e}")
        raise HTTPException(status_code=403, detail=str(e))
    
    except ValueError as e:
        logger.warning(f"Document not found: {e}")
        raise HTTPException(status_code=404, detail=str(e))
    
    except Exception as e:
        logger.error(f"Failed to delete document: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete document: {str(e)}"
        )
