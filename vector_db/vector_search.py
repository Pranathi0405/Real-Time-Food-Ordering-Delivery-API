# # vector_db/vector_search.py
# import os
# import json
# from dotenv import load_dotenv
# from sentence_transformers import SentenceTransformer
# import numpy as np
# import faiss

# load_dotenv()

# INDEX_PATH = os.path.join("vector_db", "faiss_index.idx")
# META_PATH = os.path.join("vector_db", "faiss_meta.json")
# MODEL_NAME = "all-MiniLM-L6-v2"
# EMB_DIM = 384

# class VectorSearcher:
#     def __init__(self):
#         if not os.path.exists(INDEX_PATH) or not os.path.exists(META_PATH):
#             raise FileNotFoundError("FAISS index or metadata missing. Run insert_vectors.py first to build index.")
#         self.model = SentenceTransformer(MODEL_NAME)
#         self.index = faiss.read_index(INDEX_PATH)
#         with open(META_PATH, "r", encoding="utf-8") as f:
#             self.meta = json.load(f)
#         # build a mapping from index -> meta
#         self.index_to_meta = {m["index"]: m for m in self.meta}

#     def _embed(self, text: str):
#         v = self.model.encode([text], convert_to_numpy=True)
#         faiss.normalize_L2(v)
#         return v

#     def search(self, query: str, top_k: int = 5):
#         vec = self._embed(query)
#         D, I = self.index.search(vec, top_k)
#         results = []
#         for score, idx in zip(D[0], I[0]):
#             if idx == -1:
#                 continue
#             m = self.index_to_meta.get(int(idx))
#             results.append({
#                 "score": float(score),
#                 "doc_id": m["doc_id"],
#                 "type": m["type"],
#                 "text": m["text"],
#                 "payload": m["payload"]
#             })
#         return results

# if __name__ == "__main__":
#     qs = VectorSearcher()
#     q = input("Query: ")
#     print(qs.search(q, top_k=5))


# -----------------------------------------------------------
# vector_db/vector_search.py
# -----------------------------------------------------------
# 🔍 Standalone Vector Search using CosmosDB embeddings
# -----------------------------------------------------------

# -----------------------------------------------------------
# vector_db/vector_search.py
# -----------------------------------------------------------
# 🔍 Standalone Vector Search using CosmosDB embeddings
# -----------------------------------------------------------

# -----------------------------------------------------------
# vector_db/vector_search.py
# -----------------------------------------------------------
# 🔍 Combined Vector Search: Menus + Restaurants (CosmosDB)
# If no restaurant name exists, fill with famous Indian ones.
# -----------------------------------------------------------

# -----------------------------------------------------------
# vector_db/vector_search.py
# -----------------------------------------------------------
# 🍽️ Smart Vector Search for Menus
# Always returns type: Menu + restaurant (auto-fills if missing)
# Randomly picks multiple relevant results based on query
# -----------------------------------------------------------

import os
import json
import numpy as np
import random
from dotenv import load_dotenv
from sentence_transformers import SentenceTransformer
from azure.cosmos import CosmosClient

# -----------------------------------------------------------
# 1️⃣ Load environment
# -----------------------------------------------------------
load_dotenv()
COSMOS_CONN = os.getenv("COSMOS_CONN_STRING")
DB_NAME = os.getenv("COSMOS_DATABASE", "quickbite")
MENUS_CONTAINER = "menus"

# -----------------------------------------------------------
# 2️⃣ Initialize model & Cosmos client
# -----------------------------------------------------------
print("🔗 Connecting to Cosmos DB...")
client = CosmosClient.from_connection_string(COSMOS_CONN)
container = client.get_database_client(DB_NAME).get_container_client(MENUS_CONTAINER)

model = SentenceTransformer("all-MiniLM-L6-v2")
print("✅ SentenceTransformer model loaded successfully!")

# -----------------------------------------------------------
# 3️⃣ Famous restaurant fallback names (by category)
# -----------------------------------------------------------
FAMOUS_RESTAURANTS = {
    "biryani": [
        "Paradise Biryani", "Bawarchi", "Behrouz Biryani", "Mehfil", "Pista House", "Shah Ghouse"
    ],
    "pizza": [
        "Domino's Pizza", "Pizza Hut", "La Pinoz Pizza", "Oven Story Pizza", "Chicago Pizza"
    ],
    "burger": [
        "Burger King", "McDonald's", "Biggies Burger", "Wat-a-Burger"
    ],
    "dessert": [
        "Cream Stone", "Naturals Ice Cream", "Theobroma", "Häagen-Dazs", "CakeZone", "Frozen Bottle"
    ],
    "chocolate": [
        "Theobroma", "Chocolate Room", "Smoor Chocolates", "Hershey’s Café", "Ferrero Lounge"
    ],
    "default": [
        "Zomato Star Outlet", "Swiggy Partner Restaurant", "Urban Tadka", "Chef’s Choice", "Food Fusion Hub"
    ]
}

# -----------------------------------------------------------
# 4️⃣ Cosine Similarity Function
# -----------------------------------------------------------
def cosine_similarity(vec1, vec2):
    return np.dot(vec1, vec2) / (np.linalg.norm(vec1) * np.linalg.norm(vec2))

# -----------------------------------------------------------
# 5️⃣ Vector Search Function
# -----------------------------------------------------------
def vector_search(query: str, top_k: int = 15):
    """Perform vector-based semantic search on menu items"""
    query_vec = model.encode(query).tolist()
    results = []

    # Detect query type for fallback
    query_lower = query.lower()
    query_type = "default"
    for key in FAMOUS_RESTAURANTS.keys():
        if key in query_lower:
            query_type = key
            break

    # Read all items from Cosmos DB
    items = list(container.read_all_items())

    for item in items:
        if "vector_embeddings" not in item:
            continue
        doc_vec = np.array(item["vector_embeddings"], dtype=np.float32)
        sim = cosine_similarity(np.array(query_vec, dtype=np.float32), doc_vec)

        # Assign or auto-fill restaurant name
        restaurant_name = item.get("restaurant_name")
        if not restaurant_name:
            restaurant_name = random.choice(FAMOUS_RESTAURANTS[query_type])

        # Build result
        results.append({
            "type": "Menu",
            "restaurant": restaurant_name,
            "menu_item": item.get("item_name", "Unknown Dish"),
            "similarity": round(float(sim), 3)
        })

    # Sort by similarity
    results.sort(key=lambda x: x["similarity"], reverse=True)

    # Pick a random count of results (8–15)
    random_count = random.randint(8, 15)
    return results[:random_count]

# -----------------------------------------------------------
# 6️⃣ Run standalone
# -----------------------------------------------------------
if __name__ == "__main__":
    query = input("🔍 Enter search query: ")
    results = vector_search(query)

    print("\n🎯 Recommended Menus:\n")
    print(json.dumps(results, indent=2, ensure_ascii=False))

