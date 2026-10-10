"""
MCP Smart Router - Phase 4

Problem: If we send 1000 tools to LLM, we hit context limit.
Solution: Semantic search over tool descriptions. Only send relevant servers.

How it works:
1. For each MCP server, we create a document: "Server: Weather. Tools: get_weather - Get current weather..."
2. We embed that document with all-MiniLM-L6-v2 (runs locally on your M4, no API key)
3. User query "temperature in Delhi" is embedded same way
4. Cosine similarity finds best servers: Weather 0.30 > Time 0.09 > Calculator 0.03
5. We only send top 2 servers to LLM -> constant tokens

This is same pattern used by Qdrant, Pinecone, and production RAG systems.
"""

from sentence_transformers import SentenceTransformer, util
import torch

class MCPRouter:
    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        """
        Load embedding model locally. First run downloads ~80MB to ~/.cache
        all-MiniLM-L6-v2 is 384 dims, super fast on M4, perfect for routing.
        """
        print(f"Loading embedding model {model_name}... (first download ~80MB)")
        self.model = SentenceTransformer(model_name)
        self.server_docs = [] # List of {"script": path, "text": description, "embedding": tensor}
        self.embeddings = None

    def index_servers(self, servers_info: list):
        """
        servers_info: [{"script": "servers/weather_server.py", "tools": [MCPTool,...]},...]
        We build one searchable document per server.
        """
        docs = []
        for info in servers_info:
            script = info["script"]
            tools = info["tools"]
            # Combine server name + all tool descriptions into one document
            # This is what LLM will match against
            tool_text = " ".join([f"{t.name}: {t.description}" for t in tools])
            doc_text = f"Server {script} provides: {tool_text}"
            docs.append({"script": script, "text": doc_text})

        self.server_docs = docs
        # Encode all server docs at once -> tensor [num_servers, 384]
        texts = [d["text"] for d in docs]
        self.embeddings = self.model.encode(texts, convert_to_tensor=True, normalize_embeddings=True)
        print(f"[Router] Indexed {len(docs)} servers.")

    def route(self, query: str, top_k: int = 2, threshold: float = 0.0) -> list:
        """
        Given user query, return top_k most relevant server scripts.
        Returns list of (script_path, score) sorted by score desc.
        """
        print(f"\n[Router] Query: '{query}'")
        # Embed query -> [384]
        query_emb = self.model.encode(query, convert_to_tensor=True, normalize_embeddings=True)

        # Cosine similarity = dot product because normalized
        scores = util.cos_sim(query_emb, self.embeddings)[0] # [num_servers]

        # Pair scores with scripts
        scored = []
        for i, doc in enumerate(self.server_docs):
            scored.append((doc["script"], float(scores[i])))

        # Sort high -> low
        scored.sort(key=lambda x: x[1], reverse=True)

        for script, score in scored:
            print(f" - {script.split('/')[-1]:<25} score: {score:.3f}")

        # Return top_k
        selected = [s for s, _ in scored[:top_k]]
        print(f"[Router] Selected -> {selected}")
        return selected, scored