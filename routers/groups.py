from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
import crud, models, schemas
from database import SessionLocal

router = APIRouter(prefix="/groups", tags=["Groups"])

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.post("/", response_model=schemas.Group)
def create_group(group: schemas.GroupCreate, db: Session = Depends(get_db)):
    return crud.create_group(db, group)

@router.get("/", response_model=List[schemas.Group])
def read_groups(db: Session = Depends(get_db)):
    return crud.get_groups(db)

@router.get("/{group_id}", response_model=schemas.Group)
def read_group(group_id: int, db: Session = Depends(get_db)):
    db_group = crud.get_group(db, group_id)
    if db_group is None:
        raise HTTPException(status_code=404, detail="Group not found")
    return db_group

@router.put("/{group_id}", response_model=schemas.Group)
def update_group(group_id: int, group: schemas.GroupCreate, db: Session = Depends(get_db)):
    db_group = crud.update_group(db, group_id, group)
    if db_group is None:
        raise HTTPException(status_code=404, detail="Group not found")
    return db_group

@router.delete("/{group_id}", response_model=schemas.Group)
def delete_group(group_id: int, db: Session = Depends(get_db)):
    db_group = crud.delete_group(db, group_id)
    if db_group is None:
        raise HTTPException(status_code=404, detail="Group not found")
    return db_group
