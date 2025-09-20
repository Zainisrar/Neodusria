from fastapi import APIRouter, HTTPException, Query
from typing import Optional
from pydantic import BaseModel, Field
from bson import ObjectId
from datetime import datetime
from app.db import db
from openai import OpenAI

router = APIRouter(prefix="/news-insights", tags=["News & Insights"])
materials_collection = db["materials"]
forecasts_collection = db["forecasts"]
vendors_collection = db["vendors"]
vendor_news_collection = db["vendor_news"]

router = APIRouter(prefix="/global", tags=["Global Markets"])

# ---------------- Materials ----------------
class Material(BaseModel):
    name: str
    ticker: str
    price: float
    volatility: float
    ESG_score: float
    region: str

# ---------------- Forecasts ----------------
class Forecast(BaseModel):
    material_id: str
    month: str  # e.g. "2025-10"
    demand: float
    supply: float

# ---------------- Vendors ----------------
class Vendor(BaseModel):
    name: str
    hq: str
    tier: str
    risk_score: float
    delivery_rate: float
    ESG_rating: float

# ---------------- Vendor News ----------------
class VendorNews(BaseModel):
    vendor_id: str
    headline: str
    date: datetime
    link: Optional[str] = None


def serialize(doc):
    if not doc:
        return None
    doc["_id"] = str(doc["_id"])
    if "material_id" in doc:
        doc["material_id"] = str(doc["material_id"])
    if "vendor_id" in doc:
        doc["vendor_id"] = str(doc["vendor_id"])
    return doc



# ---------------- Materials ----------------
@router.post("/materials")
def create_material(material: Material):
    result = materials_collection.insert_one(material.dict())
    return serialize(materials_collection.find_one({"_id": result.inserted_id}))

@router.get("/materials")
def list_materials():
    return [serialize(m) for m in materials_collection.find()]

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


# ---------------- Forecasts ----------------
@router.post("/forecasts")
def create_forecast(forecast: Forecast):
    data = forecast.dict()
    data["material_id"] = ObjectId(data["material_id"])
    result = forecasts_collection.insert_one(data)
    return serialize(forecasts_collection.find_one({"_id": result.inserted_id}))

@router.get("/forecasts")
def list_forecasts():
    return [serialize(f) for f in forecasts_collection.find()]


# ---------------- Vendors ----------------
@router.post("/vendors")
def create_vendor(vendor: Vendor):
    result = vendors_collection.insert_one(vendor.dict())
    return serialize(vendors_collection.find_one({"_id": result.inserted_id}))

@router.get("/vendors")
def list_vendors():
    return [serialize(v) for v in vendors_collection.find()]

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

@router.get("/vendor-news")
def list_vendor_news():
    return [serialize(n) for n in vendor_news_collection.find()]