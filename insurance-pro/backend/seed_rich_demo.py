import os
import sys
import uuid
from datetime import datetime, date, timezone
from supabase import create_client

URL = "https://sjokskemaonnvbqlnbdz.supabase.co"
KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InNqb2tza2VtYW9ubnZicWxuYmR6Iiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc5MjQ4MDc5NCwiZXhwIjoyMTA4MDU2Nzk0fQ.BSVy6BNE_yh1V2wJ303VM9hyQ18OarklvJSXg3LqcKY"

sb = create_client(URL, KEY)
BUCKET = "claim-evidence"

DEMO_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "demo_evidence"))
print("Demo dir:", DEMO_DIR)

def upload_file_if_missing(local_filename, storage_path, content_type="image/jpeg"):
    local_path = os.path.join(DEMO_DIR, local_filename)
    if not os.path.exists(local_path):
        print(f"Local file {local_path} not found")
        return False
    with open(local_path, "rb") as f:
        file_bytes = f.read()
    try:
        sb.storage.from_(BUCKET).upload(
            storage_path,
            file_bytes,
            file_options={"content-type": content_type, "upsert": "true"}
        )
        print(f"Uploaded: {storage_path}")
        return True
    except Exception as e:
        print(f"Upload error for {storage_path}: {e}")
        return False

# 1. Check or create abhirammukkamala+cust@gmail.com in auth and profiles
try:
    users_resp = sb.auth.admin.list_users()
    users = users_resp if isinstance(users_resp, list) else getattr(users_resp, "users", [])
    cust_user = next((u for u in users if u.email == "abhirammukkamala+cust@gmail.com"), None)
    if not cust_user:
        print("Creating abhirammukkamala+cust@gmail.com in Supabase Auth...")
        created = sb.auth.admin.create_user({
            "email": "abhirammukkamala+cust@gmail.com",
            "password": "ClaimPilot@2026",
            "email_confirm": True,
            "user_metadata": {"full_name": "Abhiram Mukkamala", "role": "customer"}
        })
        cust_id = created.user.id if hasattr(created, "user") else created["id"]
        print("Created user:", cust_id)
        # Ensure profile exists
        sb.table("profiles").upsert({
            "id": cust_id,
            "full_name": "Abhiram Mukkamala",
            "email": "abhirammukkamala+cust@gmail.com",
            "phone_number": "7420898829",
            "dob": "1998-05-15",
            "role": "customer",
            "is_email_verified": True,
            "is_phone_verified": True
        }).execute()
        print("Profile created for +cust")
    else:
        cust_id = cust_user.id
        print("Existing +cust user ID:", cust_id)
except Exception as e:
    print("Error checking/creating +cust user:", e)
    cust_id = None

# User IDs to populate
CUSTOMER_ABHIRAM = "360ab566-79e3-4c35-85c1-2bab7d33ec7e"
CUSTOMER_DEMO = "d55a6818-b451-4c70-8050-22dddf33bc2b"
AGENT_ABHIRAM = "593c12b2-cae9-4f39-9989-ddae9dda3ccc"

target_customer_ids = [CUSTOMER_ABHIRAM, CUSTOMER_DEMO]
if cust_id and cust_id not in target_customer_ids:
    target_customer_ids.append(cust_id)

# 2. Upload sample documents and photos for all customer IDs
for uid in target_customer_ids:
    upload_file_if_missing("pkg1_dl_abhiram.jpg", f"evidence/dl_front/{uid}/pkg1_dl_abhiram.jpg")
    upload_file_if_missing("pkg1_rc_honda_city.jpg", f"evidence/dl_back/{uid}/pkg1_rc_honda_city.jpg")
    upload_file_if_missing("set1_minor_bumper_scuff.jpg", f"evidence/photo/{uid}/set1_minor_bumper_scuff.jpg")
    upload_file_if_missing("set2_moderate_door_crease.jpg", f"evidence/photo/{uid}/set2_moderate_door_crease.jpg")
    upload_file_if_missing("set3_severe_lamp_collision.jpg", f"evidence/photo/{uid}/set3_severe_lamp_collision.jpg")

print("Storage uploads complete.")
