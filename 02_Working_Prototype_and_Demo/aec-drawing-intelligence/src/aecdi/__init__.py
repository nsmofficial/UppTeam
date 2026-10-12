"""AEC Drawing Intelligence.

Extract -> structure -> check with rules -> LLM only where judgment is needed -> human verifies.
"""
import os

os.environ.setdefault("PYMUPDF_SUGGEST_LAYOUT_ANALYZER", "0")   # silence PyMuPDF's optional-package advisory

__version__ = "1.2.0"
