
# Example usage:
# from database import create_document, get_documents, update_document, delete_document
# from schemas import User  # Import your schemas from schemas.py
#
# # Create a user using Pydantic model (REQUIRED - schemas are strictly enforced)
# user = User(username="john_doe", email="john@example.com")
# user_id = create_document("users", user)
#
# # Get all users
# users = get_documents("users")
#
# # Get users with filter
# active_users = get_documents("users", {"status": "active"})
#
# # Update a user (pass Pydantic model or dict with valid fields)
# update_document("users", {"email": "john@example.com"}, {"status": "inactive"})
#
# # Delete a user
# delete_document("users", {"email": "john@example.com"})


from pymongo import MongoClient
from datetime import datetime, timezone
import os
from dotenv import load_dotenv
from typing import Union
from pydantic import BaseModel

# Load environment variables from .env file
load_dotenv()

_client = None
db = None

database_url = os.getenv("DATABASE_URL")
database_name = os.getenv("DATABASE_NAME")

if database_url and database_name:
    _client = MongoClient(database_url)
    db = _client[database_name]

# Helper functions for common database operations
def create_document(collection_name: str, data: Union[BaseModel, dict]):
    """Insert a single document with timestamp

    Args:
        collection_name: Name of the MongoDB collection
        data: Pydantic model instance or dict. Pydantic models are recommended for schema validation.

    Returns:
        str: The inserted document's ID
    """
    if db is None:
        raise Exception("Database not available. Check DATABASE_URL and DATABASE_NAME environment variables.")

    # Convert Pydantic model to dict if needed
    if isinstance(data, BaseModel):
        data_dict = data.model_dump()
    else:
        data_dict = data.copy()

    data_dict['created_at'] = datetime.now(timezone.utc)
    data_dict['updated_at'] = datetime.now(timezone.utc)

    result = db[collection_name].insert_one(data_dict)
    return str(result.inserted_id)

def get_documents(collection_name: str, filter_dict: dict = None, limit: int = None):
    """Get documents from collection"""
    if db is None:
        raise Exception("Database not available. Check DATABASE_URL and DATABASE_NAME environment variables.")
    
    cursor = db[collection_name].find(filter_dict or {})
    if limit:
        cursor = cursor.limit(limit)
    
    return list(cursor)

def update_document(collection_name: str, filter_dict: dict, update_data: Union[BaseModel, dict]):
    """Update a document with timestamp

    Args:
        collection_name: Name of the MongoDB collection
        filter_dict: MongoDB filter to find the document to update
        update_data: Pydantic model instance or dict with fields to update

    Returns:
        bool: True if document was modified, False otherwise
    """
    if db is None:
        raise Exception("Database not available. Check DATABASE_URL and DATABASE_NAME environment variables.")

    # Convert Pydantic model to dict if needed
    if isinstance(update_data, BaseModel):
        update_dict = update_data.model_dump(exclude_unset=True)
    else:
        update_dict = update_data.copy()

    update_dict['updated_at'] = datetime.now(timezone.utc)

    result = db[collection_name].update_one(filter_dict, {"$set": update_dict})
    return result.modified_count > 0

def delete_document(collection_name: str, filter_dict: dict):
    """Delete a document"""
    if db is None:
        raise Exception("Database not initialized. Call enable-database first.")
    
    result = db[collection_name].delete_one(filter_dict)
    return result.deleted_count > 0
