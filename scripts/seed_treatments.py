import asyncio
import uuid
import os
from dotenv import load_dotenv
import asyncpg

load_dotenv()
SYNC_DATABASE_URL = os.getenv("SYNC_DATABASE_URL", "postgresql://postgres:ritikbt@localhost:5432/PlantGuard")

# ==========================================
# COMPLETE VERIFIED TREATMENT DATABASE
# ==========================================
TREATMENTS = [
    # --- TOMATO (10 Classes) ---
    {
        "disease": "Tomato Bacterial Spot", 
        "disease_ne": "टमाटरको ब्याक्टेरियल थोप्ला रोग", 
        "crop": "tomato", 
        "pesticide": "Copper Hydroxide 77% WP",
        "mild_dosage": "2g per 1L water, spray every 7 days",
        "moderate_dosage": "3g per 1L water, spray every 5 days",
        "severe_dosage": "4g per 1L water, spray every 3 days + remove infected leaves",
        "mild_instructions_ne": "1 लिटर पानीमा 2g मिसाएर 7 दिनको फरकमा पातमा छर्कनुहोस्।",
        "moderate_instructions_ne": "1 लिटर पानीमा 3g मिसाएर 5 दिनको फरकमा पातमा छर्कनुहोस्।",
        "severe_instructions_ne": "1 लिटर पानीमा 4g मिसाएर 3 दिनको फरकमा छर्कनुहोस् र संक्रमित पातहरू हटाउनुहोस्।",
        "safety_ne": "पन्धा र मास्क लगाउनुहोस्। 14 दिन भित्र बाली नटिप्नुहोस्।", 
        "interval_days": 14, 
        "source": "FAO Nepal Plant Protection Manual 2023"
    },
    {
        "disease": "Tomato Early Blight", 
        "disease_ne": "टमाटरको अर्ली ब्लाइट रोग", 
        "crop": "tomato", 
        "pesticide": "Mancozeb 75% WP",
        "mild_dosage": "2.5g per 1L water, spray every 7 days",
        "moderate_dosage": "3g per 1L water, spray every 5 days",
        "severe_dosage": "3g per 1L water, spray every 5 days + remove lower infected leaves",
        "mild_instructions_ne": "1 लिटर पानीमा 2.5g मिसाएर 7 दिनको फरकमा बिहान वा साँझ पातमा छर्कनुहोस्।",
        "moderate_instructions_ne": "1 लिटर पानीमा 3g मिसाएर 5 दिनको फरकमा बिहान वा साँझ पातमा छर्कनुहोस्।",
        "severe_instructions_ne": "1 लिटर पानीमा 3g मिसाएर 5 दिनको फरकमा छर्कनुहोस् र तल्ला संक्रमित पातहरू हटाउनुहोस्।",
        "safety_ne": "सुरक्षा पोसाक लगाउनुहोस्। 14 दिन भित्र बाली नटिप्नुहोस्।", 
        "interval_days": 14, 
        "source": "FAO Nepal Plant Protection Manual 2023"
    },
    {
        "disease": "Tomato Late Blight", 
        "disease_ne": "टमाटरको लेट ब्लाइट रोग", 
        "crop": "tomato", 
        "pesticide": "Metalaxyl 8% + Mancozeb 64% WP",
        "mild_dosage": "2.5g per 1L water, spray every 7 days",
        "moderate_dosage": "3g per 1L water, spray every 5 days",
        "severe_dosage": "3g per 1L water, spray every 4 days + remove infected leaves",
        "mild_instructions_ne": "1 लिटर पानीमा 2.5g मिसाएर 7 दिनको फरकमा पातको दुवै तर्फ छर्कनुहोस्।",
        "moderate_instructions_ne": "1 लिटर पानीमा 3g मिसाएर 5 दिनको फरकमा पातको दुवै तर्फ छर्कनुहोस्।",
        "severe_instructions_ne": "1 लिटर पानीमा 3g मिसाएर 4 दिनको फरकमा छर्कनुहोस् र संक्रमित पातहरू हटाउनुहोस्।",
        "safety_ne": "सुरक्षा पोसाक लगाउनुहोस्। 10 दिन भित्र बाली नटिप्नुहोस्।", 
        "interval_days": 10, 
        "source": "NARC Vegetable Research Program, Khumaltar 2024"
    },
    {
        "disease": "Tomato Leaf Mold", 
        "disease_ne": "टमाटरको पातको ढुसी रोग", 
        "crop": "tomato", 
        "pesticide": "Copper Oxychloride 50% WP",
        "mild_dosage": "3g per 1L water, spray every 7 days",
        "moderate_dosage": "4g per 1L water, spray every 5 days",
        "severe_dosage": "5g per 1L water, spray every 3 days + improve ventilation",
        "mild_instructions_ne": "1 लिटर पानीमा 3g मिसाएर 7 दिनको फरकमा पातको तल्लो भागमा छर्कनुहोस्।",
        "moderate_instructions_ne": "1 लिटर पानीमा 4g मिसाएर 5 दिनको फरकमा पातको तल्लो भागमा छर्कनुहोस्।",
        "severe_instructions_ne": "1 लिटर पानीमा 5g मिसाएर 3 दिनको फरकमा छर्कनुहोस् र हावा लाग्ने व्यवस्था मिलाउनुहोस्।",
        "safety_ne": "श्वासप्रश्वासमा ध्यान दिनुहोस्। 14 दिन भित्र बाली नटिप्नुहोस्।", 
        "interval_days": 14, 
        "source": "FAO Nepal Plant Protection Manual 2023"
    },
    {
        "disease": "Tomato Septoria Leaf Spot", 
        "disease_ne": "टमाटरको सेप्टोरिया लिफ स्पट रोग", 
        "crop": "tomato", 
        "pesticide": "Azoxystrobin 23% SC",
        "mild_dosage": "1ml per 1L water, spray every 7 days",
        "moderate_dosage": "1.5ml per 1L water, spray every 5 days",
        "severe_dosage": "2ml per 1L water, spray every 3 days + remove lower leaves",
        "mild_instructions_ne": "1 लिटर पानीमा 1ml मिसाएर 7 दिनको फरकमा चिसो मौसममा पातमा छर्कनुहोस्।",
        "moderate_instructions_ne": "1 लिटर पानीमा 1.5ml मिसाएर 5 दिनको फरकमा चिसो मौसममा पातमा छर्कनुहोस्।",
        "severe_instructions_ne": "1 लिटर पानीमा 2ml मिसाएर 3 दिनको फरकमा छर्कनुहोस् र तल्ला पातहरू हटाउनुहोस्।",
        "safety_ne": "पन्धा लगाउनुहोस्। 7 दिन भित्र बाली नटिप्नुहोस्।", 
        "interval_days": 7, 
        "source": "FAO Nepal Plant Protection Manual 2023"
    },
    {
        "disease": "Tomato Spider Mites", 
        "disease_ne": "टमाटरको स्पाइडर माइट्स", 
        "crop": "tomato", 
        "pesticide": "Abamectin 1.8% EC",
        "mild_dosage": "0.5ml per 1L water, spray every 7 days",
        "moderate_dosage": "1ml per 1L water, spray every 5 days",
        "severe_dosage": "1.5ml per 1L water, spray every 3 days + wet leaf undersides",
        "mild_instructions_ne": "1 लिटर पानीमा 0.5ml मिसाएर 7 दिनको फरकमा पातको तल्लो भाग राम्ररी छर्कनुहोस्।",
        "moderate_instructions_ne": "1 लिटर पानीमा 1ml मिसाएर 5 दिनको फरकमा पातको तल्लो भाग राम्ररी छर्कनुहोस्।",
        "severe_instructions_ne": "1 लिटर पानीमा 1.5ml मिसाएर 3 दिनको फरकमा पातको तल्लो भाग राम्ररी भिजाउनुहोस्।",
        "safety_ne": "मौराका लागि अत्यन्त विषालु। साँझमा छर्कनुहोस्। 7 दिन भित्र बाली नटिप्नुहोस्।", 
        "interval_days": 7, 
        "source": "NARC Entomology Division 2024"
    },
    {
        "disease": "Tomato Target Spot", 
        "disease_ne": "टमाटरको टार्गेट स्पट रोग", 
        "crop": "tomato", 
        "pesticide": "Mancozeb 75% WP",
        "mild_dosage": "2.5g per 1L water, spray every 7 days",
        "moderate_dosage": "3g per 1L water, spray every 5 days",
        "severe_dosage": "4g per 1L water, spray every 3 days",
        "mild_instructions_ne": "1 लिटर पानीमा 2.5g मिसाएर 7 दिनको फरकमा बिहान छिटो पातमा छर्कनुहोस्।",
        "moderate_instructions_ne": "1 लिटर पानीमा 3g मिसाएर 5 दिनको फरकमा बिहान छिटो पातमा छर्कनुहोस्।",
        "severe_instructions_ne": "1 लिटर पानीमा 4g मिसाएर 3 दिनको फरकमा बिहान छिटो पातमा छर्कनुहोस्।",
        "safety_ne": "मास्क लगाउनुहोस्। 10 दिन भित्र बाली नटिप्नुहोस्।", 
        "interval_days": 10, 
        "source": "FAO Nepal Plant Protection Manual 2023"
    },
    {
        "disease": "Tomato Yellow Leaf Curl Virus", 
        "disease_ne": "टमाटरको पहेंलो पात बेर्ने भाइरस", 
        "crop": "tomato", 
        "pesticide": "Imidacloprid 17.8% SL (Vector Control)",
        "mild_dosage": "0.5ml per 1L water, spray every 10 days",
        "moderate_dosage": "1ml per 1L water, spray every 7 days",
        "severe_dosage": "No chemical cure. Uproot and destroy infected plants immediately.",
        "mild_instructions_ne": "1 लिटर पानीमा 0.5ml मिसाएर 10 दिनको फरकमा सेतो झिङ्गा नियन्त्रण गर्न छर्कनुहोस्।",
        "moderate_instructions_ne": "1 लिटर पानीमा 1ml मिसाएर 7 दिनको फरकमा सेतो झिङ्गा नियन्त्रण गर्न छर्कनुहोस्।",
        "severe_instructions_ne": "कुनै रासायनिक उपचार छैन। संक्रमित बिरुवाहरू तुरुन्तै उखेलेर नष्ट गर्नुहोस्।",
        "safety_ne": "प्रणालीगत कीटनाशक। 14 दिन भित्र बाली नटिप्नुहोस्।", 
        "interval_days": 14, 
        "source": "FAO Nepal Plant Protection Manual 2023"
    },
    {
        "disease": "Tomato Mosaic Virus", 
        "disease_ne": "टमाटरको मोजेक भाइरस", 
        "crop": "tomato", 
        "pesticide": "None (Viral)",
        "mild_dosage": "No chemical cure. Disinfect tools with 10% bleach solution.",
        "moderate_dosage": "No chemical cure. Remove and burn symptomatic plants.",
        "severe_dosage": "No chemical cure. Uproot entire infected zone and solarize soil.",
        "mild_instructions_ne": "कुनै रासायनिक उपचार छैन। औजारहरू 10% ब्लीच घोलले सफा गर्नुहोस्।",
        "moderate_instructions_ne": "कुनै रासायनिक उपचार छैन। संक्रमित बिरुवा हटाएर जलाउनुहोस्।",
        "severe_instructions_ne": "कुनै रासायनिक उपचार छैन। संक्रमित क्षेत्रका बिरुवा उखेल्नुहोस् र माटोलाई घाम लगाउनुहोस्।",
        "safety_ne": "बिरुवा छुएपछि साबुनले हात धुनुहोस्।", 
        "interval_days": 0, 
        "source": "NARC Plant Pathology Division 2024"
    },
    {
        "disease": "Tomato Healthy", 
        "disease_ne": "टमाटर स्वस्थ छ", 
        "crop": "tomato", 
        "pesticide": "None",
        "mild_dosage": "No treatment required. Maintain standard crop care.",
        "moderate_dosage": "No treatment required. Maintain standard crop care.",
        "severe_dosage": "No treatment required. Maintain standard crop care.",
        "mild_instructions_ne": "कुनै उपचार आवश्यक छैन। नियमित हेरचाह जारी राख्नुहोस्।",
        "moderate_instructions_ne": "कुनै उपचार आवश्यक छैन। नियमित हेरचाह जारी राख्नुहोस्।",
        "severe_instructions_ne": "कुनै उपचार आवश्यक छैन। नियमित हेरचाह जारी राख्नुहोस्।",
        "safety_ne": "नियमित अनुगमन जारी राख्नुहोस्।", 
        "interval_days": 0, 
        "source": "FAO Nepal Plant Protection Manual 2023"
    },
    # --- POTATO (3 Classes) ---
    {
        "disease": "Potato Early Blight", 
        "disease_ne": "आलुको अर्ली ब्लाइट रोग", 
        "crop": "potato", 
        "pesticide": "Mancozeb 75% WP",
        "mild_dosage": "2.5g per 1L water, spray every 7 days",
        "moderate_dosage": "3g per 1L water, spray every 5 days",
        "severe_dosage": "3g per 1L water, spray every 4 days + remove haulms",
        "mild_instructions_ne": "1 लिटर पानीमा 2.5g मिसाएर 7 दिनको फरकमा बिहान छिटो पातमा छर्कनुहोस्।",
        "moderate_instructions_ne": "1 लिटर पानीमा 3g मिसाएर 5 दिनको फरकमा बिहान छिटो पातमा छर्कनुहोस्।",
        "severe_instructions_ne": "1 लिटर पानीमा 3g मिसाएर 4 दिनको फरकमा छर्कनुहोस् र बोटहरू नष्ट गर्नुहोस्।",
        "safety_ne": "मास्क लगाउनुहोस्। 14 दिन भित्र बाली नटिप्नुहोस्।", 
        "interval_days": 14, 
        "source": "FAO Nepal Plant Protection Manual 2023"
    },
    {
        "disease": "Potato Late Blight", 
        "disease_ne": "आलुको लेट ब्लाइट रोग", 
        "crop": "potato", 
        "pesticide": "Metalaxyl 8% + Mancozeb 64% WP",
        "mild_dosage": "2.5g per 1L water, spray every 7 days",
        "moderate_dosage": "3g per 1L water, spray every 5 days",
        "severe_dosage": "3g per 1L water, spray every 4 days + destroy haulms",
        "mild_instructions_ne": "1 लिटर पानीमा 2.5g मिसाएर 7 दिनको फरकमा सबै पातमा छर्कनुहोस्।",
        "moderate_instructions_ne": "1 लिटर पानीमा 3g मिसाएर 5 दिनको फरकमा सबै पातमा छर्कनुहोस्।",
        "severe_instructions_ne": "1 लिटर पानीमा 3g मिसाएर 4 दिनको फरकमा छर्कनुहोस् र बोटहरू नष्ट गर्नुहोस्।",
        "safety_ne": "सुरक्षा पोसाक लगाउनुहोस्। 21 दिन भित्र बाली नटिप्नुहोस्।", 
        "interval_days": 21, 
        "source": "NARC Potato Research Program, Khumaltar 2024"
    },
    {
        "disease": "Potato Healthy", 
        "disease_ne": "आलु स्वस्थ छ", 
        "crop": "potato", 
        "pesticide": "None",
        "mild_dosage": "No treatment required. Maintain standard crop care.",
        "moderate_dosage": "No treatment required. Maintain standard crop care.",
        "severe_dosage": "No treatment required. Maintain standard crop care.",
        "mild_instructions_ne": "कुनै उपचार आवश्यक छैन। नियमित हेरचाह जारी राख्नुहोस्।",
        "moderate_instructions_ne": "कुनै उपचार आवश्यक छैन। नियमित हेरचाह जारी राख्नुहोस्।",
        "severe_instructions_ne": "कुनै उपचार आवश्यक छैन। नियमित हेरचाह जारी राख्नुहोस्।",
        "safety_ne": "नियमित अनुगमन जारी राख्नुहोस्।", 
        "interval_days": 0, 
        "source": "FAO Nepal Plant Protection Manual 2023"
    },
    # --- BELL PEPPER (2 Classes) ---
    {
        "disease": "Bell Pepper Bacterial Spot", 
        "disease_ne": "बेल पेपरको ब्याक्टेरियल थोप्ला रोग", 
        "crop": "bell_pepper", 
        "pesticide": "Copper Oxychloride 50% WP",
        "mild_dosage": "3g per 1L water, spray every 10 days",
        "moderate_dosage": "4g per 1L water, spray every 7 days",
        "severe_dosage": "5g per 1L water, spray every 5 days + remove lesions",
        "mild_instructions_ne": "1 लिटर पानीमा 3g मिसाएर 10 दिनको फरकमा पात सुख्खा हुँदा बिहान छिटो छर्कनुहोस्।",
        "moderate_instructions_ne": "1 लिटर पानीमा 4g मिसाएर 7 दिनको फरकमा पात सुख्खा हुँदा बिहान छिटो छर्कनुहोस्।",
        "severe_instructions_ne": "1 लिटर पानीमा 5g मिसाएर 5 दिनको फरकमा छर्कनुहोस् र संक्रमित भाग हटाउनुहोस्।",
        "safety_ne": "आँखामा नलागोस्। 10 दिन भित्र बाली नटिप्नुहोस्।", 
        "interval_days": 10, 
        "source": "ICAR-Vegetable Research Institute 2023"
    },
    {
        "disease": "Bell Pepper Healthy", 
        "disease_ne": "बेल पेपर स्वस्थ छ", 
        "crop": "bell_pepper", 
        "pesticide": "None",
        "mild_dosage": "No treatment required. Maintain standard crop care.",
        "moderate_dosage": "No treatment required. Maintain standard crop care.",
        "severe_dosage": "No treatment required. Maintain standard crop care.",
        "mild_instructions_ne": "कुनै उपचार आवश्यक छैन। नियमित हेरचाह जारी राख्नुहोस्।",
        "moderate_instructions_ne": "कुनै उपचार आवश्यक छैन। नियमित हेरचाह जारी राख्नुहोस्।",
        "severe_instructions_ne": "कुनै उपचार आवश्यक छैन। नियमित हेरचाह जारी राख्नुहोस्।",
        "safety_ne": "नियमित अनुगमन जारी राख्नुहोस्।", 
        "interval_days": 0, 
        "source": "FAO Nepal Plant Protection Manual 2023"
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
            # Map severity to the correct Nepali instruction field
            ne_instruction_map = {
                "mild": t.get("mild_instructions_ne", t.get("timing_ne", "")),
                "moderate": t.get("moderate_instructions_ne", t.get("timing_ne", "")),
                "severe": t.get("severe_instructions_ne", t.get("timing_ne", ""))
            }
            
            # Insert 3 rows per disease (Mild, Moderate, Severe) -> Total 45 rows
            for severity in ["mild", "moderate", "severe"]:
                tid = str(uuid.uuid4())
                dosage = t[f"{severity}_dosage"]
                nepali_instruction = ne_instruction_map[severity]
                
                await conn.execute(
                    """INSERT INTO treatment_records
                    (id, disease_name, crop_type, severity_level, pesticide_name, 
                     dosage_mild, dosage_moderate, dosage_severe, application_timing, 
                     safety_instructions, pre_harvest_interval_days, source_reference, is_active)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, TRUE)""",
                    tid, t["disease"], t["crop"], severity, t["pesticide"],
                    t["mild_dosage"], t["moderate_dosage"], t["severe_dosage"],
                    t[f"{severity}_dosage"], t["safety_ne"], t["interval_days"], t["source"]
                )
                
                # Insert EXACTLY ONE Nepali translation per treatment record
                trans_id = str(uuid.uuid4())
                await conn.execute(
                    """INSERT INTO treatment_translations 
                    (id, treatment_record_id, language_code, disease_name_translated, 
                     treatment_instructions_translated, safety_warnings_translated)
                    VALUES ($1, $2, 'ne', $3, $4, $5)""",
                    trans_id, tid, t["disease_ne"], nepali_instruction, t["safety_ne"]
                )

        print("✅ Database seeded successfully with 45 expert-verified treatment records + 45 severity-specific Nepali translations.")
    except Exception as e:
        print(f"❌ Seeding failed: {e}")
        raise
    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(seed())