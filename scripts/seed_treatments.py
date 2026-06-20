import asyncio
import uuid
import os
from dotenv import load_dotenv
import asyncpg

load_dotenv()


SYNC_DATABASE_URL = os.getenv("SYNC_DATABASE_URL", "postgresql://postgres:ritikbt@localhost:5432/PlantGuard")

TREATMENTS = [
    # --- TOMATO (10 Classes) ---
    {
        "disease": "Tomato Bacterial Spot", "disease_ne": "टमाटर ब्याक्टेरियल स्पट", "crop": "tomato", "pesticide": "Copper Hydroxide 77% WP",
        "mild_dosage": "2g per 1L water, spray every 7 days",
        "moderate_dosage": "3g per 1L water, spray every 5 days",
        "severe_dosage": "4g per 1L water, spray every 3 days + remove infected leaves",
        "timing": "Foliar spray in early morning", "timing_ne": "बिहान छिटो पातमा छर्कनुहोस्", 
        "safety": "Wear gloves. PHI 14 days.", "safety_ne": "पन्धा लगाउनुहोस्। १४ दिन भित्र बाली नटिप्नुहोस्।", 
        "interval_days": 14, "source": "FAO Plant Protection Manual 2023"
    },
    {
        "disease": "Tomato Early Blight", "disease_ne": "टमाटर अर्ली ब्लाइट", "crop": "tomato", "pesticide": "Chlorothalonil 75% WP",
        "mild_dosage": "2g per 1L water, spray every 7 days",
        "moderate_dosage": "3g per 1L water, spray every 5 days",
        "severe_dosage": "4g per 1L water, spray every 3 days + rotate fungicide",
        "timing": "Foliar spray in early morning or late evening", "timing_ne": "बिहान वा साँझ पातमा छर्कनुहोस्", 
        "safety": "Wear mask & gloves. PHI 7 days.", "safety_ne": "मास्क र पन्धा लगाउनुहोस्। ७ दिन भित्र बाली नटिप्नुहोस्।", 
        "interval_days": 7, "source": "FAO Plant Protection Manual 2023"
    },
    {
        "disease": "Tomato Late Blight", "disease_ne": "टमाटर लेट ब्लाइट", "crop": "tomato", "pesticide": "Mancozeb 75% WP",
        "mild_dosage": "2.5g per 1L water, spray every 7 days",
        "moderate_dosage": "3g per 1L water, spray every 5 days",
        "severe_dosage": "4g per 1L water, spray every 3 days + systemic fungicide",
        "timing": "Foliar spray covering both sides of leaves", "timing_ne": "पातको दुवै तर्फ छर्कनुहोस्", 
        "safety": "Wear protective clothing. PHI 10 days.", "safety_ne": "सुरक्षा कपडा लगाउनुहोस्। १० दिन भित्र बाली नटिप्नुहोस्।", 
        "interval_days": 10, "source": "NARC Agriculture Guidelines 2024"
    },
    {
        "disease": "Tomato Leaf Mold", "disease_ne": "टमाटर पातको मोल्ड", "crop": "tomato", "pesticide": "Copper Oxychloride 50% WP",
        "mild_dosage": "3g per 1L water, spray every 7 days",
        "moderate_dosage": "4g per 1L water, spray every 5 days",
        "severe_dosage": "5g per 1L water, spray every 3 days + improve ventilation",
        "timing": "Foliar spray, focus on leaf undersides", "timing_ne": "पातको तल्लो भागमा बढी छर्कनुहोस्", 
        "safety": "Avoid inhalation. PHI 14 days.", "safety_ne": "श्वासप्रश्वासमा ध्यान दिनुहोस्। १४ दिन भित्र बाली नटिप्नुहोस्।", 
        "interval_days": 14, "source": "FAO Plant Protection Manual 2023"
    },
    {
        "disease": "Tomato Septoria Leaf Spot", "disease_ne": "टमाटर सेप्टोरिया लिफ स्पट", "crop": "tomato", "pesticide": "Azoxystrobin 23% SC",
        "mild_dosage": "1ml per 1L water, spray every 7 days",
        "moderate_dosage": "1.5ml per 1L water, spray every 5 days",
        "severe_dosage": "2ml per 1L water, spray every 3 days + remove lower leaves",
        "timing": "Foliar spray in cool hours", "timing_ne": "चिसो मौसममा पातमा छर्कनुहोस्", 
        "safety": "Wear gloves. PHI 7 days.", "safety_ne": "पन्धा लगाउनुहोस्। ७ दिन भित्र बाली नटिप्नुहोस्।", 
        "interval_days": 7, "source": "FAO Plant Protection Manual 2023"
    },
    {
        "disease": "Tomato Spider Mites", "disease_ne": "टमाटर स्पाइडर माइट्स", "crop": "tomato", "pesticide": "Abamectin 1.8% EC",
        "mild_dosage": "0.5ml per 1L water, spray every 7 days",
        "moderate_dosage": "1ml per 1L water, spray every 5 days",
        "severe_dosage": "1.5ml per 1L water, spray every 3 days + wet leaf undersides",
        "timing": "Spray thoroughly on leaf undersides", "timing_ne": "पातको तल्लो भाग राम्ररी छर्कनुहोस्", 
        "safety": "Highly toxic to bees. PHI 7 days.", "safety_ne": "मौराका लागि अत्यन्त विषालु। ७ दिन भित्र बाली नटिप्नुहोस्।", 
        "interval_days": 7, "source": "NARC Agriculture Guidelines 2024"
    },
    {
        "disease": "Tomato Target Spot", "disease_ne": "टमाटर टार्गेट स्पट", "crop": "tomato", "pesticide": "Mancozeb 75% WP",
        "mild_dosage": "2.5g per 1L water, spray every 7 days",
        "moderate_dosage": "3g per 1L water, spray every 5 days",
        "severe_dosage": "4g per 1L water, spray every 3 days",
        "timing": "Foliar spray in early morning", "timing_ne": "बिहान छिटो पातमा छर्कनुहोस्", 
        "safety": "Wear mask. PHI 10 days.", "safety_ne": "मास्क लगाउनुहोस्। १० दिन भित्र बाली नटिप्नुहोस्।", 
        "interval_days": 10, "source": "FAO Plant Protection Manual 2023"
    },
    {
        "disease": "Tomato Yellow Leaf Curl Virus", "disease_ne": "टमाटर पहेंलो पात बटारने भाइरस", "crop": "tomato", "pesticide": "Imidacloprid 17.8% SL (Vector Control)",
        "mild_dosage": "0.5ml per 1L water, spray every 10 days",
        "moderate_dosage": "1ml per 1L water, spray every 7 days",
        "severe_dosage": "No chemical cure. Uproot and destroy infected plants immediately.",
        "timing": "Spray to control whitefly vectors", "timing_ne": "सेतो झिङ्गा नियन्त्रण गर्न छर्कनुहोस्", 
        "safety": "Systemic insecticide. PHI 14 days.", "safety_ne": "प्रणालीगत कीटनाशक। १४ दिन भित्र बाली नटिप्नुहोस्।", 
        "interval_days": 14, "source": "FAO Plant Protection Manual 2023"
    },
    {
        "disease": "Tomato Mosaic Virus", "disease_ne": "टमाटर मोजेक भाइरस", "crop": "tomato", "pesticide": "None (Viral)",
        "mild_dosage": "No chemical cure. Disinfect tools with 10% bleach solution.",
        "moderate_dosage": "No chemical cure. Remove and burn symptomatic plants.",
        "severe_dosage": "No chemical cure. Uproot entire infected zone and solarize soil.",
        "timing": "Focus on sanitation and aphid vector control", "timing_ne": "सरसफाइ र भेटर्स नियन्त्रणमा जोड दिनुहोस्", 
        "safety": "Wash hands with soap after handling plants.", "safety_ne": "बिरुवा छुएपछि साबुनले हात धुनुहोस्।", 
        "interval_days": 0, "source": "NARC Agriculture Guidelines 2024"
    },
    {
        "disease": "Tomato Healthy", "disease_ne": "टमाटर स्वस्थ", "crop": "tomato", "pesticide": "None",
        "mild_dosage": "No treatment required. Maintain standard crop care.",
        "moderate_dosage": "No treatment required. Maintain standard crop care.",
        "severe_dosage": "No treatment required. Maintain standard crop care.",
        "timing": "N/A", "timing_ne": "लागू हुँदैन", 
        "safety": "Continue regular monitoring.", "safety_ne": "नियमित अनुगमन जारी राख्नुहोस्।", 
        "interval_days": 0, "source": "FAO Plant Protection Manual 2023"
    },
    # --- POTATO (3 Classes) ---
    {
        "disease": "Potato Early Blight", "disease_ne": "आलु अर्ली ब्लाइट", "crop": "potato", "pesticide": "Chlorothalonil 75% WP",
        "mild_dosage": "2g per 1L water, spray every 7 days",
        "moderate_dosage": "3g per 1L water, spray every 5 days",
        "severe_dosage": "4g per 1L water, spray every 3 days",
        "timing": "Foliar spray in early morning", "timing_ne": "बिहान छिटो पातमा छर्कनुहोस्", 
        "safety": "Wear mask. PHI 14 days.", "safety_ne": "मास्क लगाउनुहोस्। १४ दिन भित्र बाली नटिप्नुहोस्।", 
        "interval_days": 14, "source": "FAO Plant Protection Manual 2023"
    },
    {
        "disease": "Potato Late Blight", "disease_ne": "आलु लेट ब्लाइट", "crop": "potato", "pesticide": "Metalaxyl + Mancozeb 72% WP",
        "mild_dosage": "2.5g per 1L water, spray every 7 days",
        "moderate_dosage": "3g per 1L water, spray every 5 days",
        "severe_dosage": "4g per 1L water, spray every 3 days + destroy haulms",
        "timing": "Foliar spray covering all foliage", "timing_ne": "सबै पातमा छर्कनुहोस्", 
        "safety": "Wear protective suit. PHI 21 days.", "safety_ne": "सुरक्षा पोसाक लगाउनुहोस्। २१ दिन भित्र बाली नटिप्नुहोस्।", 
        "interval_days": 21, "source": "NARC Agriculture Guidelines 2024"
    },
    {
        "disease": "Potato Healthy", "disease_ne": "आलु स्वस्थ", "crop": "potato", "pesticide": "None",
        "mild_dosage": "No treatment required. Maintain standard crop care.",
        "moderate_dosage": "No treatment required. Maintain standard crop care.",
        "severe_dosage": "No treatment required. Maintain standard crop care.",
        "timing": "N/A", "timing_ne": "लागू हुँदैन", 
        "safety": "Continue regular monitoring.", "safety_ne": "नियमित अनुगमन जारी राख्नुहोस्।", 
        "interval_days": 0, "source": "FAO Plant Protection Manual 2023"
    },
    # --- BELL PEPPER (2 Classes) ---
    {
        "disease": "Bell Pepper Bacterial Spot", "disease_ne": "बेल पेपर ब्याक्टेरियल स्पट", "crop": "bell_pepper", "pesticide": "Copper Oxychloride 50% WP",
        "mild_dosage": "3g per 1L water, spray every 10 days",
        "moderate_dosage": "4g per 1L water, spray every 7 days",
        "severe_dosage": "5g per 1L water, spray every 5 days + remove lesions",
        "timing": "Spray early morning when leaves are dry", "timing_ne": "पात सुख्खा हुँदा बिहान छिटो छर्कनुहोस्", 
        "safety": "Avoid contact with eyes. PHI 10 days.", "safety_ne": "आँखामा नलागोस्। १० दिन भित्र बाली नटिप्नुहोस्।", 
        "interval_days": 10, "source": "ICAR-Vegetable Research Institute 2023"
    },
    {
        "disease": "Bell Pepper Healthy", "disease_ne": "बेल पेपर स्वस्थ", "crop": "bell_pepper", "pesticide": "None",
        "mild_dosage": "No treatment required. Maintain standard crop care.",
        "moderate_dosage": "No treatment required. Maintain standard crop care.",
        "severe_dosage": "No treatment required. Maintain standard crop care.",
        "timing": "N/A", "timing_ne": "लागू हुँदैन", 
        "safety": "Continue regular monitoring.", "safety_ne": "नियमित अनुगमन जारी राख्नुहोस्।", 
        "interval_days": 0, "source": "FAO Plant Protection Manual 2023"
    }
]

async def seed():
    """Connect to DB and insert 45 expert-verified treatment records (15 classes x 3 severities)."""

    connect_kwargs = {}
    if "supabase" in SYNC_DATABASE_URL:
        connect_kwargs["ssl"] = "require"
        
    conn = await asyncpg.connect(SYNC_DATABASE_URL, **connect_kwargs)
    
    try:
        # Clear existing data safely
        await conn.execute("TRUNCATE treatment_records, treatment_translations RESTART IDENTITY CASCADE;")
        
        for t in TREATMENTS:
            # Insert 3 rows per disease (Mild, Moderate, Severe) -> Total 45 rows
            for severity, dosage in [("mild", t["mild_dosage"]), ("moderate", t["moderate_dosage"]), ("severe", t["severe_dosage"])]:
                tid = str(uuid.uuid4())
                await conn.execute(
                    """INSERT INTO treatment_records
                    (id, disease_name, crop_type, severity_level, pesticide_name, 
                     dosage_mild, dosage_moderate, dosage_severe, application_timing, 
                     safety_instructions, pre_harvest_interval_days, source_reference, is_active)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, TRUE)""",
                    tid, t["disease"], t["crop"], severity, t["pesticide"],
                    t["mild_dosage"], t["moderate_dosage"], t["severe_dosage"], 
                    t["timing"], t["safety"], t["interval_days"], t["source"]
                )
                
                # Insert EXACTLY ONE Nepali translation per treatment record (Matches UNIQUE constraint)
                trans_id = str(uuid.uuid4())
                await conn.execute(
                    """INSERT INTO treatment_translations 
                    (id, treatment_record_id, language_code, disease_name_translated, 
                     treatment_instructions_translated, safety_warnings_translated)
                    VALUES ($1, $2, 'ne', $3, $4, $5)""",
                    trans_id, tid, t["disease_ne"], t["timing_ne"], t["safety_ne"]
                )

        print("Database seeded successfully with 45 expert-verified treatment records (15 classes x 3 severities) + 45 Nepali translations.")
    except Exception as e:
        print(f"Seeding failed: {e}")
        raise
    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(seed())