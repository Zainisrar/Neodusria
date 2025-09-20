from fastapi import APIRouter, HTTPException, Query
from typing import Optional
from pydantic import BaseModel, Field
from bson import ObjectId
from datetime import datetime
from app.db import db
from openai import OpenAI
from dotenv import load_dotenv
import os

# Load .env file
load_dotenv()


router = APIRouter(prefix="/news-insights", tags=["News & Insights"])
users_collection = db["users"]
news_collection = db["news"]
projects_collection = db["projects"]
domains_collection = db["domains"]
# OpenAI client
clients = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


# ---------------------- Helpers ----------------------
def serialize(doc):
    doc["_id"] = str(doc["_id"])
    if "user_id" in doc:
        doc["user_id"] = str(doc["user_id"])
    if "project_id" in doc:
        doc["project_id"] = str(doc["project_id"])
    if "domain_id" in doc:
        doc["domain_id"] = str(doc["domain_id"])
    return doc

# ---------------------- Models ----------------------
class News(BaseModel):
    headline: str
    source: str
    category: str
    domain_id: str   # will hold domain ObjectId
    date: Optional[str] = None

#----------------------- LLM Integration (Pseudo) ----------------------
def ai_classify_alert(headline: str, category: str) -> str:
    """
    Uses LLM to classify news into one of:
    - "green": Informational/positive news, no major concern.
    - "amber": Moderate concern, watch closely.
    - "red": High risk/critical alert.
    """

    prompt = f"""
    You are an AI assistant for news risk classification.

    Task: Read the following news headline and category, then classify the alert level.
    Possible alert levels:
    - Green: Informational, positive, or minor.
    - Amber: Potential concern, requires monitoring.
    - Red: Serious concern, urgent/critical impact.

    Respond with ONLY one word: Green, Amber, or Red.

    Headline: "{headline}"
    Category: "{category}"
    """

    try:
        response = clients.chat.completions.create(
            model="gpt-4.1",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
        )

        raw_output = response.choices[0].message.content.strip().lower()

        # Normalize output
        if "red" in raw_output:
            return "Red"
        elif "amber" in raw_output or "yellow" in raw_output:
            return "Amber"
        elif "green" in raw_output:
            return "Green"
        else:
            return "Green"  # default fallback if LLM gives unexpected text

    except Exception as e:
        print("AI classification error:", e)
        return "Green"  # safe fallback



# ---------------------- NEWS CRUD ----------------------
@router.post("/news")
def create_news(news: News):
    data = news.dict()

    # Step 1: Auto-set date (current UTC) if not provided
    if not data.get("date"):
        data["date"] = datetime.utcnow().isoformat()

    # Step 2: Validate domain_id
    try:
        domain_obj_id = ObjectId(data["domain_id"])
    except:
        raise HTTPException(status_code=400, detail="Invalid domain_id format")

    domain_exists = domains_collection.find_one({"_id": domain_obj_id})
    if not domain_exists:
        raise HTTPException(status_code=404, detail="Domain not found")

    data["domain_id"] = domain_obj_id  # store as ObjectId

    # Step 3: Send headline/category to AI for alert_type
    alert_type = ai_classify_alert(data["headline"], data["category"])
    data["alert_type"] = alert_type  

    # Step 4: Save in DB
    result = news_collection.insert_one(data)
    return serialize(news_collection.find_one({"_id": result.inserted_id}))

# ---------------------- INSIGHTS CRUD ----------------------
@router.get("/latest")
def get_latest_insight(project_id: str = Query(..., description="Project ID")):
    """
    Get the most recent news (insight) for a given project based on its domain.
    """
    try:
        # 1. Find project
        project = projects_collection.find_one({"_id": ObjectId(project_id)})
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")

        domain = project.get("domain")
        if not domain:
            raise HTTPException(status_code=400, detail="Project has no domain set")

        # 2. Find latest news for this domain
        latest_news = news_collection.find_one(
            {"domain": domain},
            sort=[("date", -1)]
        )

        if not latest_news:
            return {
                "project_id": project_id,
                "domain": domain,
                "latest_insight": None
            }

        # 3. Build response object
        insight = {
            "id": str(latest_news["_id"]),
            "alert_type": latest_news.get("alert_type", "Amber"),
            "headline": latest_news["headline"],
            "date": latest_news["date"]
        }

        return {
            "project_id": project_id,
            "domain": domain,
            "latest_insight": insight
        }

    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error fetching latest insight: {str(e)}")