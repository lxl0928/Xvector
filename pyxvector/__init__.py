"""pyxvector: thin HTTP client for Xvector (Milvus REST v2 style)."""

from pyxvector.client import XvectorClient
from pyxvector.exceptions import XvectorApiError, XvectorError

__all__ = ["XvectorClient", "XvectorApiError", "XvectorError"]
__version__ = "0.1.0"
