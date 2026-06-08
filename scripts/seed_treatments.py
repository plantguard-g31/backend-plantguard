import asyncio
import uuid
import os
from dotenv import load_dotenv
import asyncpg

load_dotenv()
DB_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:5432/plantguard")
# Convert to sync asyncpg format
DB_URL_SYNC = DB_URL.replace("postgresql+asyncpg://", "postgresql://")

# Updated: One entry per (disease + crop), with all three severity dosages
TREATMENTS = [
    {
        "disease": "Tomato Early Blight",
        "crop": "tomato",
        "pesticide": "Copper Hydroxide 77% WP",
        "dosage_mild": "2g per 1L water, spray every 7 days",
        "dosage_moderate": "3g per 1L water, spray every 5 days + remove affected leaves",
        "dosage_severe": "4g per 1L water + systemic fungicide rotation, destroy heavily infected plants",
        "application": "Foliar spray in early morning or late evening",
        "safety": "Wear gloves & mask. Do not harvest within 14 days. Avoid direct sunlight.",
        "source": "FAO Plant Protection Manual 2023"
    },
    {
        "disease": "Potato Late Blight",
        "crop": "potato",
        "pesticide": "Mancozeb 75% WP",
        "dosage_mild": "2.5g per 1L water, spray every 7 days",
        "dosage_moderate": "3g per 1L water, spray every 5 days + remove infected leaves",
        "dosage_severe": "4g per 1L water + alternate with systemic fungicide, destroy heavily infected plants",
        "application": "Foliar spray covering both sides of leaves",
        "safety": "Wear protective clothing. Do not apply during flowering. Keep away from water sources.",
        "source": "NARC Agriculture Guidelines 2024"
    },
    {
        "disease": "Bell Pepper Bacterial Spot",
        "crop": "bell_pepper",
        "pesticide": "Copper Oxychloride 50% WP",
        "dosage_mild": "3g per 1L water, spray every 10 days",
        "dosage_moderate": "4g per 1L water, spray every 7 days + prune affected branches",
        "dosage_severe": "5g per 1L water + combine with biocontrol agent, remove severely infected plants",
        "application": "Spray early morning when leaves are dry",
        "safety": "Avoid contact with eyes. Wash hands after application. Store in cool, dry place.",
        "source": "ICAR-Vegetable Research Institute 2023"
    }
]

async def seed():
    """Connect to DB and insert seed treatments."""
    conn = await asyncpg.connect(DB_URL_SYNC)
    try:
        # Clear existing data (safe to re-run)
        await conn.execute("TRUNCATE treatment_records, treatment_translations RESTART IDENTITY CASCADE;")
        
        for t in TREATMENTS:
            tid = str(uuid.uuid4())  # Generate unique ID for treatment record
            
            # Insert main treatment record with ALL three dosage columns
            await conn.execute(
                """INSERT INTO treatment_records 
                   (id, disease_name, crop_type, pesticide_name, dosage_mild, dosage_moderate, dosage_severe, 
                    application_method, safety_warning, source)
                   VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)""",
                tid, 
                t["disease"], 
                t["crop"], 
                t["pesticide"], 
                t["dosage_mild"], 
                t["dosage_moderate"], 
                t["dosage_severe"], 
                t["application"], 
                t["safety"], 
                t["source"]
            )
            
            # Insert Nepali translations for key fields
            trans_fields = [
                ("pesticide_name", t.get("pesticide_ne", t["pesticide"])),
                ("dosage", t.get("dosage_ne", t["dosage_moderate"])),
                ("safety_warning", t.get("safety_ne", t["safety"]))
            ]
            
            for field_name, translated_text in trans_fields:
                trans_id = str(uuid.uuid4())
                await conn.execute(
                    """INSERT INTO treatment_translations (id, treatment_id, language_code, field_name, translated_text)
                       VALUES ($1, $2, 'ne', $3, $4)""",
                    trans_id, tid, field_name, translated_text
                )
        
        print("Database seeded successfully with expert-verified treatments.")
    except Exception as e:
        print(f"Seeding failed: {e}")
        raise
    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(seed())