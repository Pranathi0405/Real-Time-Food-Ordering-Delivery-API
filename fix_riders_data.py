"""
fix_riders_data.py (FINAL VERSION FOR YOUR DATA)
-------------------------------------------------

✔ Converts your existing riders to the correct schema
✔ Adds missing fields
✔ Normalizes status values
✔ Ensures 'is_available' exists for all riders
✔ Saves updated riders back to Cosmos DB

Run:
    python fix_riders_data.py
"""

import os
from azure.cosmos import CosmosClient
from dotenv import load_dotenv

# Load .env
load_dotenv()

COSMOS_CONN_STRING = os.getenv("COSMOS_CONN_STRING")
if not COSMOS_CONN_STRING:
    raise RuntimeError("❌ Missing COSMOS_CONN_STRING")

client = CosmosClient.from_connection_string(COSMOS_CONN_STRING)
database_name = "quickbite"
container_name = "riders"

db = client.get_database_client(database_name)
riders_container = db.get_container_client(container_name)

print("✅ Connected to Cosmos DB")

# -----------------------------------------------------
# Normalize the status field based on your raw dataset
# -----------------------------------------------------
def normalize_status(raw_status: str):
    raw = raw_status.lower()

    if raw in ["busy", "offline"]:
        return "Idle"          # reset these to Idle
    if raw in ["available"]:
        return "Idle"          # still converted to Idle (initial state)

    return "Idle"


# -----------------------------------------------------
# Process all riders
# -----------------------------------------------------
updated = 0

for rider in riders_container.read_all_items():

    print(f"🔧 Fixing {rider['id']}...")

    # Normalize status
    rider["status"] = normalize_status(rider.get("status", ""))

    # Add availability flag
    rider["is_available"] = True

    # Save corrected rider
    riders_container.upsert_item(rider)
    updated += 1

print(f"\n🎉 DONE! Updated {updated} riders.")
print("✔ All riders now have: status='Idle', is_available=true")













# """
# fix_riders_data.py
# ------------------

# 🧹 Purpose:
# Cleans and validates the "riders" container in your Cosmos DB.
# Removes malformed documents that can cause 'dictionary update sequence' errors
# when your Azure Functions (process_order or reset_riders_status) run.

# 👩‍💻 Usage:
#     1️⃣ Make sure your .env file has COSMOS_CONN_STRING defined.
#     2️⃣ Run this in VS Code terminal:

#         python fix_riders_data.py

#     3️⃣ It will scan the container, count valid/invalid records,
#         and remove only broken ones.
# """

# import os
# import json
# from azure.cosmos import CosmosClient
# from dotenv import load_dotenv

# # ----------------------------------------------------
# # Load environment variables
# # ----------------------------------------------------
# load_dotenv()

# # ----------------------------------------------------
# # Connect to Cosmos DB
# # ----------------------------------------------------
# COSMOS_CONN_STRING = os.getenv("COSMOS_CONN_STRING")

# if not COSMOS_CONN_STRING:
#     raise RuntimeError("❌ Missing COSMOS_CONN_STRING in environment variables.")

# client = CosmosClient.from_connection_string(COSMOS_CONN_STRING)
# database_name = "quickbite"
# container_name = "riders"

# try:
#     db = client.get_database_client(database_name)
#     riders_container = db.get_container_client(container_name)
#     print(f"✅ Connected to Cosmos DB → Database: '{database_name}', Container: '{container_name}'")
# except Exception as e:
#     print(f"❌ Failed to connect to Cosmos DB: {e}")
#     exit(1)

# # ----------------------------------------------------
# # Validate and clean up malformed records
# # ----------------------------------------------------
# print("\n🔍 Checking rider records for invalid structures...")

# valid = 0
# invalid = 0

# try:
#     for item in riders_container.read_all_items():
#         # Step 1: Ensure item is a dictionary
#         if not isinstance(item, dict):
#             invalid += 1
#             print(f"⚠️ Non-dict record found: {item}")
#             continue

#         # Step 2: Ensure 'id' and 'name' fields exist
#         if "id" in item and "name" in item:
#             valid += 1
#         else:
#             invalid += 1
#             print(f"⚠️ Invalid record (missing id/name): {item}")
#             try:
#                 # Delete malformed record safely
#                 riders_container.delete_item(item, partition_key=item.get("id", None))
#                 print(f"🗑️ Deleted malformed record (no id or name).")
#             except Exception as e:
#                 print(f"❌ Error deleting malformed record: {e}")

# except Exception as e:
#     print(f"❌ Error scanning container: {e}")

# # ----------------------------------------------------
# # Summary
# # ----------------------------------------------------
# print(f"\n✅ Cleanup complete — {valid} valid records, {invalid} invalid records handled.")
# print("🚀 Your 'riders' container is now safe for Azure Functions.")
