from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from bson import ObjectId
from app.db import db
from fastapi import Query
router = APIRouter(prefix="/competitive", tags=["Competitive Intelligence"])

# ------------------ MongoDB Collections ------------------
competitors_collection = db["competitors"]
competitor_events_collection = db["competitor_events"]
competitor_personnel_collection = db["competitor_personnel"]
competitor_signals_collection = db["competitor_signals"]
competitor_locations_collection = db["competitor_locations"]

# ------------------ Pydantic Models ------------------
class Competitor(BaseModel):
    name: str
    hq: str
    revenue: Optional[float]
    employees: Optional[int]
    logo: Optional[str]  # store image URL or base64 string
    industry: str

class CompetitorEvent(BaseModel):
    competitor_id: str
    type: str
    description: str
    date: str

class CompetitorPersonnel(BaseModel):
    competitor_id: str
    name: str
    role: str
    type: str
    date: str

class CompetitorSignal(BaseModel):
    competitor_id: str
    type: str
    title: str
    source: str
    snippet: str
    date: str

class CompetitorLocation(BaseModel):
    competitor_id: str
    type: str
    name: str
    location: str
    status: str

# ------------------ Helper ------------------
def validate_objectid(id_str: str, field_name: str):
    try:
        return ObjectId(id_str)
    except Exception:
        raise HTTPException(status_code=400, detail=f"Invalid {field_name} format: {id_str}")

# ------------------ CRUD: Competitors ------------------
@router.post("/competitors")
def create_competitor(comp: Competitor):
    result = competitors_collection.insert_one(comp.dict())
    return {"id": str(result.inserted_id)}

@router.get("/competitors")
def list_competitors(industry: str = Query(None, description="Filter by industry")):
    query = {}
    if industry:
        query["industry"] = industry  # match industry field in MongoDB

    competitors = [
        {**c, "_id": str(c["_id"])}
        for c in competitors_collection.find(query)
    ]
    return competitors

# ------------------ CRUD: Competitor Events ------------------
@router.post("/events")
def create_competitor_event(event: CompetitorEvent):
    data = event.dict()
    data["competitor_id"] = validate_objectid(data["competitor_id"], "competitor_id")
    result = competitor_events_collection.insert_one(data)
    return {"id": str(result.inserted_id)}

@router.get("/events")
def list_competitor_events(competitor_id: Optional[str] = None):
    query = {}
    if competitor_id:
        query["competitor_id"] = validate_objectid(competitor_id, "competitor_id")
    return [
        {
            "_id": str(e["_id"]),
            "competitor_id": str(e["competitor_id"]),
            **{k: v for k, v in e.items() if k not in ["_id", "competitor_id"]}
        }
        for e in competitor_events_collection.find(query)
    ]

# ------------------ CRUD: Competitor Personnel ------------------
@router.post("/personnel")
def create_competitor_personnel(personnel: CompetitorPersonnel):
    data = personnel.dict()
    data["competitor_id"] = validate_objectid(data["competitor_id"], "competitor_id")
    result = competitor_personnel_collection.insert_one(data)
    return {"id": str(result.inserted_id)}

@router.get("/personnel")
def list_competitor_personnel(competitor_id: Optional[str] = None):
    query = {}
    if competitor_id:
        query["competitor_id"] = validate_objectid(competitor_id, "competitor_id")
    return [
        {
            "_id": str(p["_id"]),
            "competitor_id": str(p["competitor_id"]),
            **{k: v for k, v in p.items() if k not in ["_id", "competitor_id"]}
        }
        for p in competitor_personnel_collection.find(query)
    ]

# ------------------ CRUD: Competitor Signals ------------------
@router.post("/signals")
def create_competitor_signal(signal: CompetitorSignal):
    data = signal.dict()
    data["competitor_id"] = validate_objectid(data["competitor_id"], "competitor_id")
    result = competitor_signals_collection.insert_one(data)
    return {"id": str(result.inserted_id)}

@router.get("/signals")
def list_competitor_signals(competitor_id: Optional[str] = None):
    query = {}
    if competitor_id:
        query["competitor_id"] = validate_objectid(competitor_id, "competitor_id")
    return [
        {
            "_id": str(s["_id"]),
            "competitor_id": str(s["competitor_id"]),
            **{k: v for k, v in s.items() if k not in ["_id", "competitor_id"]}
        }
        for s in competitor_signals_collection.find(query)
    ]

# ------------------ CRUD: Competitor Locations ------------------
@router.post("/locations")
def create_competitor_location(location: CompetitorLocation):
    data = location.dict()
    data["competitor_id"] = validate_objectid(data["competitor_id"], "competitor_id")
    result = competitor_locations_collection.insert_one(data)
    return {"id": str(result.inserted_id)}

@router.get("/locations")
def list_competitor_locations(competitor_id: Optional[str] = None):
    query = {}
    if competitor_id:
        query["competitor_id"] = validate_objectid(competitor_id, "competitor_id")
    return [
        {
            "_id": str(l["_id"]),
            "competitor_id": str(l["competitor_id"]),
            **{k: v for k, v in l.items() if k not in ["_id", "competitor_id"]}
        }
        for l in competitor_locations_collection.find(query)
    ]
