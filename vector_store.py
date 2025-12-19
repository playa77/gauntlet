# Script Version: 0.1.0 | Phase 1: Agent Foundation
# Description: Persistent vector storage for research data using ChromaDB.
# Implementation: Handles 'sources' and 'knowledge_fragments' collections with local persistence.

import chromadb
from chromadb.config import Settings
from typing import List, Dict, Any, Optional
import uuid

class VectorStore:
    """
    Manages persistent vector collections for the research process.
    Uses ChromaDB's default local embedding model for Phase 1.
    """
    def __init__(self, persist_directory: str = "./research_db"):
        print(f"[VECTOR STORE] Initializing persistence at: {persist_directory}")
        try:
            self.client = chromadb.PersistentClient(path=persist_directory)
            
            # Collection for raw source snippets and metadata
            self.sources = self.client.get_or_create_collection(
                name="sources",
                metadata={"hnsw:space": "cosine"}
            )
            
            # Collection for extracted insights and verified claims
            self.fragments = self.client.get_or_create_collection(
                name="knowledge_fragments",
                metadata={"hnsw:space": "cosine"}
            )
        except Exception as e:
            print(f"[ERROR] [VectorStore] Initialization failed: {e}")
            raise

    def add_source(self, content: str, metadata: Dict[str, Any], doc_id: Optional[str] = None):
        """Adds a source document or snippet to the 'sources' collection."""
        uid = doc_id or str(uuid.uuid4())
        
        if not content or not content.strip():
            return
            
        try:
            self.sources.add(
                documents=[content],
                metadatas=[metadata],
                ids=[uid]
            )
        except Exception as e:
            print(f"[ERROR] [VectorStore] Failed to add source: {e}")

    def query_sources(self, query_text: str, n_results: int = 5) -> Dict[str, Any]:
        """Performs semantic search across stored sources."""
        try:
            return self.sources.query(
                query_texts=[query_text],
                n_results=n_results
            )
        except Exception as e:
            print(f"[ERROR] [VectorStore] Query failed: {e}")
            return {"documents": [[]], "metadatas": [[]]}

    def add_fragment(self, content: str, metadata: Dict[str, Any]):
        """Adds an extracted knowledge fragment to the 'fragments' collection."""
        try:
            self.fragments.add(
                documents=[content],
                metadatas=[metadata],
                ids=[str(uuid.uuid4())]
            )
        except Exception as e:
            print(f"[ERROR] [VectorStore] Failed to add fragment: {e}")
