# # vector_db/insert_vectors.py
# import os
# import json
# import uuid
# from typing import List, Dict
# from dotenv import load_dotenv
# from sentence_transformers import SentenceTransformer
# import numpy as np
# import faiss
# from azure.cosmos import CosmosClient
# from datetime import datetime

# load_dotenv()

# # Config from .env
# COSMOS_URI = os.getenv("COSMOS_VECTOR_URI") or os.getenv("COSMOS_CONN_STRING")
# COSMOS_KEY = os.getenv("COSMOS_VECTOR_KEY") or os.getenv("COSMOS_CONN_STRING")
# DB_NAME = os.getenv("COSMOS_DATABASE", "quickbite")
# VECTOR_CONTAINER = os.getenv("VECTOR_CONTAINER", "vector_embeddings")

# # Local index files
# INDEX_PATH = os.path.join("vector_db", "faiss_index.idx")
# META_PATH = os.path.join("vector_db", "faiss_meta.json")
# EMB_DIM = 384  # all-MiniLM-L6-v2 has 384 dims

# MODEL_NAME = "all-MiniLM-L6-v2"

# # Local data paths (adjust if your files are elsewhere)
# RESTAURANTS_FILE = os.path.join("..", "restaurants_synthetic.json")
# MENUS_FILE = os.path.join("..", "menus_synthetic.json")

# def load_json(path):
#     with open(path, "r", encoding="utf-8") as f:
#         return json.load(f)

# def connect_cosmos():
#     if not COSMOS_URI or not COSMOS_KEY:
#         raise Exception("Missing Cosmos vector URI/key in .env")
#     client = CosmosClient(COSMOS_URI, credential=COSMOS_KEY)
#     db = client.get_database_client(DB_NAME)
#     container = db.get_container_client(VECTOR_CONTAINER)
#     return container

# def create_text_for_restaurant(r: Dict) -> str:
#     return f"{r.get('name','')}. Cuisine: {r.get('cuisine','')}. Rating: {r.get('rating','')}."

# def create_text_for_menu_item(m: Dict, restaurant_lookup: Dict) -> str:
#     rest = restaurant_lookup.get(m.get("restaurant_id"), {})
#     return f"{m.get('name','')} from {rest.get('name','')}. Price: {m.get('price','')}. Item id: {m.get('id')}."

# def build_embeddings_and_index(interval_print=100):
#     print("Loading model:", MODEL_NAME)
#     model = SentenceTransformer(MODEL_NAME)

#     restaurants = load_json(RESTAURANTS_FILE)
#     menus = load_json(MENUS_FILE)

#     # build restaurant lookup
#     rest_lookup = {r["id"]: r for r in restaurants}

#     docs = []
#     # Add restaurant docs
#     for r in restaurants:
#         docs.append({
#             "doc_id": r["id"],
#             "type": "restaurant",
#             "text": create_text_for_restaurant(r),
#             "payload": r
#         })
#     # Add menu docs
#     for m in menus:
#         docs.append({
#             "doc_id": m["id"],
#             "type": "menu_item",
#             "text": create_text_for_menu_item(m, rest_lookup),
#             "payload": m
#         })

#     texts = [d["text"] for d in docs]
#     print(f"Encoding {len(texts)} documents...")
#     embeddings = model.encode(texts, convert_to_numpy=True, show_progress_bar=True)

#     # normalize embeddings (optional, helps with cosine using inner product)
#     faiss.normalize_L2(embeddings)

#     # create faiss index
#     index = faiss.IndexFlatIP(EMB_DIM)  # inner product over normalized vectors = cosine similarity
#     index.add(embeddings)
#     print(f"FAISS index: added {index.ntotal} vectors")

#     # Save index and metadata
#     os.makedirs("vector_db", exist_ok=True)
#     faiss.write_index(index, INDEX_PATH)
#     print(f"Saved FAISS index to {INDEX_PATH}")

#     meta = []
#     for i, d in enumerate(docs):
#         meta.append({
#             "index": i,
#             "doc_id": d["doc_id"],
#             "type": d["type"],
#             "text": d["text"],
#             "payload": d["payload"]
#         })
#     with open(META_PATH, "w", encoding="utf-8") as f:
#         json.dump(meta, f, ensure_ascii=False, indent=2)
#     print(f"Saved metadata to {META_PATH}")

#     # Save vectors + metadata to Cosmos (so container has embeddings too)
#     container = connect_cosmos()
#     print("Uploading documents to Cosmos container (vector field included). This may take a while...")
#     for i, d in enumerate(meta):
#         item = {
#             "id": d["doc_id"],         # use original id as cosmos id
#             "pk": d["type"],          # partition key field
#             "type": d["type"],
#             "text": d["text"],
#             "payload": d["payload"],
#             "embedding": embeddings[i].tolist(),
#             "indexed_at": datetime.utcnow().isoformat()
#         }
#         # upsert to avoid duplicates
#         container.upsert_item(item)
#         if (i + 1) % interval_print == 0:
#             print(f"  uploaded {i+1}/{len(meta)}")
#     print("✅ Finished uploading to Cosmos.")

#     return INDEX_PATH, META_PATH

# if __name__ == "__main__":
#     build_embeddings_and_index()

import os
from dotenv import load_dotenv
from azure.cosmos import CosmosClient
from sentence_transformers import SentenceTransformer

# -----------------------------------------------------------
# Load environment variables
# -----------------------------------------------------------
load_dotenv()

COSMOS_CONN = os.getenv("COSMOS_CONN_STRING")
DB_NAME = os.getenv("COSMOS_DATABASE", "quickbite")
CONTAINER_NAME = "menus"   # 👈 Targeting menus container

# -----------------------------------------------------------
# Initialize clients
# -----------------------------------------------------------
client = CosmosClient.from_connection_string(COSMOS_CONN)
container = client.get_database_client(DB_NAME).get_container_client(CONTAINER_NAME)

model = SentenceTransformer("all-MiniLM-L6-v2")
print("✅ Model loaded for menu embeddings")

# -----------------------------------------------------------
# Create and store embeddings
# -----------------------------------------------------------
items = list(container.read_all_items())
print(f"📦 Found {len(items)} menu items")

for item in items:
    text = f"{item.get('item_name', '')} {item.get('category', '')}"
    if not text.strip():
        continue

    embedding = model.encode(text).tolist()
    item["vector_embeddings"] = embedding
    container.upsert_item(item)
    print(f"✅ Added embedding for: {item.get('item_name')}")

print("\n🎯 All menu embeddings added successfully!")


