"""
Document processing API endpoints
"""
from fastapi import APIRouter, Depends, HTTPException, File, UploadFile
from sqlalchemy.orm import Session
from typing import Optional

from app.models import get_db
from app.services.document_processor import DocumentProcessor
from app.core.logging import setup_logging

logger = setup_logging(__name__)

router = APIRouter(prefix="/api/documents", tags=["documents"])

# Initialize document processor
document_processor = DocumentProcessor()


@router.post("/analyze")
async def analyze_document(
    file: UploadFile = File(...),
    document_type: str = "resume",
    job_description: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    Analyze document with AI-powered extraction and matching

    **Supported Formats**:
    - PDF (.pdf) - Best text extraction with pdfplumber
    - DOCX (.docx) - Microsoft Word documents
    - TXT (.txt) - Plain text files

    **Document Types**:
    - `resume` - Extract skills, experience, education, contact info
    - `generic` - Basic text extraction and summary

    **Resume Analysis Features**:
    - Contact information extraction (name, email, phone, LinkedIn)
    - Skills identification
    - Years of experience calculation
    - Education history
    - Work experience summary
    - Job fit scoring (if job_description provided)

    **Parameters**:
    - `file`: Document file upload
    - `document_type`: Type of document (default: "resume")
    - `job_description`: Optional job description for resume matching

    **Returns**:
    - Extracted text preview
    - AI-powered analysis
    - Processing statistics
    """
    # Validate file type
    allowed_extensions = ['pdf', 'docx', 'doc', 'txt']
    file_ext = file.filename.lower().split('.')[-1]
    
    if file_ext not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: .{file_ext}. Allowed: {', '.join(allowed_extensions)}"
        )

    # Check file size (max 10MB)
    MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
    content = await file.read()
    
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"File too large. Maximum size: 10MB, got: {len(content) / 1024 / 1024:.2f}MB"
        )

    # Process document
    try:
        result = document_processor.process_document(
            filename=file.filename,
            file_content=content,
            document_type=document_type,
            job_description=job_description
        )

        logger.info(f"Document analyzed: {file.filename} ({len(content)} bytes) in {result['processing_duration_ms']}ms")
        
        return {
            "message": "Document analyzed successfully",
            **result
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Document processing error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Document processing failed: {str(e)}"
        )


@router.post("/extract-text")
async def extract_text_only(
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """
    Extract raw text from document without AI analysis

    Faster endpoint for simple text extraction without AI overhead.

    **Supported Formats**: PDF, DOCX, TXT

    **Returns**:
    - Extracted text content
    - Character count
    - Word count
    """
    # Validate file type
    allowed_extensions = ['pdf', 'docx', 'doc', 'txt']
    file_ext = file.filename.lower().split('.')[-1]
    
    if file_ext not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: .{file_ext}"
        )

    # Read file
    content = await file.read()

    # Extract text only
    try:
        text = document_processor.extract_text(file.filename, content)
        
        return {
            "filename": file.filename,
            "text": text,
            "char_count": len(text),
            "word_count": len(text.split()),
            "line_count": len(text.split('\n'))
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Text extraction error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Text extraction failed: {str(e)}"
        )
