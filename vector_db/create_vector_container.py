# # vector_db/create_vector_container.py
# import os
# from dotenv import load_dotenv
# from azure.cosmos import CosmosClient, PartitionKey, exceptions

# load_dotenv()

# COSMOS_URI = os.getenv("COSMOS_VECTOR_URI") or os.getenv("COSMOS_CONN_STRING")
# COSMOS_KEY = os.getenv("COSMOS_VECTOR_KEY") or os.getenv("COSMOS_CONN_STRING")
# DB_NAME = os.getenv("COSMOS_DATABASE", "quickbite")
# VECTOR_CONTAINER = os.getenv("VECTOR_CONTAINER", "vector_embeddings")
# PARTITION_KEY = "/pk"  # we'll store a 'pk' field in each document

# def ensure_container():
#     if not COSMOS_URI or not COSMOS_KEY:
#         raise Exception("Missing COSMOS_VECTOR_URI or COSMOS_VECTOR_KEY in .env")

#     client = CosmosClient(COSMOS_URI, credential=COSMOS_KEY)
#     try:
#         db = client.create_database_if_not_exists(id=DB_NAME)
#         container = db.create_container_if_not_exists(
#             id=VECTOR_CONTAINER,
#             partition_key=PartitionKey(path=PARTITION_KEY),
#             offer_throughput=400
#         )
#         print(f"✅ Ensured container: {VECTOR_CONTAINER} in DB: {DB_NAME}")
#         return container
#     except exceptions.CosmosHttpResponseError as ex:
#         raise RuntimeError(f"Cosmos error: {ex}")

# if __name__ == "__main__":
#     ensure_container()
