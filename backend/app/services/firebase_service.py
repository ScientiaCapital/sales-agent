"""
Firebase service for multi-tenant customer platform

Provides Firebase Authentication and Firestore integration for customer isolation
"""
import os
import json
import firebase_admin
from firebase_admin import credentials, auth, firestore, storage
from typing import Dict, Optional, List
from datetime import datetime

from app.core.logging import setup_logging

logger = setup_logging(__name__)


class FirebaseService:
    """
    Service for Firebase Authentication, Firestore, and Storage operations
    
    Handles:
    - Customer authentication and session management
    - Document storage in Firestore
    - File uploads to Firebase Storage
    - Multi-tenant data isolation
    """
    
    _instance = None
    _initialized = False
    
    def __new__(cls):
        """Singleton pattern for Firebase service"""
        if cls._instance is None:
            cls._instance = super(FirebaseService, cls).__new__(cls)
        return cls._instance
    
    def __init__(self):
        """Initialize Firebase Admin SDK"""
        if not self._initialized:
            self._initialize_firebase()
            FirebaseService._initialized = True
    
    def _initialize_firebase(self):
        """Initialize Firebase Admin SDK with service account credentials"""
        try:
            # Check if already initialized
            if firebase_admin._apps:
                logger.info("Firebase already initialized")
                return
            
            # Get Firebase credentials from environment
            firebase_creds_path = os.getenv("FIREBASE_SERVICE_ACCOUNT_PATH")
            firebase_creds_json = os.getenv("FIREBASE_SERVICE_ACCOUNT_JSON")
            
            if firebase_creds_path and os.path.exists(firebase_creds_path):
                # Initialize from file path
                cred = credentials.Certificate(firebase_creds_path)
                logger.info(f"Initializing Firebase from file: {firebase_creds_path}")
            elif firebase_creds_json:
                # Initialize from JSON string (for cloud deployments)
                cred_dict = json.loads(firebase_creds_json)
                cred = credentials.Certificate(cred_dict)
                logger.info("Initializing Firebase from JSON environment variable")
            else:
                # Try default application credentials (for GCP environments)
                cred = credentials.ApplicationDefault()
                logger.info("Initializing Firebase with default application credentials")
            
            # Initialize Firebase app
            firebase_admin.initialize_app(cred, {
                'storageBucket': os.getenv("FIREBASE_STORAGE_BUCKET"),
                'databaseURL': os.getenv("FIREBASE_DATABASE_URL")
            })
            
            # Initialize Firestore client
            self.db = firestore.client()
            
            # Initialize Storage bucket
            self.bucket = storage.bucket()
            
            logger.info("Firebase initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize Firebase: {e}", exc_info=True)
            raise
    
    # === Authentication Methods ===
    
    def create_custom_token(self, uid: str, claims: Optional[Dict] = None) -> str:
        """
        Create a custom Firebase authentication token
        
        Args:
            uid: User ID
            claims: Optional custom claims for the token
        
        Returns:
            Custom token string
        """
        try:
            token = auth.create_custom_token(uid, claims)
            logger.info(f"Created custom token for user: {uid}")
            return token.decode('utf-8') if isinstance(token, bytes) else token
        except Exception as e:
            logger.error(f"Failed to create custom token for {uid}: {e}")
            raise
    
    def verify_id_token(self, id_token: str, check_revoked: bool = False) -> Dict:
        """
        Verify a Firebase ID token
        
        Args:
            id_token: Firebase ID token to verify
            check_revoked: Whether to check if token has been revoked
        
        Returns:
            Decoded token containing user claims
        """
        try:
            decoded_token = auth.verify_id_token(id_token, check_revoked=check_revoked)
            return decoded_token
        except Exception as e:
            logger.error(f"Failed to verify ID token: {e}")
            raise
    
    def get_user(self, uid: str) -> auth.UserRecord:
        """
        Get Firebase user by UID
        
        Args:
            uid: User ID
        
        Returns:
            UserRecord object
        """
        try:
            user = auth.get_user(uid)
            return user
        except Exception as e:
            logger.error(f"Failed to get user {uid}: {e}")
            raise
    
    def create_user(
        self,
        email: str,
        password: Optional[str] = None,
        display_name: Optional[str] = None,
        **kwargs
    ) -> auth.UserRecord:
        """
        Create a new Firebase user
        
        Args:
            email: User email
            password: User password (optional)
            display_name: User display name (optional)
            **kwargs: Additional user properties
        
        Returns:
            Created UserRecord
        """
        try:
            user = auth.create_user(
                email=email,
                password=password,
                display_name=display_name,
                **kwargs
            )
            logger.info(f"Created user: {user.uid} ({email})")
            return user
        except Exception as e:
            logger.error(f"Failed to create user {email}: {e}")
            raise
    
    def set_custom_user_claims(self, uid: str, claims: Dict):
        """
        Set custom claims for a user (for role-based access control)
        
        Args:
            uid: User ID
            claims: Dictionary of custom claims
        """
        try:
            auth.set_custom_user_claims(uid, claims)
            logger.info(f"Set custom claims for user {uid}: {claims}")
        except Exception as e:
            logger.error(f"Failed to set custom claims for {uid}: {e}")
            raise
    
    # === Firestore Document Methods ===
    
    def create_document(
        self,
        collection: str,
        document_id: Optional[str] = None,
        data: Dict = None
    ) -> str:
        """
        Create a Firestore document
        
        Args:
            collection: Collection name
            document_id: Optional document ID (auto-generated if not provided)
            data: Document data
        
        Returns:
            Document ID
        """
        try:
            if document_id:
                doc_ref = self.db.collection(collection).document(document_id)
                doc_ref.set(data)
            else:
                _, doc_ref = self.db.collection(collection).add(data)
                document_id = doc_ref.id
            
            logger.info(f"Created document in {collection}: {document_id}")
            return document_id
        except Exception as e:
            logger.error(f"Failed to create document in {collection}: {e}")
            raise
    
    def get_document(self, collection: str, document_id: str) -> Optional[Dict]:
        """
        Get a Firestore document
        
        Args:
            collection: Collection name
            document_id: Document ID
        
        Returns:
            Document data or None if not found
        """
        try:
            doc_ref = self.db.collection(collection).document(document_id)
            doc = doc_ref.get()
            
            if doc.exists:
                return doc.to_dict()
            return None
        except Exception as e:
            logger.error(f"Failed to get document {collection}/{document_id}: {e}")
            raise
    
    def update_document(self, collection: str, document_id: str, data: Dict):
        """
        Update a Firestore document
        
        Args:
            collection: Collection name
            document_id: Document ID
            data: Updated fields
        """
        try:
            doc_ref = self.db.collection(collection).document(document_id)
            doc_ref.update(data)
            logger.info(f"Updated document {collection}/{document_id}")
        except Exception as e:
            logger.error(f"Failed to update document {collection}/{document_id}: {e}")
            raise
    
    def delete_document(self, collection: str, document_id: str):
        """
        Delete a Firestore document
        
        Args:
            collection: Collection name
            document_id: Document ID
        """
        try:
            self.db.collection(collection).document(document_id).delete()
            logger.info(f"Deleted document {collection}/{document_id}")
        except Exception as e:
            logger.error(f"Failed to delete document {collection}/{document_id}: {e}")
            raise
    
    def query_documents(
        self,
        collection: str,
        filters: Optional[List[tuple]] = None,
        order_by: Optional[str] = None,
        limit: Optional[int] = None
    ) -> List[Dict]:
        """
        Query Firestore documents
        
        Args:
            collection: Collection name
            filters: List of (field, operator, value) tuples
            order_by: Field to order by
            limit: Maximum number of documents
        
        Returns:
            List of document data dictionaries
        """
        try:
            query = self.db.collection(collection)
            
            # Apply filters
            if filters:
                for field, operator, value in filters:
                    query = query.where(field, operator, value)
            
            # Apply ordering
            if order_by:
                query = query.order_by(order_by)
            
            # Apply limit
            if limit:
                query = query.limit(limit)
            
            docs = query.stream()
            results = [doc.to_dict() for doc in docs]
            
            logger.info(f"Queried {collection}, found {len(results)} documents")
            return results
        except Exception as e:
            logger.error(f"Failed to query {collection}: {e}")
            raise
    
    # === Firebase Storage Methods ===
    
    def upload_file(
        self,
        file_path: str,
        destination_path: str,
        content_type: Optional[str] = None
    ) -> str:
        """
        Upload a file to Firebase Storage
        
        Args:
            file_path: Local file path
            destination_path: Destination path in Firebase Storage
            content_type: Optional MIME type
        
        Returns:
            Public URL of uploaded file
        """
        try:
            blob = self.bucket.blob(destination_path)
            
            if content_type:
                blob.upload_from_filename(file_path, content_type=content_type)
            else:
                blob.upload_from_filename(file_path)
            
            # Make blob publicly accessible (optional)
            # blob.make_public()
            
            logger.info(f"Uploaded file to {destination_path}")
            return blob.public_url
        except Exception as e:
            logger.error(f"Failed to upload file to {destination_path}: {e}")
            raise
    
    def upload_bytes(
        self,
        data: bytes,
        destination_path: str,
        content_type: Optional[str] = None
    ) -> str:
        """
        Upload bytes to Firebase Storage
        
        Args:
            data: Bytes to upload
            destination_path: Destination path in Firebase Storage
            content_type: Optional MIME type
        
        Returns:
            Public URL of uploaded file
        """
        try:
            blob = self.bucket.blob(destination_path)
            blob.upload_from_string(data, content_type=content_type)
            
            logger.info(f"Uploaded bytes to {destination_path}")
            return blob.public_url
        except Exception as e:
            logger.error(f"Failed to upload bytes to {destination_path}: {e}")
            raise
    
    def download_file(self, source_path: str, destination_path: str):
        """
        Download a file from Firebase Storage
        
        Args:
            source_path: Path in Firebase Storage
            destination_path: Local destination path
        """
        try:
            blob = self.bucket.blob(source_path)
            blob.download_to_filename(destination_path)
            logger.info(f"Downloaded file from {source_path}")
        except Exception as e:
            logger.error(f"Failed to download file from {source_path}: {e}")
            raise
    
    def delete_file(self, file_path: str):
        """
        Delete a file from Firebase Storage
        
        Args:
            file_path: Path in Firebase Storage
        """
        try:
            blob = self.bucket.blob(file_path)
            blob.delete()
            logger.info(f"Deleted file {file_path}")
        except Exception as e:
            logger.error(f"Failed to delete file {file_path}: {e}")
            raise
