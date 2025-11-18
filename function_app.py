import azure.functions as func
import logging
import json
import os
import random
import time
import threading
from azure.cosmos import CosmosClient
from azure.messaging.webpubsubservice import WebPubSubServiceClient
from dotenv import load_dotenv

# ----------------------------------------------------
# Load environment and setup logging
# ----------------------------------------------------
load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

# ----------------------------------------------------
# Initialize Azure Function App (New v2 Model)
# ----------------------------------------------------
app = func.FunctionApp()

# ----------------------------------------------------
# Environment Variables
# ----------------------------------------------------
COSMOS_CONN = os.getenv("COSMOS_CONN_STRING")
COSMOS_DATABASE = os.getenv("COSMOS_DATABASE", "quickbite")
COSMOS_CONTAINER = os.getenv("COSMOS_CONTAINER", "orders")
WEB_PUBSUB_CONN = os.getenv("WEBPUBSUB_CONN_STRING")
HUB_NAME = os.getenv("WEBPUBSUB_HUB", "order-updates")

# ----------------------------------------------------
# Helper Functions
# ----------------------------------------------------
def get_cosmos():
    """Return Cosmos DB containers for orders and riders."""
    client = CosmosClient.from_connection_string(COSMOS_CONN)
    db = client.get_database_client(COSMOS_DATABASE)
    orders = db.get_container_client(COSMOS_CONTAINER)
    riders = db.get_container_client("riders")
    return orders, riders


def broadcast_update(service, order, status_text):
    """Send live updates to WebPubSub clients."""
    order["status"] = status_text
    payload = {
        "order_id": order.get("id"),
        "rider": order.get("rider_name", "N/A"),
        "status": order["status"],
        "eta": order.get("eta", "—"),
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    service.send_to_all(json.dumps(payload), content_type="application/json")
    logging.info(f"📡 Broadcasted update: {payload}")


def simulate_realtime_flow(order, orders_container, riders_container, service):
    """Simulate order lifecycle for live updates."""
    try:
        stages = [
            ("Order Placed ✅", 10),
            ("Preparing your order 👨‍🍳", 30),
            ("Out for delivery 🚴‍♂️", 50),
            ("Delivered 🎉", 20),
        ]

        for status, delay in stages:
            broadcast_update(service, order, status)
            order["status"] = status
            orders_container.upsert_item(order)
            logging.info("⏱ Waiting before next update...")
            time.sleep(delay)

    except Exception as e:
        logging.error(f"❌ simulate_realtime_flow() failed: {e}")
        
# ----------------------------------------------------
# 💥 Function 1: Service Bus Queue Trigger - Process New Order
# ----------------------------------------------------
@app.function_name(name="process_order")
@app.service_bus_queue_trigger(
    arg_name="msg",
    queue_name="%QUEUE_NAME%",
    connection="SERVICEBUS_CONN_STRING"
)
def process_order(msg: func.ServiceBusMessage):
    logging.info("📩 process_order() triggered - New order received from Service Bus queue")

    try:
        # Decode the order data
        raw_body = msg.get_body().decode("utf-8")
        order = json.loads(raw_body)
        logging.info(f"🆕 Decoded order: {order}")

        # Generate order ID if missing
        if "id" not in order:
            order["id"] = f"order-{int(time.time())}-{random.randint(1000, 9999)}"

        # Connect to Cosmos DB
        orders_container, riders_container = get_cosmos()

        # Assign available rider
        query = "SELECT * FROM r WHERE r.is_available = true"
        available_riders = list(riders_container.query_items(query=query, enable_cross_partition_query=True))

        if available_riders:
            rider = random.choice(available_riders)
            order["rider_id"] = rider.get("id")
            order["rider_name"] = rider.get("name", "Unknown")
            order["rider_phone"] = rider.get("phone", "N/A")
            order["rider_vehicle"] = rider.get("vehicle", "Bike")

            # Status stays the same forever (your requirement)
            order["status"] = "Rider Assigned"

            order["eta"] = f"{random.randint(20, 40)} mins"

            # rider["status"] = "Unavailable"      
            rider["status"] = "Assigned"
            rider["is_available"] = False
            riders_container.upsert_item(rider)
        else:
            order["rider_name"] = "Pending"
            order["status"] = "Pending Rider"
            order["eta"] = "TBD"

        # Save the initial order
        orders_container.upsert_item(order)
        logging.info(f"✅ Order {order['id']} saved successfully in Cosmos DB")

        # Publish event to Service Bus Topic (Logic App)
        publish_notification_event(order)

        # Initial Web PubSub notification
        try:
            service = WebPubSubServiceClient.from_connection_string(WEB_PUBSUB_CONN, hub=HUB_NAME)
        except Exception as e:
            logging.warning(f"⚠️ WebPubSub init failed: {e}")
            service = None

        # ----------------------------------------------------
        # ⭐ SIMPLE MESSAGE-ONLY SIMULATION (Status never changes)
        # ----------------------------------------------------
        messages = [
            "Order placed successfully",
            "Preparing your food 👨‍🍳",
            "Out for delivery 🚴‍♂️",
            "Delivered 🎉"
        ]

        delays = [5, 10, 10, 5]  # seconds

        for msg_text, wait in zip(messages, delays):
            order["message"] = msg_text
            order["updated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")

            # Update Cosmos DB
            orders_container.upsert_item(order)

            # Live broadcast
            if service:
                try:
                    service.send_to_all(json.dumps(order))
                except:
                    pass

            logging.info(f"➡️ Message updated: {msg_text}")
            time.sleep(wait)

        logging.info("🎉 Message lifecycle simulation completed")

    except Exception as e:
        logging.error(f"❌ Error in process_order(): {e}", exc_info=True)


# ----------------------------------------------------
# 💬 Function 2: Service Bus Topic Trigger - Customer Updates
# ----------------------------------------------------
@app.function_name(name="process_customer_updates")
@app.service_bus_topic_trigger(
    arg_name="msg",
    topic_name="notifications-topic",
    subscription_name="customer-updates",
    connection="SERVICEBUS_CONN_STRING"
)
def process_customer_updates(msg: func.ServiceBusMessage):
    logging.info("📩 process_customer_updates() triggered from notifications-topic/customer-updates")

    try:
        # Decode the Service Bus message
        raw_body = msg.get_body().decode("utf-8")
        update_data = json.loads(raw_body)
        logging.info(f"🔔 Received customer update: {update_data}")

        # Connect to Cosmos DB
        orders_container, riders_container = get_cosmos()

        if "order_id" in update_data:
            order_id = update_data["order_id"]
            new_status = update_data.get("status", "Unknown")
            message_text = update_data.get("message", "No message provided")

            # Find the order in Cosmos DB
            query = f"SELECT * FROM o WHERE o.id = '{order_id}'"
            items = list(orders_container.query_items(query=query, enable_cross_partition_query=True))

            if items:
                order = items[0]
                order["status"] = new_status
                order["last_update_message"] = message_text
                orders_container.upsert_item(order)
                logging.info(f"✅ Order {order_id} updated to status: {new_status}")
            else:
                logging.warning(f"⚠️ No matching order found for ID: {order_id}")
        else:
            logging.warning("⚠️ Incoming message missing 'order_id' field")

        # ----------------------------------------------------
        # 🔔 Send real-time WebPubSub broadcast
        # ----------------------------------------------------
        try:
            service = WebPubSubServiceClient.from_connection_string(WEB_PUBSUB_CONN, hub=HUB_NAME)
            notification = {
                "type": "customer_update",
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                "update_data": update_data
            }
            service.send_to_all(json.dumps(notification))
            logging.info("📡 Real-time update broadcasted successfully via WebPubSub")
        except Exception as e:
            logging.error(f"⚠️ WebPubSub broadcast failed: {e}")

    except Exception as e:
        logging.error(f"❌ Error in process_customer_updates: {e}", exc_info=True)
        
        
        
        
        
# ----------------------------------------------------
# 🔄 Function 3: Reset Rider Status (Timer Trigger)
# ----------------------------------------------------
@app.function_name(name="reset_riders_status")
@app.schedule(
    schedule="0 */3 * * * *",  # Every 3 minutes
    arg_name="mytimer",
    run_on_startup=False,
    use_monitor=True
)
def reset_riders_status(mytimer: func.TimerRequest):
    logging.info("🔄 reset_riders_status() triggered")

    try:
        orders_container, riders_container = get_cosmos()

        # Find all riders currently marked unavailable/assigned (is_available = false)
        query = "SELECT * FROM r WHERE r.is_available = false"
        busy_riders = list(
            riders_container.query_items(
                query=query,
                enable_cross_partition_query=True
            )
        )

        for rider in busy_riders:
            # Normalize back to idle + available
            rider["status"] = "Idle"
            rider["is_available"] = True
            riders_container.upsert_item(rider)

        logging.info(f"✅ Reset {len(busy_riders)} riders to Idle + is_available=True")

    except Exception as e:
        logging.error(f"❌ Error in reset_riders_status: {e}", exc_info=True)



# ----------------------------------------------------
# 📢 Publish Notification Event (Function → Service Bus Topic → Logic App)
# ----------------------------------------------------
from azure.servicebus import ServiceBusClient, ServiceBusMessage
import json, os, logging

def publish_notification_event(order):
    """
    Publishes an order update message to the Service Bus Topic so that
    the Logic App (notifications-topic/customer-updates) can process it
    and send email notifications to the customer and restaurant.
    """
    try:
        connection_str = os.getenv("SERVICEBUS_CONN_STRING")
        topic_name = "notifications-topic"

        # Construct message payload
        message_payload = {
            "order_id": order.get("id"),
            "customer_name": order.get("customer_name", "Valued Customer"),
            "customer_email": order.get("customer_email", "test@example.com"),  # ✅ corrected key
            "restaurant_email": order.get("restaurant_email", "quickbite.restaurant@example.com"),
            "status": order.get("status", "Order Placed"),
            "message": order.get("message", "Your order has been received successfully!"),
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
        }

        # Send the message to the Service Bus topic
        with ServiceBusClient.from_connection_string(connection_str) as client:
            sender = client.get_topic_sender(topic_name)
            message = ServiceBusMessage(
                body=json.dumps(message_payload).encode("utf-8"),
                content_type="application/json",
                application_properties={"status": message_payload["status"]}
            )

            sender.send_messages(message)

        logging.info(f"📨 Notification event published for Order {order['id']} to topic '{topic_name}'")

    except Exception as e:
        logging.error(f"❌ Failed to publish notification event: {e}", exc_info=True)


# def publish_notification_event(order):
#     try:
#         connection_str = os.getenv("SERVICEBUS_CONN_STRING")
#         topic_name = "notifications-topic"

#         message_payload = {
#             "order_id": order.get("id"),
#             "customer_email": order.get("customer_email"),
#             "restaurant_email": order.get("restaurant_email"),
#             "order_status": order.get("status"),
#             "order_message": order.get("message", "Your order has been received"),
#             "customer_name": order.get("customer_name", "Customer"),
#             "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
#         }

#         with ServiceBusClient.from_connection_string(connection_str) as client:
#             sender = client.get_topic_sender(topic_name)
#             message = ServiceBusMessage(
#                 body=json.dumps(message_payload).encode("utf-8"),
#                 content_type="application/json",
#                 application_properties={"order_status": message_payload["order_status"]}
#             )
#             sender.send_messages(message)

#         logging.info(f"📨 Notification event published for Order {order['id']} to topic '{topic_name}'")

#     except Exception as e:
#         logging.error(f"❌ Failed to publish notification event: {e}", exc_info=True)

