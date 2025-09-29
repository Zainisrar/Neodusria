from fastapi import APIRouter, HTTPException, Query
from typing import Optional
from pydantic import BaseModel, Field
from bson import ObjectId
from datetime import datetime
from app.db import db
from openai import OpenAI
import random
from typing import List

router = APIRouter(prefix="/news-insights", tags=["News & Insights"])
materials_collection = db["materials"]
forecasts_collection = db["forecasts"]
vendors_collection = db["vendors"]
vendor_news_collection = db["vendor_news"]
# MongoDB collection
futures_collection = db["futures_curves"]

router = APIRouter(prefix="/global", tags=["Global Markets"])

# ---------------- Materials ----------------
class Material(BaseModel):
    name: str
    ticker: str
    price: float
    industry: str | None = None
    unit: str
    volatility: float
    ESG_score: str  # Now A–F instead of float
    region: str
    icon: str | None = None  # Optional field for icons

# ---------------- Forecasts ----------------
class MonthData(BaseModel):
    month: str
    supply: float
    demand: float

class ForecastCreate(BaseModel):
    material_id: str   # store linked material
    title: str
    data: List[MonthData]
    industry: str | None = None
# ---------------- Vendors ----------------
class Vendor(BaseModel):
    # Existing fields
    name: str                          # e.g. "AlloyCorp"
    hq: str                            # e.g. "Germany"
    tier: int                          # e.g. 1, 2, 3
    risk_score: int                    # e.g. 25, 78
    delivery_rate: float               # % e.g. 98.5
    ESG_rating: str                    # e.g. "A" to "F"
    flag: str | None = None            # e.g. "🇩🇪"
    industry: str                      # e.g. "Automotive", "Electronics"
    address: str | None = None         # Headquarters full addres
    # Risk score breakdown for Radar Chart
    risk_breakdown: dict | None = None # e.g. {"financial": 70, "geopolitical": 60, "operational": 50, "compliance": 65, "cyber": 80}
    annual_revenue: float | None = None    # e.g. 5.2e9 (USD)
    employees: int | None = None           # e.g. 25000
    year_founded: int | None = None        # e.g. 1985

# ---------------- Vendor News ----------------
class VendorNews(BaseModel):
    vendor_id: str
    headline: str
    date: datetime
    link: Optional[str] = None

# ---------------- Futures ----------------
class FuturesContract(BaseModel):
    expiry: str   # e.g., "1M", "3M", "6M", "12M"
    price: float  # USD

class FuturesCurveCreate(BaseModel):
    material_id: str
    industry: str | None = None
    contracts: List[FuturesContract]

def serialize(doc):
    if not doc:
        return None
    doc["_id"] = str(doc["_id"])
    if "material_id" in doc:
        doc["material_id"] = str(doc["material_id"])
    if "vendor_id" in doc:
        doc["vendor_id"] = str(doc["vendor_id"])
    return doc



def get_volatility_level(value: float) -> str:
    mapping = {
        0.30: "Low",
        0.85: "Medium",
        1.15: "High",
        1.95: "Very High"
    }
    return mapping.get(value, "Unknown")

def generate_change() -> tuple[str, str]:
    """Generate random 24h % change and trend arrow"""
    change = round(random.uniform(-5, 5), 2)
    trend = "▲" if change >= 0 else "▼"
    return f"{'+' if change >= 0 else ''}{change}%", trend

# ---------------- API ----------------
@router.post("/materials")
def create_material(material: Material):
    material_dict = material.dict()
    
    # Add volatility level
    material_dict["volatility_level"] = get_volatility_level(material.volatility)
    
    # Add 24h Change + Trend
    change, trend = generate_change()
    material_dict["change_24h"] = change
    material_dict["trend"] = trend
    
    result = materials_collection.insert_one(material_dict)
    saved_doc = materials_collection.find_one({"_id": result.inserted_id})
    
    return serialize(saved_doc)

@router.get("/materials")
def list_materials(industry: str | None = Query(None)):
    query = {}
    if industry:
        query["industry"] = industry
    return [serialize(m) for m in materials_collection.find(query)]

@router.put("/materials/{material_id}")
def update_material(material_id: str, material: Material):
    result = materials_collection.update_one(
        {"_id": ObjectId(material_id)}, {"$set": material.dict()}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Material not found")
    return serialize(materials_collection.find_one({"_id": ObjectId(material_id)}))

@router.delete("/materials/{material_id}")
def delete_material(material_id: str):
    result = materials_collection.delete_one({"_id": ObjectId(material_id)})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Material not found")
    return {"message": "Material deleted successfully"}


# ------------------ top Mover ---------------------------
def parse_change(value):
    if isinstance(value, str):
        return float(value.replace("%", "").strip())
    return float(value)

@router.get("/top-movers")
def get_top_movers(industry: str | None = None, limit: int = 3):
    query = {}
    if industry:
        query["industry"] = {"$regex": f"^{industry}$", "$options": "i"}  

    materials = list(materials_collection.find(query))

    # Parse change_24h as number
    for m in materials:
        m["change_value"] = parse_change(m.get("change_24h", 0))

    gainers = sorted([m for m in materials if m["change_value"] > 0], key=lambda x: x["change_value"], reverse=True)[:limit]
    losers  = sorted([m for m in materials if m["change_value"] < 0], key=lambda x: x["change_value"])[:limit]

    def serialize_material(m):
        return {
            "name": m["name"],
            "ticker": m["ticker"],
            "change_24h": m["change_24h"],
            "direction": "▲" if m["change_value"] > 0 else "▼"
        }

    return {
        "title": f"Top Movers (24h){' - ' + industry if industry else ''}",
        "gainers": [serialize_material(m) for m in gainers],
        "losers": [serialize_material(m) for m in losers]
    }

# ---------------- Forecasts ----------------
@router.post("/forecasts")
def create_outlook(forecast: ForecastCreate):
    # Validate material_id
    if not ObjectId.is_valid(forecast.material_id):
        raise HTTPException(status_code=400, detail="Invalid material_id")
    
    material = materials_collection.find_one({"_id": ObjectId(forecast.material_id)})
    if not material:
        raise HTTPException(status_code=404, detail="Material not found")
    
    # Prevent duplicate forecast for same material
    existing = forecasts_collection.find_one({"material_id": forecast.material_id})
    if existing:
        raise HTTPException(status_code=400, detail="Forecast already exists for this material")
    
    forecast_dict = forecast.dict()

    # Always store ticker and industry
    forecast_dict["ticker"] = material["ticker"]  # for UI convenience
    forecast_dict["industry"] = forecast.industry or material.get("industry")  # fallback to material industry
    
    result = forecasts_collection.insert_one(forecast_dict)
    return {"message": "Forecast created", "id": str(result.inserted_id)}


@router.get("/forecasts/{material_id}")
def get_forecast(material_id: str):
    if not ObjectId.is_valid(material_id):
        raise HTTPException(status_code=400, detail="Invalid material_id")
    
    forecast = forecasts_collection.find_one({"material_id": material_id})
    if not forecast:
        raise HTTPException(status_code=404, detail="Forecast not found")
    
    forecast["_id"] = str(forecast["_id"])
    
    # Ensure industry is always present in response
    if "industry" not in forecast or not forecast["industry"]:
        # fallback from material if industry missing
        material = materials_collection.find_one({"_id": ObjectId(material_id)})
        forecast["industry"] = material.get("industry") if material else None
    
    return forecast

# -------------futures ----------------------

@router.post("/futures")
def create_futures_curve(data: FuturesCurveCreate):
    # Validate material_id
    if not ObjectId.is_valid(data.material_id):
        raise HTTPException(status_code=400, detail="Invalid material_id")
    
    material = materials_collection.find_one({"_id": ObjectId(data.material_id)})
    if not material:
        raise HTTPException(status_code=404, detail="Material not found")

    # Prevent duplicate futures curve for same material
    existing = futures_collection.find_one({"material_id": data.material_id})
    if existing:
        raise HTTPException(status_code=400, detail="Futures curve already exists for this material")
    
    futures_dict = data.dict()
    futures_dict["ticker"] = material["ticker"]
    futures_dict["material_name"] = material["name"]
    futures_dict["industry"] = data.industry or material.get("industry")

    result = futures_collection.insert_one(futures_dict)
    return {"message": "Futures curve created", "id": str(result.inserted_id)}
@router.get("/futures/{material_id}")
def get_futures_curve(material_id: str):
    if not ObjectId.is_valid(material_id):
        raise HTTPException(status_code=400, detail="Invalid material_id")

    curve = futures_collection.find_one({"material_id": material_id})
    if not curve:
        raise HTTPException(status_code=404, detail="Futures curve not found")

    curve["_id"] = str(curve["_id"])
    return curve


# ---------------- Vendors ----------------
@router.post("/vendors")
def create_vendor(vendor: Vendor):
    vendor_dict = vendor.dict()
    result = vendors_collection.insert_one(vendor_dict)
    return serialize(vendors_collection.find_one({"_id": result.inserted_id}))

@router.get("/vendors")
def list_vendors(industry: str | None = None):
    query = {}
    if industry:
        query["industry"] = industry
    return [serialize(v) for v in vendors_collection.find(query)]
@router.get("/vendors/{vendor_id}/risk_breakdown")
def get_vendor_risk_breakdown(vendor_id: str):
    vendor = vendors_collection.find_one({"_id": ObjectId(vendor_id)})
    if not vendor:
        raise HTTPException(status_code=404, detail="Vendor not found")

    if "risk_breakdown" not in vendor or vendor["risk_breakdown"] is None:
        raise HTTPException(status_code=404, detail="Risk breakdown not available")

    return {
        "vendor_id": str(vendor["_id"]),
        "name": vendor.get("name"),
        "risk_breakdown": vendor["risk_breakdown"]
    }

@router.get("/vendors/{vendor_id}/key_metrics")
def get_vendor_profile(vendor_id: str):
    vendor = vendors_collection.find_one({"_id": ObjectId(vendor_id)})
    if not vendor:
        raise HTTPException(status_code=404, detail="Vendor not found")

    profile = {
        "vendor_id": str(vendor["_id"]),
        # Key metrics
        "key_metrics": {
            "name": vendor.get("name"),
            "address": vendor.get("address"),
            "annual_revenue": vendor.get("annual_revenue"),
            "employees": vendor.get("employees"),
            "year_founded": vendor.get("year_founded")
        }
    }

    return profile
@router.put("/vendors/{vendor_id}")
def update_vendor(vendor_id: str, vendor: Vendor):
    result = vendors_collection.update_one(
        {"_id": ObjectId(vendor_id)}, {"$set": vendor.dict()}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Vendor not found")
    return serialize(vendors_collection.find_one({"_id": ObjectId(vendor_id)}))

@router.delete("/vendors/{vendor_id}")
def delete_vendor(vendor_id: str):
    result = vendors_collection.delete_one({"_id": ObjectId(vendor_id)})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Vendor not found")
    return {"message": "Vendor deleted successfully"}


# ---------------- Vendor News ----------------
@router.post("/vendor-news")
def create_vendor_news(news: VendorNews):
    data = news.dict()
    data["vendor_id"] = ObjectId(data["vendor_id"])
    result = vendor_news_collection.insert_one(data)
    return serialize(vendor_news_collection.find_one({"_id": result.inserted_id}))

@router.get("/vendor-news/{vendor_id}")
def list_vendor_news(vendor_id: str):
    try:
        vendor_object_id = ObjectId(vendor_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid vendor_id format")

    news_items = list(vendor_news_collection.find({"vendor_id": vendor_object_id}))
    
    if not news_items:
        raise HTTPException(status_code=404, detail="No news found for this vendor")
    
    return [serialize(n) for n in news_items]