# Script Version: 0.3.0 | Phase 2: Orchestration
# Description: Thread-safe utility for rate-limited fetching and parsing.
# Implementation: Fixed deadlock by moving sleep outside the lock.

import time
import httpx
import re
import os
import tempfile
import threading
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
    def __init__(self, delay_ms: int = 500):
        self.requested_delay = delay_ms / 1000.0
        self.enforced_delay = self.requested_delay * 2.0
        # Initialize next_available_time to now
        self.next_available_time = time.perf_counter()
        self.visited_urls: Set[str] = set()
        self._lock = threading.Lock() 
        
        self.headers = {
            "User-Agent": "GauntletResearchBot/0.3.0 (Educational Research Project; Thread-Safe Rate Limiting)"
        }
        print(f"[SOURCE MANAGER] Initialized with thread-safe rate limiting (Delay: {self.enforced_delay}s).")

    def _wait_for_slot(self):
        """
        Thread-safe rate limiting.
        Reserves a time slot and sleeps OUTSIDE the lock to prevent deadlocks.
        """
        sleep_duration = 0
        
        with self._lock:
            now = time.perf_counter()
            if now < self.next_available_time:
                # We are too early, must wait until next_available_time
                sleep_duration = self.next_available_time - now
                # Reserve the slot after our wait
                self.next_available_time += self.enforced_delay
            else:
                # We are on time or late, just reserve the next slot from now
                self.next_available_time = now + self.enforced_delay
        
        if sleep_duration > 0:
            time.sleep(sleep_duration)

    def fetch_and_extract(self, url: str) -> Dict[str, Any]:
        # Check visited cache first (thread-safe read optimization could be added, but lock is safer)
        with self._lock:
            if url in self.visited_urls:
                return {"url": url, "status": "skipped", "content": ""}
            self.visited_urls.add(url)

        self._wait_for_slot()
        
        print(f"[SOURCE MANAGER] Fetching: {url}")
        try:
            with httpx.Client(headers=self.headers, timeout=30.0, follow_redirects=True) as client:
                response = client.get(url)
                response.raise_for_status()
                
                content_type = response.headers.get("content-type", "").lower()
                
                if "application/pdf" in content_type or url.lower().endswith(".pdf"):
                    return self._process_pdf_binary(url, response.content)
                
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
            print(f"[ERROR] [SourceManager] Failed {url}: {e}")
            return {"url": url, "status": "error", "error": str(e)}

    def _process_pdf_binary(self, url: str, binary_data: bytes) -> Dict[str, Any]:
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
