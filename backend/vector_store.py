import os
import json
import numpy as np
import requests
import faiss
from rank_bm25 import BM25Okapi
from dotenv import load_dotenv
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
from typing import List, Dict, Any

load_dotenv()

class VectorStoreManager:
    def __init__(self):
        self.storage_dir = os.getenv("FAISS_INDEX_PATH", "./backend/vector_db")
        os.makedirs(self.storage_dir, exist_ok=True)
        
        self.index_path = os.path.join(self.storage_dir, "faiss.index")
        self.meta_path = os.path.join(self.storage_dir, "metadata.json")
        
        self.dimension = 384
        self.metadata_store = []
        
        # Load environment credentials
        self.hf_token = os.getenv("HUGGINGFACE_API_KEY", "")
        self.model_id = "BAAI/bge-small-en-v1.5"
        self.api_url = f"https://api-inference.huggingface.co/pipeline/feature-extraction/{self.model_id}"
        self.headers = {"Authorization": f"Bearer {self.hf_token}"} if self.hf_token else {}
        
        # Qdrant client setup (Optional production mode)
        self.qdrant_url = os.getenv("QDRANT_URL", "")
        self.qdrant_api_key = os.getenv("QDRANT_API_KEY", "")
        self.use_qdrant = bool(self.qdrant_url)
        
        if self.use_qdrant:
            try:
                self.qdrant_client = QdrantClient(url=self.qdrant_url, api_key=self.qdrant_api_key)
                # Create collection if it doesn't exist
                self.qdrant_collection = "memory_embeddings"
                collections = self.qdrant_client.get_collections().collections
                exists = any(c.name == self.qdrant_collection for c in collections)
                if not exists:
                    self.qdrant_client.create_collection(
                        collection_name=self.qdrant_collection,
                        vectors_config=VectorParams(size=self.dimension, distance=Distance.COSINE)
                    )
                print(f"VectorStore: Initialized Qdrant Cloud at {self.qdrant_url}")
            except Exception as e:
                print(f"VectorStore: Failed to connect to Qdrant, falling back to local FAISS: {e}")
                self.use_qdrant = False
        
        # Initialize Local FAISS (always available as default/fallback)
        if not self.use_qdrant:
            if os.path.exists(self.index_path):
                try:
                    self.index = faiss.read_index(self.index_path)
                    with open(self.meta_path, 'r') as f:
                        self.metadata_store = json.load(f)
                    print(f"VectorStore: Loaded local FAISS index with {self.index.ntotal} vectors.")
                except Exception as e:
                    print(f"VectorStore: Error loading FAISS index, creating new: {e}")
                    self.index = faiss.IndexFlatIP(self.dimension)
                    self.metadata_store = []
            else:
                self.index = faiss.IndexFlatIP(self.dimension)
                self.metadata_store = []
        
        # Initialize Local Embedding Model using SentenceTransformers
        try:
            from sentence_transformers import SentenceTransformer
            print("VectorStore: Loading local sentence-transformer model (BAAI/bge-small-en-v1.5)...")
            self.model = SentenceTransformer("BAAI/bge-small-en-v1.5")
            self.local_mode = True
            print("VectorStore: Local sentence-transformer loaded successfully.")
        except Exception as e:
            print(f"VectorStore: Failed to load local sentence-transformers ({e}). Falling back to Hugging Face API.")
            self.local_mode = False
            self.model = None

        # Initialize BM25 search engine
        self.bm25 = None
        if not self.use_qdrant and self.metadata_store:
            self._update_bm25()

    def _update_bm25(self):
        """Builds the BM25 search corpus from current stored content."""
        if not self.metadata_store:
            self.bm25 = None
            return
        corpus = [m.get("content", "").lower().split() for m in self.metadata_store]
        self.bm25 = BM25Okapi(corpus)

    def _get_embeddings(self, texts: List[str]) -> np.ndarray:
        """Generates embeddings locally using SentenceTransformers, falling back to API/dummy if offline."""
        if getattr(self, "local_mode", False) and self.model is not None:
            try:
                embeddings = self.model.encode(texts, convert_to_numpy=True).astype('float32')
                if len(embeddings.shape) == 1:
                    embeddings = embeddings.reshape(1, -1)
                faiss.normalize_L2(embeddings)
                return embeddings
            except Exception as e:
                print(f"VectorStore: Local Embedding generation failed ({e}). Trying API fallback.")

        payload = {"inputs": texts, "options": {"wait_for_model": True}}
        try:
            response = requests.post(self.api_url, headers=self.headers, json=payload, timeout=15)
            if response.status_code == 200:
                embeddings = np.array(response.json()).astype('float32')
                # If 1D array returned, reshape
                if len(embeddings.shape) == 1:
                    embeddings = embeddings.reshape(1, -1)
                faiss.normalize_L2(embeddings)
                return embeddings
            else:
                print(f"Embedding API Error: {response.status_code} - {response.text}")
        except Exception as e:
            print(f"Embedding Request Timeout/Failure: {e}")
            
        # Offline/error fallback: Generate pseudo-random deterministic embeddings based on text hash
        print("VectorStore: Using deterministic dummy embeddings (Offline Fallback)")
        fallback_embeddings = []
        for text in texts:
            # Seed generator with text hash to make it deterministic
            np.random.seed(abs(hash(text)) % (2**32))
            vec = np.random.randn(self.dimension).astype('float32')
            norm = np.linalg.norm(vec)
            if norm > 0:
                vec = vec / norm
            fallback_embeddings.append(vec)
        return np.array(fallback_embeddings)

    def add_documents(self, text_chunks: List[str], metadatas: List[Dict[str, Any]]) -> int:
        """Stores chunks and metadatas, creating embeddings asynchronously."""
        if not text_chunks:
            return 0
            
        embeddings = self._get_embeddings(text_chunks)
        
        if self.use_qdrant:
            try:
                points = []
                for i, (chunk, meta) in enumerate(zip(text_chunks, metadatas)):
                    point_id = str(uuid.uuid4())
                    payload = meta.copy()
                    payload["content"] = chunk
                    points.append(PointStruct(
                        id=point_id,
                        vector=embeddings[i].tolist(),
                        payload=payload
                    ))
                self.qdrant_client.upsert(
                    collection_name=self.qdrant_collection,
                    points=points
                )
                return len(text_chunks)
            except Exception as e:
                print(f"VectorStore: Qdrant upload failed, falling back to local storage: {e}")
                # Continue and store locally in FAISS
                
        # FAISS local storage
        self.index.add(embeddings)
        for chunk, meta in zip(text_chunks, metadatas):
            item = meta.copy()
            item["content"] = chunk
            self.metadata_store.append(item)
            
        # Sync to disk
        faiss.write_index(self.index, self.index_path)
        with open(self.meta_path, 'w') as f:
            json.dump(self.metadata_store, f)
            
        self._update_bm25()
        return len(text_chunks)

    def delete_documents(self, memory_event_id: str):
        """Deletes all vector embeddings associated with a memory event."""
        if self.use_qdrant:
            try:
                self.qdrant_client.delete(
                    collection_name=self.qdrant_collection,
                    filter={"must": [{"key": "memory_event_id", "match": {"value": memory_event_id}}]}
                )
                return
            except Exception as e:
                print(f"VectorStore: Qdrant deletion failed: {e}")
                
        # FAISS local deletion (rebuild the index excluding deleted items)
        if not self.metadata_store:
            return
            
        keep_indices = [i for i, m in enumerate(self.metadata_store) if m.get("memory_event_id") != memory_event_id]
        if len(keep_indices) == len(self.metadata_store):
            return  # Nothing to delete
            
        new_metadata = [self.metadata_store[i] for i in keep_indices]
        
        # Reconstruct FAISS Index
        new_index = faiss.IndexFlatIP(self.dimension)
        if new_metadata:
            # We can re-embed the remaining chunks
            chunks = [m["content"] for m in new_metadata]
            embeddings = self._get_embeddings(chunks)
            new_index.add(embeddings)
            
        self.index = new_index
        self.metadata_store = new_metadata
        
        # Save to disk
        faiss.write_index(self.index, self.index_path)
        with open(self.meta_path, 'w') as f:
            json.dump(self.metadata_store, f)
            
        self._update_bm25()
        print(f"VectorStore: Deleted memories for event {memory_event_id}. Remaining vectors: {len(self.metadata_store)}")

    def delete_all_documents(self):
        """Wipes all vectors and metadata."""
        if self.use_qdrant:
            try:
                self.qdrant_client.delete(
                    collection_name=self.qdrant_collection,
                    filter={"must": []}
                )
            except Exception as e:
                print(f"VectorStore: Qdrant reset failed: {e}")
                
        self.index = faiss.IndexFlatIP(self.dimension)
        self.metadata_store = []
        
        # Clear files
        if os.path.exists(self.index_path):
            os.remove(self.index_path)
        if os.path.exists(self.meta_path):
            os.remove(self.meta_path)
            
        self.bm25 = None
        print("VectorStore: Wiped all local vector indices.")

    def query(self, query_text: str, user_id: str, allowed_event_ids: List[str] = None, n_results: int = 5) -> Dict[str, Any]:
        """Performs hybrid semantic/keyword search over the vectors."""
        if self.use_qdrant:
            try:
                # Setup metadata filter
                should_filters = [{"key": "user_id", "match": {"value": user_id}}]
                if allowed_event_ids:
                    should_filters.append({
                        "key": "memory_event_id",
                        "match": {"any": allowed_event_ids}
                    })
                
                query_vector = self._get_embeddings([query_text])[0].tolist()
                search_result = self.qdrant_client.search(
                    collection_name=self.qdrant_collection,
                    query_vector=query_vector,
                    query_filter={"must": should_filters},
                    limit=n_results
                )
                
                docs = [r.payload["content"] for r in search_result]
                metadatas = [r.payload for r in search_result]
                return {
                    "documents": [docs],
                    "metadatas": [metadatas]
                }
            except Exception as e:
                print(f"VectorStore: Qdrant query failed, falling back to local: {e}")
                
        # FAISS search
        if self.index.ntotal == 0 or not self.metadata_store:
            return {"documents": [[]], "metadatas": [[]]}
            
        # 1. Filter index by active user and allowed event ids
        valid_indices = []
        for i, m in enumerate(self.metadata_store):
            if m.get("user_id") == user_id:
                if allowed_event_ids is None or m.get("memory_event_id") in allowed_event_ids:
                    valid_indices.append(i)
                    
        if not valid_indices:
            return {"documents": [[]], "metadatas": [[]]}
            
        # 2. Semantic Search (FAISS)
        query_embedding = self._get_embeddings([query_text])
        D, I = self.index.search(query_embedding, min(self.index.ntotal, 50))
        
        semantic_ranks = {idx: rank for rank, idx in enumerate(I[0]) if idx in valid_indices}
        
        # 3. Keyword Search (BM25)
        tokenized_query = query_text.lower().split()
        if self.bm25:
            bm25_scores = self.bm25.get_scores(tokenized_query)
            keyword_indices = sorted(valid_indices, key=lambda i: bm25_scores[i] if i < len(bm25_scores) else 0, reverse=True)[:50]
            keyword_ranks = {idx: rank for rank, idx in enumerate(keyword_indices)}
        else:
            keyword_ranks = {}
            
        # 4. Reciprocal Rank Fusion (RRF)
        k = 60
        combined_scores = {}
        all_candidate_indices = set(semantic_ranks.keys()) | set(keyword_ranks.keys())
        
        for idx in all_candidate_indices:
            score = 0
            if idx in semantic_ranks:
                score += 1.0 / (k + semantic_ranks[idx])
            if idx in keyword_ranks:
                score += 1.0 / (k + keyword_ranks[idx])
            combined_scores[idx] = score
            
        # 5. Top-K
        top_indices = sorted(combined_scores.keys(), key=lambda i: combined_scores[i], reverse=True)[:n_results]
        
        final_docs = [self.metadata_store[i]["content"] for i in top_indices]
        final_metadatas = [self.metadata_store[i] for i in top_indices]
        
        # Live console output print logs
        print("\n" + "="*80)
        print(f"HYBRID RETRIEVAL LATEST: Query: '{query_text}' | Allowed Events Filter Count: {len(allowed_event_ids) if allowed_event_ids else 'All'}")
        print(f"Retrieved Top {len(top_indices)} (requested {n_results}) Chunks:")
        print("-"*80)
        for rank, idx in enumerate(top_indices):
            meta = self.metadata_store[idx]
            rrf_score = combined_scores[idx]
            snippet = meta['content'][:120].replace('\n', ' ')
            title = meta.get('title', 'Unknown Title')
            location = meta.get('location', 'General')
            print(f"[{rank + 1}] Score: {rrf_score:.4f} | {title} ({location})")
            print(f"    Snippet: {snippet}...")
        print("="*80 + "\n")

        return {
            "documents": [final_docs],
            "metadatas": [final_metadatas]
        }
