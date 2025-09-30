from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from bson import ObjectId
from bson import ObjectId
from app.db import db
router = APIRouter(prefix="/tech", tags=["Technology & Innovation"])

# ------------------ MongoDB Collections ------------------
patents_collection = db["patents"]
papers_collection = db["research_papers"]
startups_collection = db["startups"]
investors_collection = db["investors"]


# Convert MongoDB document to JSON-serializable dict
def serialize(doc):
    if not doc:
        return None

    def convert(value):
        if isinstance(value, ObjectId):
            return str(value)
        if isinstance(value, list):
            return [convert(v) for v in value]
        if isinstance(value, dict):
            return {k: convert(v) for k, v in value.items()}
        return value

    return {k: convert(v) for k, v in doc.items()}


# Convert list of MongoDB documents to list of JSON-serializable dicts
def serialize_list(docs):
    return [serialize(doc) for doc in docs]

# Validate ObjectId format
def validate_object_id(id_string: str) -> bool:
    try:
        ObjectId(id_string)
        return True
    except:
        return False

# Convert and validate investor IDs
def process_investor_ids(investor_ids: Optional[List[str]]) -> List[ObjectId]:
    if not investor_ids:
        return []
    
    validated_investors = []
    for inv_id in investor_ids:
        if inv_id and inv_id.strip():  # Check if not empty or just whitespace
            if not validate_object_id(inv_id):
                raise HTTPException(status_code=400, detail=f"Invalid investor ID format: {inv_id}")
            validated_investors.append(ObjectId(inv_id))
    return validated_investors
# ------------------ MODELS ------------------
class Patent(BaseModel):
    title: str
    assignee: str
    filing_date: str  # ISO format YYYY-MM-DD
    status: str       # e.g. "Granted", "Pending"
    citations: int
    abstract: str
    industry: str     # <-- Added industry field


class ResearchPaper(BaseModel):
    title: str
    authors: List[str]
    institution: str
    summary: str
    tags: List[str]
    industry: str                # <-- Added
    publication_date: str        # ISO format YYYY-MM-DD
    field_of_study: str          # <-- Added

class Startup(BaseModel):
    name: str
    sector: str
    funding_stage: str  # e.g. Seed, Series A, Series B
    funding_amount: float
    investors: Optional[List[str]] = []  # investor ids (frontend sends them)
    industry: str                        # <-- Added
    location: str                        # <-- Added
    lead_investor: str                   # <-- Added

class Investor(BaseModel):
    name: str
    type: str  # e.g. VC, Angel, PE, Corporate


# ------------------ CRUD APIs ------------------

# ---------- PATENTS ----------
@router.post("/patents")
def create_patent(patent: Patent):
    result = patents_collection.insert_one(patent.dict())
    return serialize(patents_collection.find_one({"_id": result.inserted_id}))
@router.get("/patents")
def get_patents(industry: str | None = None):
    query = {}
    if industry:
        query["industry"] = industry  # filter by industry if provided
    return serialize_list(patents_collection.find(query))
@router.get("/patents/{patent_id}")
def get_patent(patent_id: str):
    patent = patents_collection.find_one({"_id": ObjectId(patent_id)})
    if not patent:
        raise HTTPException(status_code=404, detail="Patent not found")
    return serialize(patent)
@router.put("/patents/{patent_id}")
def update_patent(patent_id: str, patent: Patent):
    result = patents_collection.update_one(
        {"_id": ObjectId(patent_id)}, {"$set": patent.dict()}
    )
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Patent not updated")
    return serialize(patents_collection.find_one({"_id": ObjectId(patent_id)}))
@router.delete("/patents/{patent_id}")
def delete_patent(patent_id: str):
    patents_collection.delete_one({"_id": ObjectId(patent_id)})
    return {"message": "Patent deleted"}


# ---------- RESEARCH PAPERS ----------
@router.post("/papers")
def create_paper(paper: ResearchPaper):
    result = papers_collection.insert_one(paper.dict())
    return serialize(papers_collection.find_one({"_id": result.inserted_id}))
# ---------- GET RESEARCH PAPERS ----------
@router.get("/papers")
def get_papers(industry: str | None = None):
    query = {}
    if industry:
        query["industry"] = industry   # filter if industry provided
    return serialize_list(papers_collection.find(query))
@router.get("/papers/{paper_id}")
def get_paper(paper_id: str):
    paper = papers_collection.find_one({"_id": ObjectId(paper_id)})
    if not paper:
        raise HTTPException(status_code=404, detail="Research paper not found")
    return serialize(paper)

@router.put("/papers/{paper_id}")
def update_paper(paper_id: str, paper: ResearchPaper):
    result = papers_collection.update_one(
        {"_id": ObjectId(paper_id)}, {"$set": paper.dict()}
    )
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Research paper not updated")
    return serialize(papers_collection.find_one({"_id": ObjectId(paper_id)}))

@router.delete("/papers/{paper_id}")
def delete_paper(paper_id: str):
    papers_collection.delete_one({"_id": ObjectId(paper_id)})
    return {"message": "Research paper deleted"}


# ---------- STARTUPS ----------
@router.post("/startups")
def create_startup(startup: Startup):
    data = startup.dict()
    data["investors"] = process_investor_ids(data["investors"])
    result = startups_collection.insert_one(data)
    return serialize(startups_collection.find_one({"_id": result.inserted_id}))

@router.get("/startups")
def get_startups(industry: str | None = None):
    query = {}
    if industry:
        query["industry"] = industry   # filter if industry provided
    return serialize_list(startups_collection.find(query))


@router.get("/startups/{startup_id}")
def get_startup(startup_id: str):
    startup = startups_collection.find_one({"_id": ObjectId(startup_id)})
    if not startup:
        raise HTTPException(status_code=404, detail="Startup not found")
    return serialize(startup)

@router.put("/startups/{startup_id}")
def update_startup(startup_id: str, startup: Startup):
    data = startup.dict()
    data["investors"] = process_investor_ids(data["investors"])
    
    result = startups_collection.update_one(
        {"_id": ObjectId(startup_id)}, {"$set": data}
    )
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Startup not updated")
    return serialize(startups_collection.find_one({"_id": ObjectId(startup_id)}))

@router.delete("/startups/{startup_id}")
def delete_startup(startup_id: str):
    startups_collection.delete_one({"_id": ObjectId(startup_id)})
    return {"message": "Startup deleted"}


# ---------- INVESTORS ----------
@router.post("/investors")
def create_investor(investor: Investor):
    result = investors_collection.insert_one(investor.dict())
    return serialize(investors_collection.find_one({"_id": result.inserted_id}))

@router.get("/investors")
def get_investors():
    return serialize_list(investors_collection.find())

@router.get("/investors/{investor_id}")
def get_investor(investor_id: str):
    investor = investors_collection.find_one({"_id": ObjectId(investor_id)})
    if not investor:
        raise HTTPException(status_code=404, detail="Investor not found")
    return serialize(investor)

@router.put("/investors/{investor_id}")
def update_investor(investor_id: str, investor: Investor):
    result = investors_collection.update_one(
        {"_id": ObjectId(investor_id)}, {"$set": investor.dict()}
    )
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Investor not updated")
    return serialize(investors_collection.find_one({"_id": ObjectId(investor_id)}))

@router.delete("/investors/{investor_id}")
def delete_investor(investor_id: str):
    investors_collection.delete_one({"_id": ObjectId(investor_id)})
    return {"message": "Investor deleted"}
