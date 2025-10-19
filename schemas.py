"""
Database Schemas

Define your MongoDB collection schemas here using Pydantic models or simple dictionaries.
This file serves as the single source of truth for your data structure.

Import these schemas in your main.py when validating requests/responses.
"""

# Example User Schema (delete this and add your own)
"""
Example usage with Pydantic:

from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime

class User(BaseModel):
    id: Optional[str] = None
    username: str
    email: EmailStr
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

# In main.py:
# @app.post("/users")
# async def create_user(user: User):
#     user_dict = user.model_dump()
#     user_id = create_document("users", user_dict)
#     return {"id": user_id, **user_dict}
"""

# Add your schemas below:
# --------------------------------------------------
