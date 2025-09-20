from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from bson import ObjectId
from app.db import db

router = APIRouter(prefix="/dashboard", tags=["Projects & Dashboard"])

projects_collection = db["projects"]
suppliers_collection = db["suppliers"]
market_scores_collection = db["market_scores"]
domains_collection = db["domains"]
# ---------------------- Models ----------------------
class Project(BaseModel):
    user_id: str
    title: str
    domain_id: str   # now frontend will send domain _id
    status: str


class Supplier(BaseModel):
    user_id: str
    name: str
    location: str
    risk_score: int
    status: str

class MarketScore(BaseModel):
    user_id: str
    domain: str
    score: int
    date: str

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
def get_market_scores(user_id: str = Query(...)):
    return [serialize(m) for m in market_scores_collection.find({"user_id": ObjectId(user_id)})]

@router.post("/market-scores")
def create_market_score(market_score: MarketScore):
    data = market_score.dict()
    data["user_id"] = ObjectId(data["user_id"])
    result = market_scores_collection.insert_one(data)
    return serialize(market_scores_collection.find_one({"_id": result.inserted_id}))

@router.delete("/market-scores/{market_score_id}")
def delete_market_score(market_score_id: str, user_id: str = Query(...)):
    result = market_scores_collection.delete_one({"_id": ObjectId(market_score_id), "user_id": ObjectId(user_id)})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Market score not found or not authorized")
    return {"message": f"Market score {market_score_id} deleted"}
