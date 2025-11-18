"""
🍔 QuickBite - Real-Time Food Ordering API
Fully functional FastAPI backend for all project phases.
------------------------------------------------------------
Features:
✅ POST /orders           → Reliable order ingestion (Service Bus)
✅ GET  /orders/{id}      → Fetch order status from Cosmos DB
✅ PUT  /orders/{id}/status → Update order status (for Functions / internal use)
✅ POST /telemetry        → Receive rider GPS/status updates
✅ GET  /search           → Vector / text search (no OpenAI)
✅ POST /upload           → Upload menu images or receipts
------------------------------------------------------------
Integrations:
- Cosmos DB (mycosmosdbproject)
- Service Bus (myservicebusproject)
- Web PubSub (quickbite-webpubsub)
- Blob Storage (myprojectstorage)
- Logic Apps (mylogicapp)
- Azure AI Search (vector db, no OpenAI)
"""

import os, uuid, json, requests, random
from datetime import datetime
from fastapi import FastAPI, HTTPException, UploadFile, File, Query
from fastapi.responses import JSONResponse
from azure.servicebus import ServiceBusClient, ServiceBusMessage
from azure.cosmos import CosmosClient
from azure.storage.blob import BlobServiceClient
from dotenv import load_dotenv
from pydantic import BaseModel
import time


# ---------------------------------------------------
# ✅ 1. Load Environment Variables
# ---------------------------------------------------
load_dotenv()

COSMOS_CONN = os.getenv("COSMOS_CONN_STRING")
DB_NAME = os.getenv("COSMOS_DATABASE", "quickbite")
ORDERS_CONTAINER = os.getenv("COSMOS_CONTAINER", "orders")

SERVICEBUS_CONN = os.getenv("SERVICEBUS_CONN_STRING")
QUEUE_NAME = os.getenv("QUEUE_NAME", "orders-queue")

BLOB_CONN = os.getenv("BLOB_CONN_STRING")  # optional for uploads
BLOB_CONTAINER = "menu-assets"

SEARCH_ENDPOINT = os.getenv("SEARCH_ENDPOINT")
SEARCH_KEY = os.getenv("SEARCH_KEY")
SEARCH_INDEX = os.getenv("SEARCH_INDEX", "quickbite-vector-index")

# ---------------------------------------------------
# ✅ 2. Initialize Clients
# ---------------------------------------------------
app = FastAPI(title="🍔 QuickBite API", version="2.0")

cosmos_client = CosmosClient.from_connection_string(COSMOS_CONN)
orders_container = cosmos_client.get_database_client(DB_NAME).get_container_client(ORDERS_CONTAINER)

blob_service = None
if BLOB_CONN:
    blob_service = BlobServiceClient.from_connection_string(BLOB_CONN)
    try:
        blob_service.create_container(BLOB_CONTAINER)
    except Exception:
        pass  # already exists

# ---------------------------------------------------
# ✅ 3. Data Models
# ---------------------------------------------------
class Item(BaseModel):
    item_name: str
    price: int

class OrderIn(BaseModel):
    restaurant_id: str
    restaurant_name: str
    customer_name: str
    customer_email: str
    items: list[Item]

class StatusUpdate(BaseModel):
    status: str

class TelemetryData(BaseModel):
    order_id: str
    rider_id: str
    location: dict

# ---------------------------------------------------
# ✅ 4. Utility Functions
# ---------------------------------------------------
def send_to_service_bus(payload: dict):
    """Push message to Azure Service Bus queue"""
    sb_client = ServiceBusClient.from_connection_string(SERVICEBUS_CONN)
    sender = sb_client.get_queue_sender(queue_name=QUEUE_NAME)
    with sender:
        sender.send_messages(ServiceBusMessage(json.dumps(payload)))

def find_order(order_id: str):
    """Query Cosmos DB for a given order_id"""
    query = "SELECT * FROM c WHERE c.order_id=@order_id"
    items = list(
        orders_container.query_items(
            query=query,
            parameters=[{"name": "@order_id", "value": order_id}],
            enable_cross_partition_query=True
        )
    )
    return items[0] if items else None


@app.post("/orders", status_code=202)
def place_order(order: OrderIn):
    """Customer places a new order → returns order_id immediately."""

    # Generate an order_id (same style as your function app)
    order_id = f"order-{int(time.time())}-{random.randint(1000, 9999)}"

    payload = {
        "id": order_id,                      # <-- This is the Cosmos DB id (pk)
        "restaurant_id": order.restaurant_id,
        "restaurant_name": order.restaurant_name,
        "customer_name": order.customer_name,
        "customer_email": order.customer_email,
        "items": [i.dict() for i in order.items],
    }

    try:
        # Send to Service Bus (Function App will process and save it)
        send_to_service_bus(payload)

        return {
            "message": "📨 Order sent to Service Bus successfully",
            "order_id": order_id,            # <-- Return THIS to user
            "status": "queued"
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"❌ Failed to queue order: {str(e)}"
        )


# ---- GET: Retrieve Order ----
@app.get("/orders/{order_id}")
def get_order(order_id: str):
    order = find_order(order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return order


# ---- FIX THIS ----
def find_order(order_id: str):
    try:
        # id == partition key, since pk = '/id'
        return orders_container.read_item(item=order_id, partition_key=order_id)
    except:
        return None


# ---- PUT: Update Order Status ----
@app.put("/orders/{order_id}/status")
def update_order_status(order_id: str, update: StatusUpdate):
    """Update order status (e.g., Preparing, Out for Delivery, Delivered)"""
    order = find_order(order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    order["status"] = update.status
    order["updated_at"] = datetime.utcnow().isoformat()
    orders_container.upsert_item(order)
    return {"message": f"✅ Order {order_id} updated to {update.status}"}

# ---- POST: Rider Telemetry Updates ----
@app.post("/telemetry")
def receive_telemetry(data: TelemetryData):
    """Rider sends location / delivery telemetry"""
    order = find_order(data.order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    telemetry = order.get("telemetry", [])
    telemetry.append({
        "rider_id": data.rider_id,
        "location": data.location,
        "timestamp": datetime.utcnow().isoformat()
    })
    order["telemetry"] = telemetry
    orders_container.upsert_item(order)
    return {"message": "✅ Telemetry updated"}

# ---- GET: Text / Vector Search ----
@app.get("/search")
def search_orders(q: str = Query(..., description="Search keyword or menu item")):
    """Search Cosmos-synced data using Azure Search text search"""
    try:
        headers = {"Content-Type": "application/json", "api-key": SEARCH_KEY}
        search_url = f"{SEARCH_ENDPOINT}/indexes/{SEARCH_INDEX}/docs/search?api-version=2023-11-01"
        payload = {"search": q, "top": 5}
        res = requests.post(search_url, headers=headers, json=payload)
        if res.status_code == 200:
            return res.json()
        else:
            raise HTTPException(status_code=500, detail=f"Search failed: {res.text}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ---- POST: Upload Menu / Receipt to Blob Storage ----
@app.post("/upload")
def upload_file(file: UploadFile = File(...)):
    """Upload menu images or invoices to Azure Blob Storage"""
    if not blob_service:
        raise HTTPException(status_code=500, detail="Blob connection not configured")
    try:
        blob_client = blob_service.get_blob_client(container=BLOB_CONTAINER, blob=file.filename)
        blob_client.upload_blob(file.file, overwrite=True)
        blob_url = blob_client.url
        return {"message": "✅ File uploaded", "url": blob_url}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Blob upload failed: {e}")

# ---- Root Health Check ----
@app.get("/")
def health_check():
    """Root health endpoint"""
    return {"status": "✅ QuickBite API running", "timestamp": datetime.utcnow().isoformat()}










