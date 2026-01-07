from datetime import datetime, timedelta
from typing import Dict, Optional, Any, Tuple
from dataclasses import dataclass, field
import threading

from app.config import get_settings
from app.models.schemas import VehicleStatus, CacheStats


@dataclass
class CacheEntry:
    """Single cache entry with timestamp and result."""
    plate_number: str
    result: VehicleStatus
    timestamp: datetime = field(default_factory=datetime.now)
    
    def is_expired(self, cooldown: timedelta) -> bool:
        """Check if this entry has expired."""
        return datetime.now() - self.timestamp > cooldown


class PlateCache:
    """
    In-memory cache for recently scanned plates.
    Prevents duplicate API calls for plates scanned within the cooldown period.
    """
    
    def __init__(self, cooldown_minutes: Optional[int] = None):
        settings = get_settings()
        self._cooldown = timedelta(minutes=cooldown_minutes or settings.cache_cooldown_min)
        self._cache: Dict[str, CacheEntry] = {}
        self._lock = threading.Lock()
        
        # Statistics
        self._hit_count = 0
        self._miss_count = 0
    
    def _normalize_plate(self, plate_number: str) -> str:
        """Normalize plate number for consistent caching."""
        return plate_number.upper().replace(" ", "").replace("-", "")
    
    def is_recently_scanned(self, plate_number: str) -> bool:
        """Check if plate was recently scanned (within cooldown period)."""
        normalized = self._normalize_plate(plate_number)
        
        with self._lock:
            if normalized in self._cache:
                entry = self._cache[normalized]
                if not entry.is_expired(self._cooldown):
                    return True
                # Entry expired, remove it
                del self._cache[normalized]
            return False
    
    def get_cached_result(self, plate_number: str) -> Optional[VehicleStatus]:
        """Get cached result for a plate if available and not expired."""
        normalized = self._normalize_plate(plate_number)
        
        with self._lock:
            if normalized in self._cache:
                entry = self._cache[normalized]
                if not entry.is_expired(self._cooldown):
                    self._hit_count += 1
                    return entry.result
                # Entry expired, remove it
                del self._cache[normalized]
            self._miss_count += 1
            return None
    
    def add_plate(self, plate_number: str, result: VehicleStatus) -> None:
        """Add a plate and its result to the cache."""
        normalized = self._normalize_plate(plate_number)
        
        with self._lock:
            self._cache[normalized] = CacheEntry(
                plate_number=normalized,
                result=result,
                timestamp=datetime.now()
            )
    
    def get_or_fetch(
        self, 
        plate_number: str, 
        fetch_func: Any
    ) -> Tuple[VehicleStatus, bool]:
        """
        Get cached result or fetch from external source.
        
        Returns:
            Tuple of (VehicleStatus, is_cached)
        """
        cached = self.get_cached_result(plate_number)
        if cached is not None:
            return cached, True
        
        # Not cached, need to fetch
        result = fetch_func(plate_number)
        self.add_plate(plate_number, result)
        return result, False
    
    async def get_or_fetch_async(
        self, 
        plate_number: str, 
        fetch_func: Any
    ) -> Tuple[VehicleStatus, bool]:
        """
        Async version: Get cached result or fetch from external source.
        
        Returns:
            Tuple of (VehicleStatus, is_cached)
        """
        cached = self.get_cached_result(plate_number)
        if cached is not None:
            return cached, True
        
        # Not cached, need to fetch
        result = await fetch_func(plate_number)
        self.add_plate(plate_number, result)
        return result, False
    
    def cleanup_expired(self) -> int:
        """Remove all expired entries. Returns count of removed entries."""
        removed = 0
        
        with self._lock:
            expired_keys = [
                key for key, entry in self._cache.items()
                if entry.is_expired(self._cooldown)
            ]
            for key in expired_keys:
                del self._cache[key]
                removed += 1
        
        return removed
    
    def clear(self) -> None:
        """Clear all cache entries."""
        with self._lock:
            self._cache.clear()
            self._hit_count = 0
            self._miss_count = 0
    
    def get_stats(self) -> CacheStats:
        """Get cache statistics."""
        with self._lock:
            total = len(self._cache)
            expired = sum(
                1 for entry in self._cache.values()
                if entry.is_expired(self._cooldown)
            )
            active = total - expired
            
            total_requests = self._hit_count + self._miss_count
            hit_rate = self._hit_count / total_requests if total_requests > 0 else 0.0
            
            return CacheStats(
                total_entries=total,
                active_entries=active,
                expired_entries=expired,
                hit_count=self._hit_count,
                miss_count=self._miss_count,
                hit_rate=hit_rate
            )


# Global cache instance
plate_cache = PlateCache()

