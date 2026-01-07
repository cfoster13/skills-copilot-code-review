from fastapi import APIRouter, Depends, HTTPException, status
from src.backend.database import announcements_collection
from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from src.backend.routers.auth import get_current_user

router = APIRouter()

class Announcement(BaseModel):
    id: Optional[str] = Field(None, alias="_id")
    title: str
    message: str
    start_date: Optional[str] = None
    expiration_date: str
    created_by: Optional[str] = None  # Make optional for input

@router.get("/announcements", response_model=List[Announcement])
def get_announcements():
    now = datetime.now().isoformat()
    announcements = list(announcements_collection.find({
        "$and": [
            {
                "$or": [
                    {"start_date": None},
                    {"start_date": {"$lte": now}}
                ]
            },
            {"expiration_date": {"$gte": now}}
        ]
    }))
    return announcements

def _ensure_announcement_permission(announcement_doc: Optional[Dict[str, Any]], user: Dict[str, Any], action: str) -> None:
    """
    Verify that the current user is allowed to perform the given action on the announcement.

    Allows access if:
    - the announcement exists, and
    - the user is the creator (created_by) or has admin role (user.get("role") == "admin").
    """
    if not announcement_doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Announcement not found")

    username = user.get("username")
    is_admin = user.get("role") == "admin"
    created_by = announcement_doc.get("created_by")

    if not is_admin and created_by != username:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Not authorized to {action} this announcement",
        )


@router.post("/announcements", response_model=Announcement)
def create_announcement(announcement: Announcement, user: Optional[Dict[str, Any]] = Depends(get_current_user)):
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
    data = announcement.dict(by_alias=True)
    # Ensure the creator is always set to the authenticated user, ignoring any client-provided value.
    data["created_by"] = user["username"]
    result = announcements_collection.insert_one(data)
    data["_id"] = str(result.inserted_id)
    return data

@router.get("/announcements/{announcement_id}", response_model=Announcement)
def get_announcement(announcement_id: str):
    announcement = announcements_collection.find_one({"_id": announcement_id})
    if not announcement:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Announcement not found")
    return announcement


@router.put("/announcements/{announcement_id}", response_model=Announcement)
def update_announcement(announcement_id: str, announcement: Announcement, user: Optional[Dict[str, Any]] = Depends(get_current_user)):
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)

    # Load the existing announcement to enforce ownership/admin checks.
    existing_announcement = announcements_collection.find_one({"_id": announcement_id})
    _ensure_announcement_permission(existing_announcement, user, action="update")

    data = announcement.dict(by_alias=True, exclude={"created_by"})
    # Preserve the original creator; do not allow clients to change created_by.
    if existing_announcement and "created_by" in existing_announcement:
        data["created_by"] = existing_announcement["created_by"]

    announcements_collection.update_one({"_id": announcement_id}, {"$set": data})
    data["_id"] = announcement_id
    return data

@router.delete("/announcements/{announcement_id}")
def delete_announcement(announcement_id: str, user: Optional[Dict[str, Any]] = Depends(get_current_user)):
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)

    # Load the existing announcement before attempting to delete, to enforce permissions.
    existing_announcement = announcements_collection.find_one({"_id": announcement_id})
    _ensure_announcement_permission(existing_announcement, user, action="delete")

    announcements_collection.delete_one({"_id": announcement_id})
    return {"success": True}
