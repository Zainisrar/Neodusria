from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from bson import ObjectId
from app.db import db

router = APIRouter(prefix="/dashboard", tags=["Projects & Dashboard"])

projects_collection = db["projects"]
suppliers_collection = db["suppliers"]
market_scores_collection = db["market_scores"]
domains_collection = db["domains"]
commodity_prices_collection = db["commodity_prices"]
risks_collection = db["risks"]
# ---------------------- Models ----------------------
class Project(BaseModel):
    user_id: str
    title: str
    domain_id: str   # now frontend will send domain _id
    status: str

class CommodityPrice(BaseModel):
    commodity: str   # e.g., Oil, Copper, Gas
    date: str        # YYYY-MM-DD
    price: float


class Supplier(BaseModel):
    user_id: str
    name: str
    location: str
    risk_score: int
    status: str

class MarketScore(BaseModel):
    domain: str
    score: int
    date: str

class Risk(BaseModel):
    name: str
    likelihood: int  # 1–5 scale
    impact: int      # 1–5 scale
    category: str    # e.g., supplier, regulation, technology

def serialize(document):
    """Convert MongoDB ObjectId → str for JSON response"""
    if not document:
        return None
    document["_id"] = str(document["_id"])
    return document
def serialize(document):
    """
    Convert MongoDB document (with ObjectId) to JSON-serializable dict.
    """
    if not document:
        return None

    document["_id"] = str(document["_id"])
    if "user_id" in document:
        document["user_id"] = str(document["user_id"])
    if "domain_id" in document:
        document["domain_id"] = str(document["domain_id"])
    return document


# ---------------------- PROJECTS CRUD ----------------------
@router.get("/projects")
def get_projects(user_id: str = Query(...)):
    return [serialize(p) for p in projects_collection.find({"user_id": ObjectId(user_id)})]

@router.post("/projects")
def create_project(project: Project):
    try:
        # Convert ids
        user_id = ObjectId(project.user_id)
        domain_id = ObjectId(project.domain_id)

        # Validate domain
        domain_doc = domains_collection.find_one({"_id": domain_id})
        if not domain_doc:
            raise HTTPException(status_code=404, detail="Domain not found")

        # Prepare project data
        data = {
            "user_id": user_id,
            "title": project.title,
            "domain_id": domain_id,
            "domain": domain_doc["name"],  # store name for readability
            "status": project.status
        }

        # Insert
        result = projects_collection.insert_one(data)
        inserted_project = projects_collection.find_one({"_id": result.inserted_id})

        # Serialize before returning
        return serialize(inserted_project)

    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error creating project: {str(e)}")

@router.delete("/projects/{project_id}")
def delete_project(project_id: str, user_id: str = Query(...)):
    result = projects_collection.delete_one({"_id": ObjectId(project_id), "user_id": ObjectId(user_id)})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Project not found or not authorized")
    return {"message": f"Project {project_id} deleted"}

# ---------------------- SUPPLIERS CRUD ----------------------
@router.get("/suppliers")
def get_suppliers(user_id: str = Query(...)):
    return [serialize(s) for s in suppliers_collection.find({"user_id": ObjectId(user_id)})]

@router.post("/suppliers")
def create_supplier(supplier: Supplier):
    data = supplier.dict()
    data["user_id"] = ObjectId(data["user_id"])
    result = suppliers_collection.insert_one(data)
    return serialize(suppliers_collection.find_one({"_id": result.inserted_id}))

@router.delete("/suppliers/{supplier_id}")
def delete_supplier(supplier_id: str, user_id: str = Query(...)):
    result = suppliers_collection.delete_one({"_id": ObjectId(supplier_id), "user_id": ObjectId(user_id)})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Supplier not found or not authorized")
    return {"message": f"Supplier {supplier_id} deleted"}

# ---------------------- MARKET SCORES CRUD ----------------------
@router.get("/market-scores")
def get_market_scores():
    return [serialize(m) for m in market_scores_collection.find()]

@router.post("/market-scores")
def create_market_score(market_score: MarketScore):
    data = market_score.dict()
    result = market_scores_collection.insert_one(data)
    return serialize(market_scores_collection.find_one({"_id": result.inserted_id}))

@router.delete("/market-scores/{market_score_id}")
def delete_market_score(market_score_id: str, user_id: str = Query(...)):
    result = market_scores_collection.delete_one({"_id": ObjectId(market_score_id), "user_id": ObjectId(user_id)})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Market score not found or not authorized")
    return {"message": f"Market score {market_score_id} deleted"}

# ---------------------- COMMODITY PRICES ----------------------

@router.post("/commodity-prices")
def create_commodity_price(price: CommodityPrice):
    """
    Insert a new commodity price record (no user ID required).
    """
    try:
        data = price.dict()

        # Insert into collection
        result = commodity_prices_collection.insert_one(data)

        inserted_doc = commodity_prices_collection.find_one({"_id": result.inserted_id})
        return serialize(inserted_doc)

    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error creating commodity price: {str(e)}")


@router.get("/commodity-prices")
def get_commodity_prices(commodity: str = Query(None)):
    """
    Fetch last 10 days of commodity prices (optionally filter by commodity type).
    """
    query = {}
    if commodity:
        query["commodity"] = commodity

    docs = (
        commodity_prices_collection
        .find(query)
        .sort("date", -1)   # latest first
        .limit(10)
    )

    return [serialize(d) for d in docs]
    """
    Fetch last 10 days of commodity prices for a user (optionally filtered by commodity type).
    """
    query = {"user_id": ObjectId(user_id)}
    if commodity:
        query["commodity"] = commodity

    docs = (
        commodity_prices_collection
        .find(query)
        .sort("date", -1)   # sort by date descending
        .limit(10)
    )

    return [serialize(d) for d in docs]



# ---------------------- Risk Endpoints ----------------------
@router.post("/risks")
def add_risk(risk: Risk):
    """Add a new risk to the heatmap"""
    if risk.likelihood < 1 or risk.likelihood > 5:
        raise HTTPException(status_code=400, detail="Likelihood must be 1–5")
    if risk.impact < 1 or risk.impact > 5:
        raise HTTPException(status_code=400, detail="Impact must be 1–5")

    result = risks_collection.insert_one(risk.dict())
    inserted_risk = risks_collection.find_one({"_id": result.inserted_id})
    return serialize(inserted_risk)

@router.get("/all")
def get_risks():
    """Get all risks for heatmap"""
    return [serialize(r) for r in risks_collection.find()]