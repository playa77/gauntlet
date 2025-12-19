# Script Version: 0.2.7 | Phase 1: Agent Foundation
# Description: Unified utility for rate-limited fetching and parsing with deduplication.
# Implementation: Added visited_urls registry and automated PDF handling.

import time
import httpx
import re
import os
import tempfile
from pathlib import Path
from typing import Dict, Any, Set

try:
    import fitz  # PyMuPDF
except ImportError:
    fitz = None

try:
    import trafilatura
except ImportError:
    trafilatura = None

class SourceManager:
    """
    Handles fetching and parsing of external sources with buffered rate limiting.
    Includes deduplication to prevent redundant processing of the same URL.
    """
    def __init__(self, delay_ms: int = 500):
        self.requested_delay = delay_ms / 1000.0
        self.enforced_delay = self.requested_delay * 2.0
        self.last_request_completion_time = time.perf_counter() - self.enforced_delay
        self.visited_urls: Set[str] = set()
        
        self.headers = {
            "User-Agent": "GauntletResearchBot/0.2.7 (Educational Research Project; Double-Buffer Rate Limiting)"
        }
        print(f"[SOURCE MANAGER] Initialized with deduplication.")

    def _wait_for_slot(self):
        target_time = self.last_request_completion_time + self.enforced_delay
        while True:
            now = time.perf_counter()
            remaining = target_time - now
            if remaining <= 0:
                break
            if remaining > 0.010:
                time.sleep(remaining / 2.0)

    def fetch_and_extract(self, url: str) -> Dict[str, Any]:
        """
        Fetches content, handles deduplication, and routes to appropriate parser (HTML/PDF).
        """
        if url in self.visited_urls:
            print(f"[SOURCE MANAGER] Skipping already visited URL: {url}")
            return {"url": url, "status": "skipped", "content": ""}

        self._wait_for_slot()
        self.visited_urls.add(url)
        
        print(f"[SOURCE MANAGER] Fetching: {url}")
        try:
            with httpx.Client(headers=self.headers, timeout=30.0, follow_redirects=True) as client:
                response = client.get(url)
                response.raise_for_status()
                self.last_request_completion_time = time.perf_counter()
                
                content_type = response.headers.get("content-type", "").lower()
                
                # Handle PDF
                if "application/pdf" in content_type or url.lower().endswith(".pdf"):
                    return self._process_pdf_binary(url, response.content)
                
                # Handle HTML
                if trafilatura:
                    content = trafilatura.extract(response.text, include_comments=False)
                else:
                    content = re.sub(r'<[^>]+>', '', response.text)
                
                return {
                    "url": url,
                    "content": content or "No content extracted.",
                    "status": "success",
                    "type": "html"
                }
        except Exception as e:
            self.last_request_completion_time = time.perf_counter()
            print(f"[ERROR] [SourceManager] Failed {url}: {e}")
            return {"url": url, "status": "error", "error": str(e)}

    def _process_pdf_binary(self, url: str, binary_data: bytes) -> Dict[str, Any]:
        """Saves binary PDF to temp file and extracts text."""
        if not fitz:
            return {"url": url, "status": "error", "error": "PyMuPDF not installed"}
            
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            tmp.write(binary_data)
            tmp_path = tmp.name
            
        try:
            text_content = []
            with fitz.open(tmp_path) as doc:
                for page in doc:
                    text_content.append(page.get_text())
            return {
                "url": url,
                "content": "\n".join(text_content),
                "status": "success",
                "type": "pdf"
            }
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
