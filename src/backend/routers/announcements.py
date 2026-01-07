from fastapi import APIRouter, Depends, HTTPException, status
from pymongo.collection import Collection
from src.backend.database import db, announcements_collection
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field
from src.backend.routers.auth import get_current_user

router = APIRouter()

class Announcement(BaseModel):
    id: Optional[str] = Field(None, alias="_id")
    title: str
    message: str
    start_date: Optional[str] = None
    expiration_date: str
    created_by: str

@router.get("/announcements", response_model=List[Announcement])
def get_announcements():
    now = datetime.now().isoformat()
    announcements = list(announcements_collection.find({
        "$or": [
            {"start_date": None},
            {"start_date": {"$lte": now}}
        ],
        "expiration_date": {"$gte": now}
    }))
    return announcements

@router.post("/announcements", response_model=Announcement)
def create_announcement(announcement: Announcement, user=Depends(get_current_user)):
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
    data = announcement.dict(by_alias=True)
    data["created_by"] = user["username"]
    result = announcements_collection.insert_one(data)
    data["_id"] = str(result.inserted_id)
    return data

@router.put("/announcements/{announcement_id}", response_model=Announcement)
def update_announcement(announcement_id: str, announcement: Announcement, user=Depends(get_current_user)):
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
    data = announcement.dict(by_alias=True)
    result = announcements_collection.update_one({"_id": announcement_id}, {"$set": data})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Announcement not found")
    data["_id"] = announcement_id
    return data

@router.delete("/announcements/{announcement_id}")
def delete_announcement(announcement_id: str, user=Depends(get_current_user)):
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
    result = announcements_collection.delete_one({"_id": announcement_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Announcement not found")
    return {"success": True}
