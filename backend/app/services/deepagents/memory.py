"""
Long-term Memory System for Deep Agents

Provides persistent memory across agent sessions using Redis for:
- Context persistence
- Learning from past interactions
- Pattern recognition
- Knowledge accumulation

Based on LangChain Deep Agents memory framework.
"""

import json
import time
from typing import Dict, Any, List, Optional, Union
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict

import redis.asyncio as redis
from langchain_core.messages import BaseMessage

from app.core.logging import setup_logging
from app.core.config import settings

logger = setup_logging(__name__)


@dataclass
class MemoryEntry:
    """Individual memory entry with metadata."""
    key: str
    content: Dict[str, Any]
    timestamp: datetime
    session_id: str
    agent_id: str
    entry_type: str  # context, learning, pattern, knowledge
    importance_score: float = 0.5  # 0-1, higher = more important
    access_count: int = 0
    last_accessed: Optional[datetime] = None


class LongTermMemory:
    """
    Long-term memory system for Deep Agents.
    
    Features:
    - Persistent storage in Redis
    - Automatic TTL management
    - Importance-based retention
    - Pattern learning and recognition
    - Context-aware retrieval
    """
    
    def __init__(
        self,
        agent_id: str,
        ttl_days: int = 30,
        max_entries: int = 1000,
        redis_url: Optional[str] = None
    ):
        """
        Initialize Long-term Memory system.
        
        Args:
            agent_id: Unique agent identifier
            ttl_days: Time-to-live for memory entries in days
            max_entries: Maximum number of entries to store
            redis_url: Redis connection URL (defaults to settings)
        """
        self.agent_id = agent_id
        self.ttl_days = ttl_days
        self.max_entries = max_entries
        self.redis_url = redis_url or settings.REDIS_URL
        
        # Redis connection
        self.redis_client = None
        
        # Memory keys
        self.memory_key = f"deep_agent_memory:{agent_id}"
        self.context_key = f"deep_agent_context:{agent_id}"
        self.patterns_key = f"deep_agent_patterns:{agent_id}"
        self.learning_key = f"deep_agent_learning:{agent_id}"
        
        logger.info(f"LongTermMemory initialized: agent_id={agent_id}, ttl_days={ttl_days}")
    
    async def _get_redis_client(self) -> redis.Redis:
        """Get Redis client connection."""
        if not self.redis_client:
            self.redis_client = redis.from_url(self.redis_url, decode_responses=True)
        return self.redis_client
    
    async def save_context(
        self,
        session_id: str,
        context_data: Dict[str, Any],
        entry_type: str = "context"
    ) -> bool:
        """
        Save context data to memory.
        
        Args:
            session_id: Session identifier
            context_data: Context data to save
            entry_type: Type of memory entry
            
        Returns:
            True if saved successfully
        """
        try:
            redis_client = await self._get_redis_client()
            
            # Create memory entry
            entry = MemoryEntry(
                key=f"{session_id}:{int(time.time())}",
                content=context_data,
                timestamp=datetime.now(),
                session_id=session_id,
                agent_id=self.agent_id,
                entry_type=entry_type
            )
            
            # Calculate importance score
            entry.importance_score = self._calculate_importance_score(context_data)
            
            # Store in Redis with TTL
            entry_key = f"{self.memory_key}:{entry.key}"
            await redis_client.hset(
                entry_key,
                mapping={
                    "data": json.dumps(asdict(entry), default=str),
                    "timestamp": entry.timestamp.isoformat()
                }
            )
            
            # Set TTL
            await redis_client.expire(entry_key, self.ttl_days * 24 * 3600)
            
            # Add to session index
            session_index_key = f"{self.context_key}:{session_id}"
            await redis_client.sadd(session_index_key, entry.key)
            await redis_client.expire(session_index_key, self.ttl_days * 24 * 3600)
            
            # Cleanup old entries if needed
            await self._cleanup_old_entries()
            
            logger.debug(f"Context saved: session={session_id}, type={entry_type}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to save context: {e}", exc_info=True)
            return False
    
    async def load_context(self, session_id: str) -> Dict[str, Any]:
        """
        Load context data from memory.
        
        Args:
            session_id: Session identifier
            
        Returns:
            Loaded context data
        """
        try:
            redis_client = await self._get_redis_client()
            
            # Get session entries
            session_index_key = f"{self.context_key}:{session_id}"
            entry_keys = await redis_client.smembers(session_index_key)
            
            if not entry_keys:
                return {}
            
            # Load entries
            context_data = {}
            for entry_key in entry_keys:
                full_key = f"{self.memory_key}:{entry_key}"
                entry_data = await redis_client.hget(full_key, "data")
                
                if entry_data:
                    entry = json.loads(entry_data)
                    context_data[entry_key] = entry["content"]
                    
                    # Update access tracking
                    await self._update_access_tracking(entry_key)
            
            logger.debug(f"Context loaded: session={session_id}, entries={len(context_data)}")
            return context_data
            
        except Exception as e:
            logger.error(f"Failed to load context: {e}", exc_info=True)
            return {}
    
    async def learn_pattern(
        self,
        pattern_data: Dict[str, Any],
        pattern_type: str = "interaction"
    ) -> bool:
        """
        Learn and store patterns from agent interactions.
        
        Args:
            pattern_data: Pattern data to learn
            pattern_type: Type of pattern
            
        Returns:
            True if pattern learned successfully
        """
        try:
            redis_client = await self._get_redis_client()
            
            # Create pattern entry
            pattern_key = f"{pattern_type}:{int(time.time())}"
            pattern_entry = {
                "pattern_data": pattern_data,
                "pattern_type": pattern_type,
                "timestamp": datetime.now().isoformat(),
                "agent_id": self.agent_id,
                "confidence": pattern_data.get("confidence", 0.5)
            }
            
            # Store pattern
            await redis_client.hset(
                f"{self.patterns_key}:{pattern_key}",
                mapping=pattern_entry
            )
            
            # Set TTL
            await redis_client.expire(
                f"{self.patterns_key}:{pattern_key}",
                self.ttl_days * 24 * 3600
            )
            
            logger.debug(f"Pattern learned: type={pattern_type}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to learn pattern: {e}", exc_info=True)
            return False
    
    async def get_relevant_patterns(
        self,
        query: str,
        pattern_type: Optional[str] = None,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Get patterns relevant to a query.
        
        Args:
            query: Query to find relevant patterns
            pattern_type: Filter by pattern type
            limit: Maximum number of patterns to return
            
        Returns:
            List of relevant patterns
        """
        try:
            redis_client = await self._get_redis_client()
            
            # Get all pattern keys
            pattern_keys = await redis_client.keys(f"{self.patterns_key}:*")
            
            patterns = []
            for key in pattern_keys:
                pattern_data = await redis_client.hgetall(key)
                if pattern_data:
                    patterns.append(pattern_data)
            
            # Simple relevance scoring (in production, use vector similarity)
            scored_patterns = []
            for pattern in patterns:
                score = self._calculate_relevance_score(query, pattern)
                if score > 0.3:  # Threshold for relevance
                    scored_patterns.append((score, pattern))
            
            # Sort by relevance and return top results
            scored_patterns.sort(key=lambda x: x[0], reverse=True)
            return [pattern for score, pattern in scored_patterns[:limit]]
            
        except Exception as e:
            logger.error(f"Failed to get relevant patterns: {e}", exc_info=True)
            return []
    
    async def get_summary(self, session_id: str) -> Dict[str, Any]:
        """
        Get memory summary for a session.
        
        Args:
            session_id: Session identifier
            
        Returns:
            Memory summary
        """
        try:
            redis_client = await self._get_redis_client()
            
            # Get session entries count
            session_index_key = f"{self.context_key}:{session_id}"
            entry_count = await redis_client.scard(session_index_key)
            
            # Get patterns count
            pattern_keys = await redis_client.keys(f"{self.patterns_key}:*")
            pattern_count = len(pattern_keys)
            
            # Get learning entries count
            learning_keys = await redis_client.keys(f"{self.learning_key}:*")
            learning_count = len(learning_keys)
            
            return {
                "session_id": session_id,
                "agent_id": self.agent_id,
                "context_entries": entry_count,
                "patterns_learned": pattern_count,
                "learning_entries": learning_count,
                "memory_health": "healthy" if entry_count > 0 else "empty"
            }
            
        except Exception as e:
            logger.error(f"Failed to get memory summary: {e}", exc_info=True)
            return {"error": str(e)}
    
    async def clear_session(self, session_id: str) -> bool:
        """
        Clear memory for a specific session.
        
        Args:
            session_id: Session identifier
            
        Returns:
            True if cleared successfully
        """
        try:
            redis_client = await self._get_redis_client()
            
            # Get session entries
            session_index_key = f"{self.context_key}:{session_id}"
            entry_keys = await redis_client.smembers(session_index_key)
            
            # Delete entries
            for entry_key in entry_keys:
                full_key = f"{self.memory_key}:{entry_key}"
                await redis_client.delete(full_key)
            
            # Delete session index
            await redis_client.delete(session_index_key)
            
            logger.info(f"Session cleared: {session_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to clear session: {e}", exc_info=True)
            return False
    
    def _calculate_importance_score(self, context_data: Dict[str, Any]) -> float:
        """Calculate importance score for context data."""
        score = 0.5  # Base score
        
        # Increase score based on data richness
        if "insights" in context_data:
            score += 0.2
        if "recommendations" in context_data:
            score += 0.2
        if "confidence_score" in context_data:
            score += context_data["confidence_score"] * 0.1
        
        return min(score, 1.0)
    
    def _calculate_relevance_score(self, query: str, pattern: Dict[str, Any]) -> float:
        """Calculate relevance score for pattern matching."""
        # Simple keyword matching (in production, use vector similarity)
        query_lower = query.lower()
        pattern_text = str(pattern.get("pattern_data", "")).lower()
        
        # Count matching words
        query_words = set(query_lower.split())
        pattern_words = set(pattern_text.split())
        matches = len(query_words.intersection(pattern_words))
        
        return matches / max(len(query_words), 1)
    
    async def _update_access_tracking(self, entry_key: str) -> None:
        """Update access tracking for memory entries."""
        try:
            redis_client = await self._get_redis_client()
            full_key = f"{self.memory_key}:{entry_key}"
            
            # Increment access count
            await redis_client.hincrby(full_key, "access_count", 1)
            
            # Update last accessed
            await redis_client.hset(full_key, "last_accessed", datetime.now().isoformat())
            
        except Exception as e:
            logger.warning(f"Failed to update access tracking: {e}")
    
    async def _cleanup_old_entries(self) -> None:
        """Clean up old entries to maintain memory limits."""
        try:
            redis_client = await self._get_redis_client()
            
            # Get all memory entries
            memory_keys = await redis_client.keys(f"{self.memory_key}:*")
            
            if len(memory_keys) <= self.max_entries:
                return
            
            # Get entries with metadata
            entries_with_metadata = []
            for key in memory_keys:
                entry_data = await redis_client.hget(key, "data")
                if entry_data:
                    entry = json.loads(entry_data)
                    entries_with_metadata.append((key, entry))
            
            # Sort by importance and access count
            entries_with_metadata.sort(
                key=lambda x: (
                    x[1].get("importance_score", 0.5),
                    x[1].get("access_count", 0)
                ),
                reverse=True
            )
            
            # Keep top entries, delete the rest
            entries_to_keep = entries_with_metadata[:self.max_entries]
            entries_to_delete = entries_with_metadata[self.max_entries:]
            
            for key, _ in entries_to_delete:
                await redis_client.delete(key)
            
            logger.info(f"Memory cleanup: kept {len(entries_to_keep)}, deleted {len(entries_to_delete)}")
            
        except Exception as e:
            logger.error(f"Failed to cleanup old entries: {e}", exc_info=True)
    
    async def health_check(self) -> Dict[str, Any]:
        """Perform health check on memory system."""
        try:
            redis_client = await self._get_redis_client()
            
            # Test Redis connection
            await redis_client.ping()
            
            # Check memory usage
            memory_info = await redis_client.memory_usage(self.memory_key)
            
            return {
                "status": "healthy",
                "redis_connected": True,
                "memory_usage_bytes": memory_info,
                "agent_id": self.agent_id
            }
            
        except Exception as e:
            return {
                "status": "unhealthy",
                "redis_connected": False,
                "error": str(e),
                "agent_id": self.agent_id
            }
