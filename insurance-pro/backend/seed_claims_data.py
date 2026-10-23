import os
import sys
import uuid
import json
from datetime import datetime, timezone
from supabase import create_client

URL = "https://sjokskemaonnvbqlnbdz.supabase.co"
KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InNqb2tza2VtYW9ubnZicWxuYmR6Iiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc5MjQ4MDc5NCwiZXhwIjoyMTA4MDU2Nzk0fQ.BSVy6BNE_yh1V2wJ303VM9hyQ18OarklvJSXg3LqcKY"

sb = create_client(URL, KEY)

AGENT_ID = "593c12b2-cae9-4f39-9989-ddae9dda3ccc" # abhirammukkamala+agent@gmail.com
USERS = [
    {
        "id": "360ab566-79e3-4c35-85c1-2bab7d33ec7e",
        "name": "Abhiram Mukkamala",
        "dl": "MH1220180012345",
        "claims_prefix": "CLM-2026-48",
    },
    {
        "id": "ca5fc58d-9cae-43ec-be58-be9f11ec001b",
        "name": "Abhiram Mukkamala",
        "dl": "MH1220180012345",
        "claims_prefix": "CLM-2026-78",
    },
    {
        "id": "d55a6818-b451-4c70-8050-22dddf33bc2b",
        "name": "ClaimPilot Demo Customer",
        "dl": "MH1420190098765",
        "claims_prefix": "CLM-2026-90",
    }
]

# Ensure agent_policies and policies map DEMO-POL-101, DEMO-POL-202, DEMO-POL-303, POL-M-992333 to AGENT_ID
policies_to_seed = [
    ("DEMO-POL-101", "Honda City 1.5 ZX (2023)"),
    ("DEMO-POL-202", "Hyundai Creta 1.5 SX(O) (2023)"),
    ("DEMO-POL-303", "Tata Nexon Fearless+ (2024)"),
    ("POL-M-992333", "Honda City")
]

for pol, veh in policies_to_seed:
    sb.table("agent_policies").upsert({
        "policy_number": pol,
        "agent_id": AGENT_ID
    }, on_conflict="policy_number").execute()
    sb.table("policies").upsert({
        "policy_number": pol,
        "assigned_agent_id": AGENT_ID,
        "customer_name": "Abhiram Mukkamala",
        "vehicle_model": veh
    }, on_conflict="policy_number").execute()

print("Policies seeded and assigned to agent:", AGENT_ID)

for user in USERS:
    uid = user["id"]
    name = user["name"]
    dl = user["dl"]
    pfx = user["claims_prefix"]
    print(f"\nProcessing user {name} ({uid})...")

    # Claim 1: Pending Review (The primary claim to review in the Agent Portal)
    c1_number = f"{pfx}292"
    c1_desc = "Reversing out of commercial parking bay, front bumper brushed against concrete pillar and headlamp cracked. Minor front-end impact."
    c1_resp = sb.table("claims").upsert({
        "claim_number": c1_number,
        "user_id": uid,
        "assigned_agent_id": AGENT_ID,
        "incident_type": "Accident",
        "vehicle_name": "Honda City 1.5 ZX (2023)",
        "policy_number": "DEMO-POL-101",
        "hsrp_number": "MH12AB9921",
        "engine_number": "IVTEC202388190",
        "chassis_number": "MAKHC239921880",
        "incident_date": "2026-10-22",
        "location_address": "Kharadi IT Park, Wing B Parking",
        "location_city": "Pune",
        "location_state": "Maharashtra",
        "pincode": "411014",
        "description": c1_desc,
        "driver_name": name,
        "driver_dl_number": dl,
        "claimed_amount": 47000.00,
        "approved_amount": 0.00,
        "status": "pending_review",
        "fraud_score": 12,
        "risk_level": "Low Risk"
    }, on_conflict="claim_number").execute()
    c1_id = c1_resp.data[0]["id"]
    print(f"  Claim 1 ({c1_number}) id: {c1_id}")

    # Evidence for Claim 1: DL Front, DL Back/RC, Damage Photos
    sb.table("claim_evidence").delete().eq("claim_id", c1_id).execute()
    evidence_c1 = [
        {
            "claim_id": c1_id,
            "file_url": f"evidence/dl_front/{uid}/pkg1_dl_abhiram.jpg",
            "storage_path": f"evidence/dl_front/{uid}/pkg1_dl_abhiram.jpg",
            "file_type": "image/jpeg",
            "category": "dl_front"
        },
        {
            "claim_id": c1_id,
            "file_url": f"evidence/dl_back/{uid}/pkg1_rc_honda_city.jpg",
            "storage_path": f"evidence/dl_back/{uid}/pkg1_rc_honda_city.jpg",
            "file_type": "image/jpeg",
            "category": "dl_back"
        },
        {
            "claim_id": c1_id,
            "file_url": f"evidence/photo/{uid}/set3_severe_lamp_collision.jpg",
            "storage_path": f"evidence/photo/{uid}/set3_severe_lamp_collision.jpg",
            "file_type": "image/jpeg",
            "category": "photo"
        },
        {
            "claim_id": c1_id,
            "file_url": f"evidence/photo/{uid}/set2_moderate_door_crease.jpg",
            "storage_path": f"evidence/photo/{uid}/set2_moderate_door_crease.jpg",
            "file_type": "image/jpeg",
            "category": "photo"
        }
    ]
    sb.table("claim_evidence").insert(evidence_c1).execute()

    # AI Analysis for Claim 1
    c1_damages = [
        {
            "id": "dmg_lamp_01",
            "part": "headlamp",
            "type": "Fracture & Assembly Dislocation",
            "damage_type": "Impact Fracture",
            "location": "Front Right Headlamp Assembly",
            "severity": "Severe",
            "confidence": 0.94,
            "area_ratio": 0.18,
            "boundingBox": {"x": 22.4, "y": 30.5, "width": 45.2, "height": 38.6},
            "repair_action": "OEM Assembly Replacement & Calibration",
            "estimated_cost": 24000.0,
            "estimated_cost_min": 21000.0,
            "estimated_cost_max": 26000.0
        },
        {
            "id": "dmg_bumper_02",
            "part": "front bumper",
            "type": "Tear & Mount Distortion",
            "damage_type": "Bumper Impact",
            "location": "Front Fascia / Lower Lip",
            "severity": "Moderate",
            "confidence": 0.89,
            "area_ratio": 0.24,
            "boundingBox": {"x": 15.0, "y": 55.0, "width": 62.0, "height": 32.0},
            "repair_action": "Plastic Welding, Tinkering & Primer Refinish",
            "estimated_cost": 16500.0,
            "estimated_cost_min": 14000.0,
            "estimated_cost_max": 19000.0
        },
        {
            "id": "dmg_fender_03",
            "part": "quarter panel / fender",
            "type": "Sheet Metal Crease",
            "damage_type": "Panel Deformation",
            "location": "Right Front Fender",
            "severity": "Minor",
            "confidence": 0.86,
            "area_ratio": 0.08,
            "boundingBox": {"x": 68.0, "y": 35.0, "width": 24.0, "height": 22.0},
            "repair_action": "Paintless Dent Repair (PDR)",
            "estimated_cost": 6500.0,
            "estimated_cost_min": 5000.0,
            "estimated_cost_max": 8000.0
        }
    ]
    sb.table("claim_ai_analysis").upsert({
        "claim_id": c1_id,
        "detected_damages": c1_damages,
        "estimated_cost_min": 40000.00,
        "estimated_cost_max": 53000.00,
        "fraud_flags": []
    }, on_conflict="claim_id").execute()
    print("  Claim 1 evidence & AI analysis seeded.")

    # Claim 2: High Risk Fraud Claim (For Fraud Detection Showcase)
    c2_number = f"{pfx}367"
    c2_resp = sb.table("claims").upsert({
        "claim_number": c2_number,
        "user_id": uid,
        "assigned_agent_id": AGENT_ID,
        "incident_type": "Accident",
        "vehicle_name": "Honda City",
        "policy_number": "DEMO-POL-101",
        "hsrp_number": "MH12AB9921",
        "engine_number": "IVTEC202388190",
        "chassis_number": "MAKHC239921880",
        "incident_date": "2026-10-18",
        "location_address": "Viman Nagar Road, Pune",
        "location_city": "Pune",
        "location_state": "Maharashtra",
        "pincode": "411014",
        "description": "Minor scratch on bumper while parallel parking in commercial lane.",
        "driver_name": name,
        "driver_dl_number": dl,
        "claimed_amount": 32000.00,
        "approved_amount": 0.00,
        "status": "under_review",
        "fraud_score": 88,
        "risk_level": "HIGH RISK"
    }, on_conflict="claim_number").execute()
    c2_id = c2_resp.data[0]["id"]
    print(f"  Claim 2 ({c2_number}) id: {c2_id}")

    sb.table("claim_evidence").delete().eq("claim_id", c2_id).execute()
    evidence_c2 = [
        {
            "claim_id": c2_id,
            "file_url": f"evidence/dl_front/{uid}/pkg1_dl_abhiram.jpg",
            "storage_path": f"evidence/dl_front/{uid}/pkg1_dl_abhiram.jpg",
            "file_type": "image/jpeg",
            "category": "dl_front"
        },
        {
            "claim_id": c2_id,
            "file_url": f"evidence/photo/{uid}/set1_minor_bumper_scuff.jpg",
            "storage_path": f"evidence/photo/{uid}/set1_minor_bumper_scuff.jpg",
            "file_type": "image/jpeg",
            "category": "photo"
        }
    ]
    sb.table("claim_evidence").insert(evidence_c2).execute()

    c2_damages = [
        {
            "id": "dmg_scuff_01",
            "part": "bumper",
            "type": "Superficial Scuff",
            "damage_type": "Surface Abrasion",
            "location": "Lower Bumper Apron",
            "severity": "Minor",
            "confidence": 0.95,
            "area_ratio": 0.04,
            "boundingBox": {"x": 30.0, "y": 60.0, "width": 35.0, "height": 18.0},
            "repair_action": "Rubbing, Polishing & Spot Paint",
            "estimated_cost": 3500.0,
            "estimated_cost_min": 2500.0,
            "estimated_cost_max": 4500.0
        }
    ]
    c2_fraud_flags = [
        "Duplicate photographic evidence detected across historical claims database (pHash distance: 1)",
        "Disproportionate claim amount: Claimed ₹32,000 for minor superficial abrasion valued under ₹4,500",
        "Metadata alert: Image EXIF creation timestamp does not align with reported incident time"
    ]
    sb.table("claim_ai_analysis").upsert({
        "claim_id": c2_id,
        "detected_damages": c2_damages,
        "estimated_cost_min": 2500.00,
        "estimated_cost_max": 4500.00,
        "fraud_flags": c2_fraud_flags
    }, on_conflict="claim_id").execute()
    print("  Claim 2 fraud evidence seeded.")

    # Claim 3: Settled Claim (Clean Historical Settlement Showcase)
    c3_number = f"{pfx}847"
    c3_resp = sb.table("claims").upsert({
        "claim_number": c3_number,
        "user_id": uid,
        "assigned_agent_id": AGENT_ID,
        "incident_type": "Accident",
        "vehicle_name": "Honda City",
        "policy_number": "POL-M-992333",
        "hsrp_number": "MH12AB1234",
        "engine_number": "ENG654321",
        "chassis_number": "CHS654321",
        "incident_date": "2026-10-10",
        "location_address": "Senapati Bapat Road, Shivaji Nagar",
        "location_city": "Pune",
        "location_state": "Maharashtra",
        "pincode": "411016",
        "description": "Front bumper and hood impact during slow moving traffic collision.",
        "driver_name": name,
        "driver_dl_number": dl,
        "claimed_amount": 22000.00,
        "approved_amount": 18500.00,
        "status": "settlement_accepted",
        "fraud_score": 8,
        "risk_level": "LOW RISK"
    }, on_conflict="claim_number").execute()
    c3_id = c3_resp.data[0]["id"]
    print(f"  Claim 3 ({c3_number}) id: {c3_id}")

    sb.table("claim_evidence").delete().eq("claim_id", c3_id).execute()
    evidence_c3 = [
        {
            "claim_id": c3_id,
            "file_url": f"evidence/dl_front/{uid}/pkg1_dl_abhiram.jpg",
            "storage_path": f"evidence/dl_front/{uid}/pkg1_dl_abhiram.jpg",
            "file_type": "image/jpeg",
            "category": "dl_front"
        },
        {
            "claim_id": c3_id,
            "file_url": f"evidence/dl_back/{uid}/pkg1_rc_honda_city.jpg",
            "storage_path": f"evidence/dl_back/{uid}/pkg1_rc_honda_city.jpg",
            "file_type": "image/jpeg",
            "category": "dl_back"
        },
        {
            "claim_id": c3_id,
            "file_url": f"evidence/photo/{uid}/set1_minor_bumper_scuff.jpg",
            "storage_path": f"evidence/photo/{uid}/set1_minor_bumper_scuff.jpg",
            "file_type": "image/jpeg",
            "category": "photo"
        }
    ]
    sb.table("claim_evidence").insert(evidence_c3).execute()

    c3_damages = [
        {
            "id": "dmg_hood_01",
            "part": "hood",
            "type": "Hood Dent & Scuff",
            "damage_type": "Impact Crease",
            "location": "Front Hood Center",
            "severity": "Moderate",
            "confidence": 0.91,
            "area_ratio": 0.12,
            "boundingBox": {"x": 25.0, "y": 30.0, "width": 50.0, "height": 30.0},
            "repair_action": "Tinkering & 2-Coat Paint",
            "estimated_cost": 18500.0,
            "estimated_cost_min": 16000.0,
            "estimated_cost_max": 21000.0
        }
    ]
    sb.table("claim_ai_analysis").upsert({
        "claim_id": c3_id,
        "detected_damages": c3_damages,
        "estimated_cost_min": 16000.00,
        "estimated_cost_max": 21000.00,
        "fraud_flags": []
    }, on_conflict="claim_id").execute()
    print("  Claim 3 settled evidence & AI analysis seeded.")

print("\nAll database seeding completed successfully!")
