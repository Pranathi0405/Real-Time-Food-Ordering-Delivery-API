import os
import json
import time
import random
import uuid
from datetime import datetime
from dotenv import load_dotenv
from azure.cosmos import CosmosClient, exceptions

# ---------------------------------------------------
# ✅ 1. Load Environment Variables
# ---------------------------------------------------
load_dotenv()
COSMOS_CONN = os.getenv("COSMOS_CONN_STRING")
DATABASE_NAME = os.getenv("COSMOS_DATABASE")
CONTAINER_NAME = os.getenv("COSMOS_CONTAINER")

if not COSMOS_CONN:
    raise Exception("❌ Missing Cosmos connection string in .env file")

# ---------------------------------------------------
# ✅ 2. Initialize Cosmos Client
# ---------------------------------------------------
client = CosmosClient.from_connection_string(COSMOS_CONN)
database = client.get_database_client(DATABASE_NAME)
orders_container = database.get_container_client(CONTAINER_NAME)

print(f"✅ Connected to Azure Cosmos DB — Database: {DATABASE_NAME}, Container: {CONTAINER_NAME}\n")

# ---------------------------------------------------
# ✅ 3. Sample Data for Random Generation
# ---------------------------------------------------
customers = ["Alice", "Bob", "Charlie", "David", "Ella"]
restaurants = [
    {"id": "REST001", "name": "Taco Town"},
    {"id": "REST002", "name": "Pizza Palace"},
    {"id": "REST003", "name": "Burger Barn"},
    {"id": "REST004", "name": "Sushi Stop"},
]

menu_items = [
    {"item_name": "Burger", "price": 120},
    {"item_name": "Pizza", "price": 200},
    {"item_name": "Tacos", "price": 100},
    {"item_name": "Pasta", "price": 150},
    {"item_name": "Sandwich", "price": 90},
]

statuses = ["Placed", "Preparing", "Ready", "Out for Delivery", "Delivered"]

# ---------------------------------------------------
# ✅ 4. Function to Generate a Valid Order Document
# ---------------------------------------------------
def generate_random_order():
    restaurant = random.choice(restaurants)
    customer = random.choice(customers)
    item_count = random.randint(1, 3)
    selected_items = random.sample(menu_items, item_count)
    total_price = sum(item["price"] for item in selected_items)

    # ✅ Must include `id` because partition key = /id
    new_order = {
        "id": str(uuid.uuid4()),  # partition key
        "order_id": "ORD" + str(random.randint(1000, 9999)),
        "restaurant_id": restaurant["id"],
        "restaurant_name": restaurant["name"],
        "customer_name": customer,
        "items": selected_items,
        "total_price": total_price,
        "status": random.choice(statuses),
        "created_at": datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat()
    }

    return new_order

# ---------------------------------------------------
# ✅ 5. Continuous Real-Time Order Generation
# ---------------------------------------------------
print("🚀 Starting real-time order generation (press Ctrl + C to stop)...\n")

log_file = "orders_log.txt"

try:
    while True:
        new_order = generate_random_order()

        # 🧾 Print order details to console
        print(f"🧾 New Order:\n{json.dumps(new_order, indent=2)}")

        # ✅ Insert into Cosmos DB
        orders_container.upsert_item(new_order)
        print(f"✅ Inserted order: {new_order['order_id']} at {datetime.now().strftime('%H:%M:%S')}\n")

        # 🗂️ Log to file
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(new_order, indent=2) + "\n\n")

        # Wait before generating next order (adjustable)
        time.sleep(5)  # ⏳ generates an order every 5 seconds

except KeyboardInterrupt:
    print("\n🛑 Real-time order generation stopped by user.\n")

except exceptions.CosmosHttpResponseError as e:
    print(f"❌ Cosmos DB Error: {e.message}")

except Exception as e:
    print(f"⚠️ Unexpected Error: {e}")
