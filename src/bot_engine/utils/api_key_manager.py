"""API Key Manager for handling multiple keys with rotation and health tracking."""

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional

from loguru import logger


class KeyStatus(str, Enum):
    """Status of an API key."""

    ACTIVE = "active"  # Key is working
    FAILED = "failed"  # Key has failed, in cooldown
    EXHAUSTED = "exhausted"  # Key has failed too many times


@dataclass
class APIKeyInfo:
    """Information about an API key and its health status."""

    key: str
    status: KeyStatus = KeyStatus.ACTIVE
    failure_count: int = 0
    last_failure: Optional[datetime] = None
    last_success: Optional[datetime] = None
    cooldown_until: Optional[datetime] = None

    def is_in_cooldown(self) -> bool:
        """Check if key is currently in cooldown period."""
        if not self.cooldown_until:
            return False
        return datetime.now() < self.cooldown_until

    def mask_key(self) -> str:
        """Return masked version of key for logging."""
        if len(self.key) <= 8:
            return "****"
        return f"{self.key[:4]}...{self.key[-4:]}"


class APIKeyManager:
    """Manages a pool of API keys with health tracking and rotation."""

    def __init__(
        self,
        api_keys: List[str],
        cooldown_seconds: int = 300,  # 5 minutes default
        max_failures: int = 3,
    ):
        """Initialize the key manager.

        Args:
            api_keys: List of API keys to manage
            cooldown_seconds: How long to wait before retrying a failed key
            max_failures: Max failures before marking key as exhausted
        """
        if not api_keys:
            raise ValueError("At least one API key is required")

        self.cooldown_seconds = cooldown_seconds
        self.max_failures = max_failures

        # Initialize key info
        self.keys: Dict[str, APIKeyInfo] = {key: APIKeyInfo(key=key) for key in api_keys}

        # Track current key
        self.current_key: Optional[str] = api_keys[0]
        self.rotation_count = 0

        logger.info(f"Initialized APIKeyManager with {len(api_keys)} keys")

    def get_current_key(self) -> Optional[str]:
        """Get the current active key.

        Returns:
            Current API key or None if all keys are exhausted
        """
        if self.current_key and self._is_key_usable(self.current_key):
            return self.current_key

        # Current key not usable, find next one
        next_key = self.get_next_key()
        if next_key:
            self.current_key = next_key
        return self.current_key

    def get_next_key(self) -> Optional[str]:
        """Get the next available healthy key.

        Returns:
            Next usable API key or None if all keys exhausted
        """
        # 1. Try ACTIVE keys first
        for key, info in self.keys.items():
            if info.status == KeyStatus.ACTIVE:
                logger.debug(f"Selected ACTIVE key: {info.mask_key()}")
                return key

        # 2. Try FAILED keys that have completed cooldown
        for key, info in self.keys.items():
            if info.status == KeyStatus.FAILED and not info.is_in_cooldown():
                logger.info(f"Key {info.mask_key()} cooldown expired, marking as ACTIVE")
                info.status = KeyStatus.ACTIVE
                info.cooldown_until = None
                return key

        # 3. All keys are either EXHAUSTED or in cooldown
        logger.error("No available API keys!")
        return None

    def mark_success(self, key: str) -> None:
        """Mark a key as successfully used.

        Args:
            key: The API key that worked
        """
        if key not in self.keys:
            return

        info = self.keys[key]
        info.status = KeyStatus.ACTIVE
        info.last_success = datetime.now()
        info.failure_count = 0  # Reset failures on success
        info.cooldown_until = None

        logger.debug(f"Key {info.mask_key()} marked as successful")

    def mark_failure(self, key: str, error_msg: str) -> None:
        """Mark a key as failed and put it in cooldown.

        Args:
            key: The API key that failed
            error_msg: The error message for logging
        """
        if key not in self.keys:
            return

        info = self.keys[key]
        info.failure_count += 1
        info.last_failure = datetime.now()

        # Check if key should be exhausted
        if info.failure_count >= self.max_failures:
            info.status = KeyStatus.EXHAUSTED
            logger.error(f"Key {info.mask_key()} EXHAUSTED after {info.failure_count} failures")
        else:
            info.status = KeyStatus.FAILED
            info.cooldown_until = datetime.now() + timedelta(seconds=self.cooldown_seconds)
            logger.warning(
                f"Key {info.mask_key()} FAILED (attempt {info.failure_count}/{self.max_failures}): {error_msg}"
            )

    def rotate_key(self, reason: str) -> Optional[str]:
        """Rotate to the next available key.

        Args:
            reason: Reason for rotation (for logging)

        Returns:
            Next API key or None if all keys exhausted
        """
        old_key = self.current_key
        next_key = self.get_next_key()

        if next_key:
            self.current_key = next_key
            self.rotation_count += 1

            old_masked = self.keys[old_key].mask_key() if old_key else "none"
            new_masked = self.keys[next_key].mask_key()

            logger.info(
                f"Key rotation #{self.rotation_count}: {old_masked} → {new_masked} ({reason})"
            )

        return next_key

    def get_stats(self) -> Dict:
        """Get statistics about key usage.

        Returns:
            Dictionary with key statistics
        """
        stats = {
            "total_keys": len(self.keys),
            "active_keys": sum(1 for k in self.keys.values() if k.status == KeyStatus.ACTIVE),
            "failed_keys": sum(1 for k in self.keys.values() if k.status == KeyStatus.FAILED),
            "exhausted_keys": sum(1 for k in self.keys.values() if k.status == KeyStatus.EXHAUSTED),
            "rotation_count": self.rotation_count,
            "current_key": (self.keys[self.current_key].mask_key() if self.current_key else None),
        }

        return stats

    def _is_key_usable(self, key: str) -> bool:
        """Check if a key is currently usable.

        Args:
            key: The API key to check

        Returns:
            True if key can be used now
        """
        if key not in self.keys:
            return False

        info = self.keys[key]

        if info.status == KeyStatus.ACTIVE:
            return True

        if info.status == KeyStatus.FAILED and not info.is_in_cooldown():
            # Cooldown expired, mark as active
            info.status = KeyStatus.ACTIVE
            info.cooldown_until = None
            return True

        return False
