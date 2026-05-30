import logging
import sys

from app.config import settings

# Configure logging
logging.basicConfig(
    level=settings.LOGGING_LEVEL,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout)  # Log to console
    ]
)

logger = logging.getLogger(__name__)
