import logging
import os
import time
from typing import Dict, Any

logger = logging.getLogger(__name__)


class StorageManager:
    @staticmethod
    def cleanup_expired_images(images_dir: str, max_age_days: int = 14) -> int:
        """
        Removes generated image files older than max_age_days.
        Returns: count of deleted files.
        """
        if not os.path.exists(images_dir):
            return 0

        now = time.time()
        max_age_seconds = max_age_days * 86400
        deleted_count = 0

        try:
            for filename in os.listdir(images_dir):
                filepath = os.path.join(images_dir, filename)
                if not os.path.isfile(filepath):
                    continue

                if not filename.startswith("gen_") or not filename.endswith(".png"):
                    continue

                try:
                    mtime = os.path.getmtime(filepath)
                    if now - mtime > max_age_seconds:
                        os.remove(filepath)
                        deleted_count += 1
                        logger.debug("Removed expired image: %s", filename)
                except OSError as err:
                    logger.warning("Error checking/removing file %s: %s", filepath, err)

        except Exception as exc:
            logger.error("Failed to run image cleanup in %s: %s", images_dir, exc)

        logger.info("Storage cleanup finished: removed %d expired images (TTL %d days)", deleted_count, max_age_days)
        return deleted_count

    @staticmethod
    def get_storage_stats(images_dir: str) -> Dict[str, Any]:
        """
        Returns stats about the images directory: file count, total size in MB.
        """
        if not os.path.exists(images_dir):
            return {"file_count": 0, "total_size_mb": 0.0}

        count = 0
        total_bytes = 0
        try:
            for filename in os.listdir(images_dir):
                filepath = os.path.join(images_dir, filename)
                if os.path.isfile(filepath):
                    count += 1
                    total_bytes += os.path.getsize(filepath)
        except Exception:
            pass

        return {
            "file_count": count,
            "total_size_mb": round(total_bytes / (1024 * 1024), 2),
        }
