"""
Document processing API endpoints
"""
from fastapi import APIRouter, Depends, HTTPException, File, UploadFile, Body
from sqlalchemy.orm import Session
from typing import Optional, List
from pydantic import BaseModel

from app.models import get_db
from app.services.document_processor import DocumentProcessor
from app.services.document_analyzer import DocumentAnalyzer
from app.core.logging import setup_logging
from app.core.exceptions import UnsupportedDocumentTypeError, DocumentTooLargeError

logger = setup_logging(__name__)

router = APIRouter(prefix="/documents", tags=["documents"])

# Initialize services
document_processor = DocumentProcessor()
document_analyzer = DocumentAnalyzer()


# Request/Response models
class QuestionRequest(BaseModel):
    question: str
    relevant_pages: Optional[List[int]] = None


class SearchRequest(BaseModel):
    query: str
    max_results: Optional[int] = 5
    highlight: Optional[bool] = True


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
        raise UnsupportedDocumentTypeError(
            f"Unsupported file type: .{file_ext}. Allowed: {', '.join(allowed_extensions)}",
            context={"file_extension": file_ext, "allowed": allowed_extensions}
        )

    # Check file size (max 10MB)
    MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
    content = await file.read()
    
    if len(content) > MAX_FILE_SIZE:
        raise DocumentTooLargeError(
            f"File too large. Maximum size: 10MB, got: {len(content) / 1024 / 1024:.2f}MB",
            context={"file_size_mb": len(content) / 1024 / 1024, "max_size_mb": 10}
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


@router.post("/analyze-with-gist")
async def analyze_document_with_gist_memory(
    file: UploadFile = File(...),
    extract_keys: bool = True,
    create_summary: bool = True,
    db: Session = Depends(get_db)
):
    """
    Analyze document using Cerebras gist memory pattern

    Advanced document analysis using the gist memory pattern for efficient
    processing of long documents. Provides:
    - Intelligent document pagination
    - Page-level gist summaries
    - Comprehensive document summary
    - Structured key item extraction (entities, dates, actions, topics)
    - Document statistics and compression ratio

    **Supported Formats**: PDF, DOCX, TXT

    **Parameters**:
    - `file`: Document file upload
    - `extract_keys`: Extract key items (entities, dates, etc.)
    - `create_summary`: Generate comprehensive summary

    **Returns**:
    - Document summary
    - Extracted key items (people, organizations, dates, phrases, actions, topics)
    - Page gists for each document section
    - Processing statistics (pages, compression ratio, processing time)
    """
    # Validate file type
    allowed_extensions = ['pdf', 'docx', 'doc', 'txt']
    file_ext = file.filename.lower().split('.')[-1]

    if file_ext not in allowed_extensions:
        raise UnsupportedDocumentTypeError(
            f"Unsupported file type: .{file_ext}. Allowed: {', '.join(allowed_extensions)}",
            context={"file_extension": file_ext, "allowed": allowed_extensions}
        )

    # Check file size (max 20MB for gist memory processing)
    MAX_FILE_SIZE = 20 * 1024 * 1024  # 20MB
    content = await file.read()

    if len(content) > MAX_FILE_SIZE:
        raise DocumentTooLargeError(
            f"File too large. Maximum size: 20MB, got: {len(content) / 1024 / 1024:.2f}MB",
            context={"file_size_mb": len(content) / 1024 / 1024, "max_size_mb": 20}
        )

    # Analyze with gist memory
    try:
        result = document_analyzer.analyze_document(
            filename=file.filename,
            file_content=content,
            extract_keys=extract_keys,
            create_summary=create_summary
        )

        if not result['success']:
            raise HTTPException(
                status_code=500,
                detail=result.get('error', 'Analysis failed')
            )

        logger.info(f"Document analyzed with gist memory: {file.filename} ({result['pages']} pages) in {result['total_processing_time_ms']}ms")

        return {
            "message": "Document analyzed successfully with gist memory",
            **result
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Gist memory analysis error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Gist memory analysis failed: {str(e)}"
        )


@router.post("/search")
async def search_document(
    search_request: SearchRequest,
    db: Session = Depends(get_db)
):
    """
    Search within the most recently analyzed document

    Uses the gist memory system to search across document pages with
    optional highlighting of query terms.

    **Parameters**:
    - `query`: Search query string
    - `max_results`: Maximum number of results (default: 5)
    - `highlight`: Whether to highlight query terms (default: true)

    **Returns**:
    - List of matching pages with:
      - Page number
      - Relevance score
      - Page gist (summary)
      - Text snippet
      - Highlighted snippet (if highlight=true)

    **Note**: This searches the last document analyzed with `/analyze-with-gist`.
    For persistent search, document should be stored in database.
    """
    try:
        results = document_analyzer.search_document(
            query=search_request.query,
            max_results=search_request.max_results,
            highlight=search_request.highlight
        )

        return {
            "message": f"Found {len(results)} matching pages",
            "query": search_request.query,
            "results": results
        }

    except Exception as e:
        logger.error(f"Document search error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Document search failed: {str(e)}"
        )


@router.post("/question")
async def answer_question(
    question_request: QuestionRequest,
    db: Session = Depends(get_db)
):
    """
    Answer a question about the most recently analyzed document

    Uses gist memory to intelligently identify relevant document sections
    and generate an answer using Cerebras AI.

    **Parameters**:
    - `question`: Question to answer about the document
    - `relevant_pages`: Optional specific pages to use (auto-detected if not provided)

    **Returns**:
    - Answer to the question
    - Relevant pages used
    - Processing time
    - Number of pages consulted

    **Note**: This answers questions about the last document analyzed with `/analyze-with-gist`.
    """
    try:
        result = document_analyzer.answer_question(
            question=question_request.question,
            relevant_pages=question_request.relevant_pages
        )

        return {
            "message": "Question answered successfully",
            "question": question_request.question,
            **result
        }

    except Exception as e:
        logger.error(f"Question answering error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Question answering failed: {str(e)}"
        )


@router.get("/stats")
async def get_document_stats(db: Session = Depends(get_db)):
    """
    Get statistics about the currently loaded document

    Returns comprehensive statistics including:
    - Total pages
    - Total words and gist words
    - Compression ratio
    - Average page word count
    - Page-level metadata

    **Note**: Returns stats for the last document analyzed with `/analyze-with-gist`.
    """
    try:
        stats = document_analyzer.get_document_stats()

        if 'error' in stats:
            raise HTTPException(
                status_code=404,
                detail=stats['error']
            )

        return {
            "message": "Document statistics retrieved",
            **stats
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Stats retrieval error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve document stats: {str(e)}"
        )


@router.get("/page/{page_num}")
async def get_page_content(
    page_num: int,
    db: Session = Depends(get_db)
):
    """
    Get full text content of a specific page

    **Parameters**:
    - `page_num`: Page number (1-indexed)

    **Returns**:
    - Full text content of the requested page

    **Note**: Retrieves page from the last document analyzed with `/analyze-with-gist`.
    """
    try:
        content = document_analyzer.get_page_content(page_num)

        if content is None:
            raise HTTPException(
                status_code=404,
                detail=f"Page {page_num} not found or no document loaded"
            )

        return {
            "message": f"Page {page_num} retrieved",
            "page_num": page_num,
            "content": content,
            "word_count": len(content.split())
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Page retrieval error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve page: {str(e)}"
        )
