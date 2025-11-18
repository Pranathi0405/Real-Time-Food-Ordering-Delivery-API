import os
from azure.cosmos import CosmosClient
from dotenv import load_dotenv

load_dotenv()  # loads values from your .env or local.settings.json if used manually

COSMOS_CONN = os.getenv("COSMOS_CONN_STRING")

try:
    # Connect
    client = CosmosClient.from_connection_string(COSMOS_CONN)
    db = client.get_database_client("quickbite")

    print("✅ Connected to database:", db.database_link)

    # List containers
    for c in db.list_containers():
        print("📦 Container:", c['id'])

    # Check if orders container is accessible
    orders = db.get_container_client("orders")
    items = list(orders.query_items("SELECT TOP 1 * FROM c", enable_cross_partition_query=True))
    print("🔍 Found item sample:", items[0] if items else "No data found (but connection is OK)")

except Exception as e:
    print("❌ Cosmos DB connection failed:", e)
