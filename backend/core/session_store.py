"""
Session Store for Supervisor State Management

This module provides session storage for multi-turn conversations.

Phase 1 Implementation: In-Memory Store
- Uses Python dict for storage
- Thread-safe operations with locks
- Session expiry (30-min timeout)
- Automatic cleanup of expired sessions

Phase 2 (Future): Redis + MongoDB
- Short-term: Redis (active sessions, 30-min TTL)
- Medium-term: MongoDB (session logs, 7-day TTL)
- Long-term: MongoDB (user profiles, permanent)
"""
import threading
import time
from datetime import datetime, timedelta
from typing import Dict, Optional, List
from abc import ABC, abstractmethod

from schemas.supervisor import SupervisorState, SessionStoreEntry
from core.logging import get_logger

logger = get_logger(__name__)


# ============================================================================
# Abstract Base Class for Session Store
# ============================================================================

class SessionStore(ABC):
    """
    Abstract base class for session storage implementations

    Defines the interface that all session stores must implement.
    Allows easy migration from in-memory to Redis/MongoDB in Phase 2.
    """

    @abstractmethod
    def save(self, session_id: str, supervisor_state: SupervisorState) -> None:
        """
        Save supervisor state to store

        Args:
            session_id: Unique session identifier
            supervisor_state: SupervisorState to save

        Raises:
            Exception: If save fails
        """
        pass

    @abstractmethod
    def get(self, session_id: str) -> Optional[SupervisorState]:
        """
        Retrieve supervisor state from store

        Args:
            session_id: Session identifier

        Returns:
            SupervisorState if found and not expired, None otherwise
        """
        pass

    @abstractmethod
    def delete(self, session_id: str) -> bool:
        """
        Delete session from store

        Args:
            session_id: Session identifier

        Returns:
            True if deleted, False if not found
        """
        pass

    @abstractmethod
    def exists(self, session_id: str) -> bool:
        """
        Check if session exists and is not expired

        Args:
            session_id: Session identifier

        Returns:
            True if exists and active, False otherwise
        """
        pass

    @abstractmethod
    def clear_all(self) -> int:
        """
        Clear all sessions from store

        Returns:
            Number of sessions cleared
        """
        pass

    @abstractmethod
    def cleanup_expired(self) -> int:
        """
        Remove expired sessions

        Returns:
            Number of sessions cleaned up
        """
        pass

    @abstractmethod
    def get_all_active_sessions(self) -> List[str]:
        """
        Get list of all active session IDs

        Returns:
            List of active session IDs
        """
        pass

    @abstractmethod
    def get_stats(self) -> Dict[str, any]:
        """
        Get session store statistics

        Returns:
            Dict with stats (total_sessions, active_sessions, expired_sessions, etc.)
        """
        pass


# ============================================================================
# In-Memory Session Store Implementation (Phase 1)
# ============================================================================

class InMemorySessionStore(SessionStore):
    """
    In-memory session store using Python dict

    Features:
    - Thread-safe operations with RLock
    - Automatic session expiry (configurable, default 30 minutes)
    - Periodic cleanup of expired sessions
    - Session statistics tracking

    Example:
        >>> store = InMemorySessionStore(session_timeout_minutes=30)
        >>> store.save("session-123", supervisor_state)
        >>> state = store.get("session-123")
        >>> store.delete("session-123")

    Thread Safety:
        All operations are protected by threading.RLock for thread safety.
    """

    def __init__(
        self,
        session_timeout_minutes: int = 30,
        cleanup_interval_seconds: int = 300  # 5 minutes
    ):
        """
        Initialize in-memory session store

        Args:
            session_timeout_minutes: Session expiry timeout (default: 30 minutes)
            cleanup_interval_seconds: Interval for automatic cleanup (default: 5 minutes)
        """
        self.session_timeout_minutes = session_timeout_minutes
        self.cleanup_interval_seconds = cleanup_interval_seconds

        # Storage: {session_id: SessionStoreEntry}
        self._store: Dict[str, SessionStoreEntry] = {}

        # Thread safety
        self._lock = threading.RLock()

        # Statistics
        self._stats = {
            "total_saves": 0,
            "total_gets": 0,
            "total_deletes": 0,
            "total_cleanups": 0,
            "cache_hits": 0,
            "cache_misses": 0,
        }

        # Last cleanup time
        self._last_cleanup = datetime.utcnow()

        logger.info(
            f"Initialized InMemorySessionStore "
            f"(timeout: {session_timeout_minutes}m, "
            f"cleanup: {cleanup_interval_seconds}s)"
        )

    def save(self, session_id: str, supervisor_state: SupervisorState) -> None:
        """
        Save supervisor state to in-memory store

        Creates new entry if session doesn't exist, updates existing otherwise.

        Args:
            session_id: Unique session identifier
            supervisor_state: SupervisorState to save
        """
        with self._lock:
            now = datetime.utcnow()
            expires_at = now + timedelta(minutes=self.session_timeout_minutes)

            # Check if entry exists
            if session_id in self._store:
                # Update existing entry
                entry = self._store[session_id]
                entry["supervisor_state"] = supervisor_state
                entry["last_accessed"] = now
                entry["expires_at"] = expires_at
            else:
                # Create new entry
                entry: SessionStoreEntry = {
                    "session_id": session_id,
                    "supervisor_state": supervisor_state,
                    "created_at": now,
                    "last_accessed": now,
                    "expires_at": expires_at,
                }
                self._store[session_id] = entry

            self._stats["total_saves"] += 1

            logger.info(
                f"Saved session {session_id} "
                f"(expires: {expires_at.isoformat()})"
            )

    def get(self, session_id: str) -> Optional[SupervisorState]:
        """
        Retrieve supervisor state from store

        Returns None if:
        - Session doesn't exist
        - Session has expired

        Updates last_accessed timestamp if session found.

        Args:
            session_id: Session identifier

        Returns:
            SupervisorState if found and not expired, None otherwise
        """
        with self._lock:
            self._stats["total_gets"] += 1

            # Check if exists
            if session_id not in self._store:
                self._stats["cache_misses"] += 1
                logger.info(f"Session {session_id} not found")
                return None

            entry = self._store[session_id]

            # Check if expired
            now = datetime.utcnow()
            if now > entry["expires_at"]:
                self._stats["cache_misses"] += 1
                logger.info(f"Session {session_id} expired")
                # Delete expired session
                del self._store[session_id]
                return None

            # Update last_accessed and extend expiry
            entry["last_accessed"] = now
            entry["expires_at"] = now + timedelta(minutes=self.session_timeout_minutes)

            self._stats["cache_hits"] += 1
            logger.info(f"Retrieved session {session_id}")

            return entry["supervisor_state"]

    def delete(self, session_id: str) -> bool:
        """
        Delete session from store

        Args:
            session_id: Session identifier

        Returns:
            True if deleted, False if not found
        """
        with self._lock:
            if session_id in self._store:
                del self._store[session_id]
                self._stats["total_deletes"] += 1
                logger.info(f"Deleted session {session_id}")
                return True
            else:
                logger.info(f"Session {session_id} not found for deletion")
                return False

    def exists(self, session_id: str) -> bool:
        """
        Check if session exists and is not expired

        Args:
            session_id: Session identifier

        Returns:
            True if exists and active, False otherwise
        """
        with self._lock:
            if session_id not in self._store:
                return False

            entry = self._store[session_id]
            now = datetime.utcnow()

            # Check if expired
            if now > entry["expires_at"]:
                # Delete expired session
                del self._store[session_id]
                return False

            return True

    def clear_all(self) -> int:
        """
        Clear all sessions from store

        Returns:
            Number of sessions cleared
        """
        with self._lock:
            count = len(self._store)
            self._store.clear()
            logger.info(f"Cleared all sessions (count: {count})")
            return count

    def cleanup_expired(self) -> int:
        """
        Remove expired sessions

        Called automatically or manually to clean up expired sessions.

        Returns:
            Number of sessions cleaned up
        """
        with self._lock:
            now = datetime.utcnow()
            expired_sessions = []

            # Find expired sessions
            for session_id, entry in self._store.items():
                if now > entry["expires_at"]:
                    expired_sessions.append(session_id)

            # Delete expired sessions
            for session_id in expired_sessions:
                del self._store[session_id]

            if expired_sessions:
                self._stats["total_cleanups"] += len(expired_sessions)
                logger.info(f"Cleaned up {len(expired_sessions)} expired sessions")

            self._last_cleanup = now

            return len(expired_sessions)

    def get_all_active_sessions(self) -> List[str]:
        """
        Get list of all active session IDs

        Returns:
            List of active session IDs (non-expired)
        """
        with self._lock:
            now = datetime.utcnow()
            active_sessions = []

            for session_id, entry in self._store.items():
                if now <= entry["expires_at"]:
                    active_sessions.append(session_id)

            return active_sessions

    def get_stats(self) -> Dict[str, any]:
        """
        Get session store statistics

        Returns:
            Dict with stats:
            - total_sessions: Total number of sessions in store
            - active_sessions: Number of non-expired sessions
            - expired_sessions: Number of expired sessions (pending cleanup)
            - total_saves: Cumulative save operations
            - total_gets: Cumulative get operations
            - total_deletes: Cumulative delete operations
            - total_cleanups: Cumulative cleanup operations
            - cache_hit_rate: Percentage of successful gets
            - last_cleanup: Timestamp of last cleanup
        """
        with self._lock:
            now = datetime.utcnow()
            active_count = 0
            expired_count = 0

            for entry in self._store.values():
                if now <= entry["expires_at"]:
                    active_count += 1
                else:
                    expired_count += 1

            # Calculate cache hit rate
            total_gets = self._stats["total_gets"]
            cache_hits = self._stats["cache_hits"]
            cache_hit_rate = (
                (cache_hits / total_gets * 100) if total_gets > 0 else 0.0
            )

            return {
                "store_type": "in_memory",
                "total_sessions": len(self._store),
                "active_sessions": active_count,
                "expired_sessions": expired_count,
                "total_saves": self._stats["total_saves"],
                "total_gets": self._stats["total_gets"],
                "total_deletes": self._stats["total_deletes"],
                "total_cleanups": self._stats["total_cleanups"],
                "cache_hits": self._stats["cache_hits"],
                "cache_misses": self._stats["cache_misses"],
                "cache_hit_rate": f"{cache_hit_rate:.1f}%",
                "last_cleanup": self._last_cleanup.isoformat(),
                "session_timeout_minutes": self.session_timeout_minutes,
            }

    def auto_cleanup_if_needed(self) -> int:
        """
        Perform cleanup if cleanup interval has elapsed

        This method should be called periodically (e.g., on every get/save)
        to automatically clean up expired sessions without explicit calls.

        Returns:
            Number of sessions cleaned up (0 if cleanup not needed yet)
        """
        with self._lock:
            now = datetime.utcnow()
            time_since_last_cleanup = (now - self._last_cleanup).total_seconds()

            if time_since_last_cleanup >= self.cleanup_interval_seconds:
                return self.cleanup_expired()

            return 0

    def get_session_info(self, session_id: str) -> Optional[Dict[str, any]]:
        """
        Get metadata about a specific session

        Args:
            session_id: Session identifier

        Returns:
            Dict with session metadata or None if not found

        Example:
            {
                "session_id": "uuid-123",
                "created_at": "2025-01-15T10:00:00",
                "last_accessed": "2025-01-15T10:15:00",
                "expires_at": "2025-01-15T10:30:00",
                "is_expired": False,
                "turn_count": 5,
                "is_active": True
            }
        """
        with self._lock:
            if session_id not in self._store:
                return None

            entry = self._store[session_id]
            now = datetime.utcnow()
            is_expired = now > entry["expires_at"]

            return {
                "session_id": entry["session_id"],
                "created_at": entry["created_at"].isoformat(),
                "last_accessed": entry["last_accessed"].isoformat(),
                "expires_at": entry["expires_at"].isoformat(),
                "is_expired": is_expired,
                "turn_count": entry["supervisor_state"]["turn_count"],
                "is_active": entry["supervisor_state"]["is_active"],
                "user_id": entry["supervisor_state"]["user_context"]["user_id"],
            }


# ============================================================================
# Global Session Store Instance (Singleton Pattern)
# ============================================================================

# Global instance (initialized when module is imported)
_session_store: Optional[SessionStore] = None


def get_session_store() -> SessionStore:
    """
    Get global session store instance (singleton)

    Creates instance on first call. Subsequent calls return same instance.

    Returns:
        SessionStore instance

    Example:
        >>> store = get_session_store()
        >>> store.save("session-123", supervisor_state)
    """
    global _session_store

    if _session_store is None:
        # Initialize with default settings
        _session_store = InMemorySessionStore(
            session_timeout_minutes=30,
            cleanup_interval_seconds=300  # 5 minutes
        )

    return _session_store


def set_session_store(store: SessionStore) -> None:
    """
    Set global session store instance

    Allows injecting custom session store (useful for testing or Phase 2 migration)

    Args:
        store: SessionStore implementation

    Example:
        >>> # For testing
        >>> test_store = InMemorySessionStore(session_timeout_minutes=1)
        >>> set_session_store(test_store)
    """
    global _session_store
    _session_store = store
    logger.info(f"Set global session store to {store.__class__.__name__}")
