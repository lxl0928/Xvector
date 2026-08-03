from __future__ import annotations


class XvectorError(Exception):
    pass


class XvectorApiError(XvectorError):
    def __init__(self, code: int, message: str):
        super().__init__(f"[{code}] {message}")
        self.code = code
        self.message = message
