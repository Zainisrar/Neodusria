from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from bson import ObjectId
from app.db import db
router = APIRouter(prefix="/compliance", tags=["Compliance & Regulation"])

# ------------------ MongoDB Collections ------------------
regulations_collection = db["regulations"]
standards_collection = db["standards"]
project_compliance_collection = db["project_compliance"]

# Convert MongoDB document to JSON-serializable dict
def serialize(doc):
    if not doc:
        return None
    doc["_id"] = str(doc["_id"])
    return doc

# Convert list of MongoDB documents to list of JSON-serializable dicts
def serialize_list(docs):
    return [serialize(doc) for doc in docs]

# Serialize project compliance document with ObjectId fields
def serialize_project_compliance(doc):
    if not doc:
        return None
    return {
        "_id": str(doc["_id"]),
        "project_id": str(doc["project_id"]),
        "standard_id": str(doc["standard_id"]),
        "status": doc["status"]
    }

# ------------------ Helper ------------------
def validate_object_id(id_value: str, field_name: str = "ID"):
    """Validate and convert a string to ObjectId safely."""
    try:
        return ObjectId(id_value)
    except Exception:
        raise HTTPException(status_code=400, detail=f"Invalid {field_name} format: {id_value}")

# ------------------ Pydantic Models ------------------
class Regulation(BaseModel):
    title: str
    body: str
    status: str
    draft_date: Optional[str] = None
    comment_end: Optional[str] = None
    enact_date: Optional[str] = None

class Standard(BaseModel):
    title: str
    body: str
    status: str
    scope: Optional[str] = None
    publication_date: Optional[str] = None

class ProjectCompliance(BaseModel):
    project_id: str  # <- Will be converted to ObjectId
    standard_id: str  # <- Will be converted to ObjectId
    status: str = "pending"  # Default status

# ------------------ Regulations CRUD ------------------
@router.post("/regulations")
def create_regulation(regulation: Regulation):
    data = regulation.dict()
    result = regulations_collection.insert_one(data)
    return serialize(regulations_collection.find_one({"_id": result.inserted_id}))

@router.get("/regulations")
def list_regulations():
    return serialize_list(regulations_collection.find())

@router.get("/regulations/{reg_id}")
def get_regulation(reg_id: str):
    reg_id = validate_object_id(reg_id, "regulation ID")
    regulation = regulations_collection.find_one({"_id": reg_id})
    if not regulation:
        raise HTTPException(status_code=404, detail="Regulation not found")
    return serialize(regulation)

@router.put("/regulations/{reg_id}")
def update_regulation(reg_id: str, regulation: Regulation):
    reg_id = validate_object_id(reg_id, "regulation ID")
    update_result = regulations_collection.update_one({"_id": reg_id}, {"$set": regulation.dict()})
    if update_result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Regulation not found")
    return serialize(regulations_collection.find_one({"_id": reg_id}))

@router.delete("/regulations/{reg_id}")
def delete_regulation(reg_id: str):
    reg_id = validate_object_id(reg_id, "regulation ID")
    delete_result = regulations_collection.delete_one({"_id": reg_id})
    if delete_result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Regulation not found")
    return {"message": "Regulation deleted successfully"}

# ------------------ Standards CRUD ------------------
@router.post("/standards")
def create_standard(standard: Standard):
    data = standard.dict()
    result = standards_collection.insert_one(data)
    return serialize(standards_collection.find_one({"_id": result.inserted_id}))

@router.get("/standards")
def list_standards():
    return serialize_list(standards_collection.find())

@router.get("/standards/{std_id}")
def get_standard(std_id: str):
    std_id = validate_object_id(std_id, "standard ID")
    standard = standards_collection.find_one({"_id": std_id})
    if not standard:
        raise HTTPException(status_code=404, detail="Standard not found")
    return serialize(standard)

@router.put("/standards/{std_id}")
def update_standard(std_id: str, standard: Standard):
    std_id = validate_object_id(std_id, "standard ID")
    update_result = standards_collection.update_one({"_id": std_id}, {"$set": standard.dict()})
    if update_result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Standard not found")
    return serialize(standards_collection.find_one({"_id": std_id}))

@router.delete("/standards/{std_id}")
def delete_standard(std_id: str):
    std_id = validate_object_id(std_id, "standard ID")
    delete_result = standards_collection.delete_one({"_id": std_id})
    if delete_result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Standard not found")
    return {"message": "Standard deleted successfully"}

# ------------------ CRUD: Project Compliance ------------------
@router.post("/project_compliance")
def create_project_compliance(pc: ProjectCompliance):
    # Validate ObjectIds with specific error messages
    project_id = validate_object_id(pc.project_id, "project_id")
    standard_id = validate_object_id(pc.standard_id, "standard_id")

    data = {
        "project_id": project_id,
        "standard_id": standard_id,
        "status": pc.status
    }
    result = project_compliance_collection.insert_one(data)
    return serialize_project_compliance(project_compliance_collection.find_one({"_id": result.inserted_id}))

@router.get("/project_compliance")
def list_project_compliance():
    return [serialize_project_compliance(pc) for pc in project_compliance_collection.find()]

@router.get("/project_compliance/{pc_id}")
def get_project_compliance(pc_id: str):
    pc_id = validate_object_id(pc_id, "project compliance ID")
    pc = project_compliance_collection.find_one({"_id": pc_id})
    if not pc:
        raise HTTPException(status_code=404, detail="Project compliance record not found")
    return serialize_project_compliance(pc)
@router.put("/project-compliance/{pc_id}")
def update_project_compliance(pc_id: str, pc: ProjectCompliance):
    pc_id = validate_object_id(pc_id, "project compliance ID")
    data = pc.dict()
    data["project_id"] = validate_object_id(data["project_id"], "project ID")
    data["standard_id"] = validate_object_id(data["standard_id"], "standard ID")
    update_result = project_compliance_collection.update_one({"_id": pc_id}, {"$set": data})
    if update_result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Project compliance record not found")
    return serialize_project_compliance(project_compliance_collection.find_one({"_id": pc_id}))

@router.delete("/project-compliance/{pc_id}")
def delete_project_compliance(pc_id: str):
    pc_id = validate_object_id(pc_id, "project compliance ID")
    delete_result = project_compliance_collection.delete_one({"_id": pc_id})
    if delete_result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Project compliance record not found")
    return {"message": "Project compliance record deleted successfully"}
