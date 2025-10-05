"""
Comprehensive tests for Redis Cache Manager

Tests cover:
- Cache hit/miss scenarios
- TTL expiration behavior
- Cache invalidation
- Fallback when Redis unavailable
- Key generation consistency
- Statistics tracking
"""

import pytest
import asyncio
from datetime import timedelta
from unittest.mock import AsyncMock, patch, MagicMock
from app.services.cache_manager import CacheManager


class TestCacheManager:
    """Test suite for CacheManager"""
    
    @pytest.fixture
    async def cache_manager(self):
        """Create cache manager instance for testing"""
        manager = CacheManager(redis_url="redis://localhost:6379/1")  # Use DB 1 for tests
        yield manager
        # Cleanup after tests
        await manager.close()
    
    @pytest.fixture
    async def mock_redis(self):
        """Create mock Redis client"""
        mock = AsyncMock()
        mock.ping = AsyncMock(return_value=True)
        mock.get = AsyncMock(return_value=None)
        mock.setex = AsyncMock()
        mock.delete = AsyncMock(return_value=1)
        mock.incr = AsyncMock()
        return mock


class TestKeyGeneration:
    """Test cache key generation"""
    
    def test_key_generation_consistency(self):
        """Test that same inputs produce same keys"""
        manager = CacheManager()
        
        key1 = manager._generate_key("test", company="TechCorp", industry="SaaS")
        key2 = manager._generate_key("test", company="TechCorp", industry="SaaS")
        
        assert key1 == key2
    
    def test_key_generation_case_insensitive(self):
        """Test that case variations produce same key"""
        manager = CacheManager()
        
        key1 = manager._generate_key("test", company="TechCorp", industry="SaaS")
        key2 = manager._generate_key("test", company="techcorp", industry="saas")
        
        assert key1 == key2
    
    def test_key_generation_different_values(self):
        """Test that different inputs produce different keys"""
        manager = CacheManager()
        
        key1 = manager._generate_key("test", company="TechCorp", industry="SaaS")
        key2 = manager._generate_key("test", company="DataCorp", industry="SaaS")
        
        assert key1 != key2
    
    def test_key_generation_none_handling(self):
        """Test that None values are handled consistently"""
        manager = CacheManager()
        
        key1 = manager._generate_key("test", company="TechCorp", industry=None)
        key2 = manager._generate_key("test", company="TechCorp", industry="")
        
        # None and empty string should produce same key
        assert key1 == key2
    
    def test_key_format(self):
        """Test key format includes prefix and hash"""
        manager = CacheManager()
        
        key = manager._generate_key("lead_qual", company="TechCorp", industry="SaaS")
        
        assert key.startswith("lead_qual:")
        assert len(key) == len("lead_qual:") + 32  # MD5 hash is 32 chars


class TestTTLGeneration:
    """Test TTL with jitter"""
    
    def test_ttl_jitter_range(self):
        """Test TTL jitter stays within expected range"""
        manager = CacheManager()
        base_ttl = timedelta(hours=24)
        base_seconds = 86400
        
        # Generate multiple TTLs to test randomness
        ttls = [manager._get_ttl_with_jitter(base_ttl) for _ in range(100)]
        
        # All should be within ±12.5% (75600 to 97200 seconds)
        min_expected = base_seconds - int(base_seconds * 0.125)
        max_expected = base_seconds + int(base_seconds * 0.125)
        
        assert all(min_expected <= ttl <= max_expected for ttl in ttls)
    
    def test_ttl_jitter_randomness(self):
        """Test that TTL jitter produces different values"""
        manager = CacheManager()
        base_ttl = timedelta(hours=24)
        
        ttls = set([manager._get_ttl_with_jitter(base_ttl) for _ in range(50)])
        
        # Should have some variation (not all identical)
        assert len(ttls) > 1


@pytest.mark.asyncio
class TestCacheOperations:
    """Test cache CRUD operations"""
    
    async def test_cache_miss(self, cache_manager):
        """Test cache miss returns None"""
        # Clear any existing cache
        await cache_manager.clear_all_qualifications()
        
        result = await cache_manager.get_cached_qualification(
            company_name="NonExistentCorp",
            industry="Test"
        )
        
        assert result is None
    
    async def test_cache_hit(self, cache_manager):
        """Test cache hit returns stored data"""
        # Store data
        test_data = {
            "score": 85.5,
            "reasoning": "High quality lead",
            "latency_ms": 945,
            "model": "llama3.1-8b"
        }
        
        await cache_manager.cache_qualification(
            company_name="TechCorp",
            industry="SaaS",
            qualification_data=test_data
        )
        
        # Retrieve data
        result = await cache_manager.get_cached_qualification(
            company_name="TechCorp",
            industry="SaaS"
        )
        
        assert result is not None
        assert result["score"] == 85.5
        assert result["reasoning"] == "High quality lead"
        assert result["model"] == "llama3.1-8b"
    
    async def test_cache_different_industries(self, cache_manager):
        """Test same company with different industries are cached separately"""
        data1 = {"score": 80, "reasoning": "SaaS lead"}
        data2 = {"score": 60, "reasoning": "Healthcare lead"}
        
        await cache_manager.cache_qualification(
            company_name="TechCorp",
            industry="SaaS",
            qualification_data=data1
        )
        
        await cache_manager.cache_qualification(
            company_name="TechCorp",
            industry="Healthcare",
            qualification_data=data2
        )
        
        result1 = await cache_manager.get_cached_qualification(
            company_name="TechCorp",
            industry="SaaS"
        )
        
        result2 = await cache_manager.get_cached_qualification(
            company_name="TechCorp",
            industry="Healthcare"
        )
        
        assert result1["score"] == 80
        assert result2["score"] == 60
    
    async def test_cache_invalidation(self, cache_manager):
        """Test cache invalidation removes data"""
        # Store data
        test_data = {"score": 85, "reasoning": "Test"}
        
        await cache_manager.cache_qualification(
            company_name="TechCorp",
            industry="SaaS",
            qualification_data=test_data
        )
        
        # Verify it's cached
        result = await cache_manager.get_cached_qualification(
            company_name="TechCorp",
            industry="SaaS"
        )
        assert result is not None
        
        # Invalidate
        invalidated = await cache_manager.invalidate_lead_cache(
            company_name="TechCorp",
            industry="SaaS"
        )
        assert invalidated is True
        
        # Verify it's gone
        result = await cache_manager.get_cached_qualification(
            company_name="TechCorp",
            industry="SaaS"
        )
        assert result is None
    
    async def test_clear_all_qualifications(self, cache_manager):
        """Test clearing all qualification cache"""
        # Store multiple items
        for i in range(5):
            await cache_manager.cache_qualification(
                company_name=f"Company{i}",
                industry="SaaS",
                qualification_data={"score": i * 10, "reasoning": f"Test {i}"}
            )
        
        # Clear all
        deleted_count = await cache_manager.clear_all_qualifications()
        
        assert deleted_count >= 5
        
        # Verify all are gone
        for i in range(5):
            result = await cache_manager.get_cached_qualification(
                company_name=f"Company{i}",
                industry="SaaS"
            )
            assert result is None


@pytest.mark.asyncio
class TestCacheStatistics:
    """Test cache statistics tracking"""
    
    async def test_hit_stat_increment(self, cache_manager):
        """Test cache hit increments hit counter"""
        # Clear stats
        redis = await cache_manager._get_redis()
        await redis.delete("cache:stats:hits", "cache:stats:misses", "cache:stats:errors")
        
        # Store data
        await cache_manager.cache_qualification(
            company_name="TestCorp",
            industry="SaaS",
            qualification_data={"score": 80, "reasoning": "Test"}
        )
        
        # Hit the cache
        await cache_manager.get_cached_qualification(
            company_name="TestCorp",
            industry="SaaS"
        )
        
        stats = await cache_manager.get_cache_stats()
        assert stats["hits"] >= 1
    
    async def test_miss_stat_increment(self, cache_manager):
        """Test cache miss increments miss counter"""
        # Clear stats
        redis = await cache_manager._get_redis()
        await redis.delete("cache:stats:hits", "cache:stats:misses", "cache:stats:errors")
        
        # Miss the cache
        await cache_manager.get_cached_qualification(
            company_name="NonExistent",
            industry="Test"
        )
        
        stats = await cache_manager.get_cache_stats()
        assert stats["misses"] >= 1
    
    async def test_hit_rate_calculation(self, cache_manager):
        """Test hit rate percentage calculation"""
        # Clear stats
        redis = await cache_manager._get_redis()
        await redis.delete("cache:stats:hits", "cache:stats:misses", "cache:stats:errors")
        
        # Create 1 hit and 1 miss (50% hit rate)
        await cache_manager.cache_qualification(
            company_name="HitCorp",
            industry="SaaS",
            qualification_data={"score": 80, "reasoning": "Test"}
        )
        
        # 1 hit
        await cache_manager.get_cached_qualification(
            company_name="HitCorp",
            industry="SaaS"
        )
        
        # 1 miss
        await cache_manager.get_cached_qualification(
            company_name="MissCorp",
            industry="SaaS"
        )
        
        stats = await cache_manager.get_cache_stats()
        assert stats["hit_rate"] == 50.0


@pytest.mark.asyncio
class TestGracefulDegradation:
    """Test fallback when Redis unavailable"""
    
    async def test_cache_read_failure_returns_none(self):
        """Test cache read error returns None gracefully"""
        manager = CacheManager(redis_url="redis://invalid:9999")
        
        result = await manager.get_cached_qualification(
            company_name="TestCorp",
            industry="SaaS"
        )
        
        # Should return None, not raise exception
        assert result is None
    
    async def test_cache_write_failure_returns_false(self):
        """Test cache write error returns False gracefully"""
        manager = CacheManager(redis_url="redis://invalid:9999")
        
        success = await manager.cache_qualification(
            company_name="TestCorp",
            industry="SaaS",
            qualification_data={"score": 80, "reasoning": "Test"}
        )
        
        # Should return False, not raise exception
        assert success is False
    
    async def test_health_check_failure(self):
        """Test health check reports unhealthy when Redis down"""
        manager = CacheManager(redis_url="redis://invalid:9999")
        
        health = await manager.health_check()
        
        assert health["status"] == "unhealthy"
        assert health["connected"] is False
        assert "error" in health


@pytest.mark.asyncio
class TestHealthCheck:
    """Test health check functionality"""
    
    async def test_health_check_success(self, cache_manager):
        """Test health check reports healthy when Redis up"""
        health = await cache_manager.health_check()
        
        assert health["status"] == "healthy"
        assert health["connected"] is True
        assert "latency_ms" in health
        assert health["latency_ms"] >= 0
    
    async def test_stats_structure(self, cache_manager):
        """Test cache stats return correct structure"""
        stats = await cache_manager.get_cache_stats()
        
        assert "connected" in stats
        assert "hits" in stats
        assert "misses" in stats
        assert "errors" in stats
        assert "hit_rate" in stats
        assert "total_operations" in stats
        
        # Values should be non-negative
        assert stats["hits"] >= 0
        assert stats["misses"] >= 0
        assert stats["errors"] >= 0
        assert 0 <= stats["hit_rate"] <= 100
