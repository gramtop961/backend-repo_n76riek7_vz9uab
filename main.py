import os
import inspect
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict, Any, List, Optional

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    return {"message": "Hello from FastAPI Backend!"}

@app.get("/api/hello")
def hello():
    return {"message": "Hello from the backend API!"}

@app.get("/test")
def test_database():
    """Test endpoint to check if database is available and accessible"""
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": []
    }
    
    try:
        # Try to import database module
        from database import db
        
        if db is not None:
            response["database"] = "✅ Available"
            response["database_url"] = "✅ Configured"
            response["database_name"] = db.name if hasattr(db, 'name') else "✅ Connected"
            response["connection_status"] = "Connected"
            
            # Try to list collections to verify connectivity
            try:
                collections = db.list_collection_names()
                response["collections"] = collections[:10]  # Show first 10 collections
                response["database"] = "✅ Connected & Working"
            except Exception as e:
                response["database"] = f"⚠️  Connected but Error: {str(e)[:50]}"
        else:
            response["database"] = "⚠️  Available but not initialized"
            
    except ImportError:
        response["database"] = "❌ Database module not found (run enable-database first)"
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:50]}"
    
    # Check environment variables
    import os
    response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
    response["database_name"] = "✅ Set" if os.getenv("DATABASE_NAME") else "❌ Not Set"
    
    return response

# ============================================================================
# DATABASE VIEWER ENDPOINTS
# ============================================================================

@app.get("/api/database/schemas")
async def get_all_schemas():
    """
    Expose all Pydantic schemas from schemas.py
    Returns a mapping of schema names to their JSON Schema representation
    """
    try:
        import schemas
        schemas_dict = {}
        
        # Get all Pydantic models from schemas module
        for name, obj in inspect.getmembers(schemas):
            # Check if it's a Pydantic model
            if (inspect.isclass(obj) and 
                issubclass(obj, BaseModel) and 
                obj is not BaseModel and
                not name.startswith("_")):
                try:
                    # Get JSON schema for validation
                    schemas_dict[name] = {
                        "json_schema": obj.model_json_schema(),
                        "fields": list(obj.model_fields.keys()),
                        "required_fields": obj.model_json_schema().get("required", [])
                    }
                except Exception as e:
                    print(f"Error processing schema {name}: {e}")
        
        return {"ok": True, "schemas": schemas_dict}
    except ImportError:
        raise HTTPException(status_code=400, detail="Schemas module not found. Define schemas in schemas.py")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error loading schemas: {str(e)}")

@app.get("/api/database/collections")
async def list_collections():
    """
    List all MongoDB collections and their document counts
    """
    try:
        from database import db
        
        if db is None:
            raise HTTPException(status_code=503, detail="Database not connected")
        
        collections = db.list_collection_names()
        collections_info = []
        
        for col_name in collections:
            count = db[col_name].count_documents({})
            collections_info.append({
                "name": col_name,
                "count": count
            })
        
        return {"ok": True, "collections": collections_info}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error listing collections: {str(e)}")

@app.get("/api/database/collections/{collection_name}")
async def get_collection_documents(
    collection_name: str,
    limit: int = 100,
    skip: int = 0,
    filter: Optional[str] = None
):
    """
    Get documents from a collection
    Query params:
    - limit: max documents to return (default 100, max 1000)
    - skip: number of documents to skip (pagination)
    - filter: JSON string filter (e.g., {"status": "active"})
    """
    try:
        from database import db, get_documents
        
        if db is None:
            raise HTTPException(status_code=503, detail="Database not connected")
        
        # Validate collection exists
        if collection_name not in db.list_collection_names():
            raise HTTPException(status_code=404, detail=f"Collection '{collection_name}' not found")
        
        # Limit max documents
        limit = min(limit, 1000)
        
        # Parse filter if provided
        filter_dict = {}
        if filter:
            import json
            try:
                filter_dict = json.loads(filter)
            except json.JSONDecodeError:
                raise HTTPException(status_code=400, detail="Invalid filter JSON")
        
        # Fetch documents
        collection = db[collection_name]
        total = collection.count_documents(filter_dict)
        documents = list(collection.find(filter_dict).skip(skip).limit(limit))
        
        # Convert ObjectId to string for JSON serialization
        for doc in documents:
            if "_id" in doc:
                doc["_id"] = str(doc["_id"])
        
        return {
            "ok": True,
            "collection": collection_name,
            "documents": documents,
            "total": total,
            "limit": limit,
            "skip": skip
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching documents: {str(e)}")

@app.post("/api/database/collections/{collection_name}/validate")
async def validate_document(collection_name: str, document: Dict[str, Any]):
    """
    Validate a document against its Pydantic schema
    """
    try:
        import schemas
        
        # Map collection name to schema
        schema_map = {}
        for name, obj in inspect.getmembers(schemas):
            if (inspect.isclass(obj) and 
                issubclass(obj, BaseModel) and 
                obj is not BaseModel):
                # Convert class name to snake_case collection name
                collection_key = name.lower()
                schema_map[collection_key] = obj
        
        if collection_name not in schema_map:
            return {
                "ok": True,
                "valid": True,
                "message": "No schema defined for this collection, skipping validation"
            }
        
        # Validate document
        schema_class = schema_map[collection_name]
        try:
            schema_class.model_validate(document)
            return {"ok": True, "valid": True}
        except Exception as validation_error:
            # Extract validation errors
            errors = []
            if hasattr(validation_error, "errors"):
                errors = validation_error.errors()
            
            return {
                "ok": True,
                "valid": False,
                "errors": errors
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error validating document: {str(e)}")

@app.post("/api/database/collections/{collection_name}/create")
async def create_document(collection_name: str, document: Dict[str, Any]):
    """
    Create a new document in collection (with schema validation)
    """
    try:
        from database import db, create_document as create_doc
        
        if db is None:
            raise HTTPException(status_code=503, detail="Database not connected")
        
        # Validate first
        validation = await validate_document(collection_name, document)
        if not validation["valid"]:
            raise HTTPException(status_code=400, detail=f"Validation failed: {validation.get('errors', [])}")
        
        # Create document
        doc_id = create_doc(collection_name, document)
        
        return {
            "ok": True,
            "id": doc_id,
            "message": f"Document created in {collection_name}"
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creating document: {str(e)}")

@app.put("/api/database/collections/{collection_name}/{doc_id}")
async def update_document(collection_name: str, doc_id: str, document: Dict[str, Any]):
    """
    Update a document in collection (with schema validation)
    """
    try:
        from database import db, update_document as update_doc
        from bson import ObjectId
        
        if db is None:
            raise HTTPException(status_code=503, detail="Database not connected")
        
        # Validate first
        validation = await validate_document(collection_name, document)
        if not validation["valid"]:
            raise HTTPException(status_code=400, detail=f"Validation failed: {validation.get('errors', [])}")
        
        # Update document
        try:
            obj_id = ObjectId(doc_id)
        except:
            raise HTTPException(status_code=400, detail="Invalid document ID format")
        
        success = update_doc(collection_name, {"_id": obj_id}, document)
        
        if not success:
            raise HTTPException(status_code=404, detail=f"Document not found")
        
        return {
            "ok": True,
            "message": f"Document {doc_id} updated in {collection_name}"
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error updating document: {str(e)}")

@app.delete("/api/database/collections/{collection_name}/{doc_id}")
async def delete_document(collection_name: str, doc_id: str):
    """
    Delete a document from collection
    """
    try:
        from database import db, delete_document as delete_doc
        from bson import ObjectId
        
        if db is None:
            raise HTTPException(status_code=503, detail="Database not connected")
        
        try:
            obj_id = ObjectId(doc_id)
        except:
            raise HTTPException(status_code=400, detail="Invalid document ID format")
        
        success = delete_doc(collection_name, {"_id": obj_id})
        
        if not success:
            raise HTTPException(status_code=404, detail=f"Document not found")
        
        return {
            "ok": True,
            "message": f"Document {doc_id} deleted from {collection_name}"
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error deleting document: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
