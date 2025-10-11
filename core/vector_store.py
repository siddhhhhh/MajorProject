import chromadb
from chromadb.config import Settings as ChromaSettings
from typing import List, Dict, Any, Optional
from config.settings import settings
import os

class VectorStore:
    def __init__(self):
        # Initialize persistent Chroma client
        self.client = chromadb.PersistentClient(
            path=settings.CHROMA_PERSIST_DIR
        )
        
        # Get or create collection
        self.collection = self.client.get_or_create_collection(
            name=settings.CHROMA_COLLECTION_NAME,
            metadata={"description": "ESG evidence and reports"}
        )
    
    def add_documents(self, documents: List[str], metadatas: List[Dict], 
                     ids: List[str]) -> None:
        """Add documents to vector store"""
        try:
            self.collection.add(
                documents=documents,
                metadatas=metadatas,
                ids=ids
            )
            print(f"Added {len(documents)} documents to vector store")
        except Exception as e:
            print(f"Error adding documents: {e}")
    
    def search_similar(self, query: str, n_results: int = 5, 
                      filter_dict: Optional[Dict] = None) -> Dict[str, Any]:
        """Search for similar documents"""
        try:
            results = self.collection.query(
                query_texts=[query],
                n_results=n_results,
                where=filter_dict
            )
            return results
        except Exception as e:
            print(f"Error searching documents: {e}")
            return {"documents": [[]], "metadatas": [[]], "distances": [[]]}
    
    def get_collection_count(self) -> int:
        """Get total documents in collection"""
        return self.collection.count()
    
    def delete_collection(self) -> None:
        """Delete the collection"""
        self.client.delete_collection(name=settings.CHROMA_COLLECTION_NAME)

# Global instance
vector_store = VectorStore()
