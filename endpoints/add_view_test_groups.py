import requests
import uuid
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from pydantic import BaseModel
from datetime import datetime
from typing import List, Optional
import logging
from uuid import UUID

from models.models import TestGroup, TestCase, TestResult
from dependencies import get_db
from KdbSubs import *
from config.config import SCHEDULER_URL

logger = logging.getLogger(__name__)

router = APIRouter()

class ConnectionTest(BaseModel):
    server: str
    port: int
    tls: bool

class TestGroupCreate(BaseModel):
    name: str
    server: str
    port: int
    schedule: Optional[str] = None
    tls: bool

class TestGroupUpdate(BaseModel):
    name: Optional[str] = None
    server: Optional[str] = None
    port: Optional[int] = None
    schedule: Optional[str] = None
    tls: Optional[bool] = None

@router.post("/test_kdb_connection/")
async def test_kdb_connection(test_group: ConnectionTest, db: Session = Depends(get_db)):
    logger.info("testing kdb connection")
    try:
        # Assuming this function exists and tests the connection to kdb
        result = test_kdb_conn(host=test_group.server, port=test_group.port, tls=test_group.tls)
        return {"message": "success", "details": result}
    except Exception as e:
        return {"message": "failed", "details": str(e)}


@router.post("/upsert_test_group/{group_id}/")
async def upsert_test_group(group_id: UUID, test_group: TestGroupCreate, db: Session = Depends(get_db)):
    logger.info("upserting test group")

    # Check if another group with the same name already exists
    existing_group_with_name = db.query(TestGroup).filter(
        TestGroup.name == test_group.name,
        TestGroup.id != group_id.bytes
    ).first()
    if existing_group_with_name:
        raise HTTPException(status_code=400, detail="A test group with this name already exists")

    # Check if the group already exists
    existing_group = db.get(TestGroup, group_id.bytes)
    if existing_group:
        # Perform update logic
        logger.info(f"Editing existing test group with ID {group_id.hex}")
        if test_group.name is not None:
            existing_group.name = test_group.name
        if test_group.server is not None:
            existing_group.server = test_group.server
        if test_group.port is not None:
            existing_group.port = test_group.port
        if test_group.schedule is not None:
            existing_group.schedule = test_group.schedule
        if test_group.tls is not None:
            existing_group.tls = test_group.tls

        db.commit()

    else:
        # Perform creation logic
        logger.info(f"Creating new test group with ID {group_id.hex}")
        new_test_group = TestGroup(
            id=group_id.bytes,  # Use the provided UUID
            name=test_group.name,
            server=test_group.server,
            port=test_group.port,
            schedule=test_group.schedule,
            tls=test_group.tls
        )
        db.add(new_test_group)
        db.commit()
        db.refresh(new_test_group)

    # Notify the scheduler to add the new job
    try:
        logger.info(f"Sending POST request to {SCHEDULER_URL}/update_job/{group_id.hex}")
        response = requests.post(f"{SCHEDULER_URL}/update_job/{group_id.hex}")
        if response.status_code != 200:
            raise HTTPException(status_code=500, detail="Failed to update scheduler")
    except requests.exceptions.RequestException as e:
        raise HTTPException(status_code=500, detail=f"Scheduler communication error: {e}")

    return {"message": "Test group upserted successfully", "id": group_id.hex}


@router.post("/add_test_group/")
async def add_test_group(test_group: TestGroupCreate, db: Session = Depends(get_db)):
    logger.info("adding test group")
    
    # Use the provided UUID if it exists (e.g., in production)
    new_test_group = TestGroup(
        id=test_group.id.bytes if test_group.id else uuid.uuid4().bytes,
        name=test_group.name,
        server=test_group.server,
        port=test_group.port,
        schedule=test_group.schedule,
        tls=test_group.tls
    )
    db.add(new_test_group)
    db.commit()
    db.refresh(new_test_group)

    # Notify the scheduler to add the new job
    try:
        response = requests.post(f"{SCHEDULER_URL}/update_job/{new_test_group.id.hex}")
        if response.status_code != 200:
            raise HTTPException(status_code=500, detail="Failed to update scheduler")
    except requests.exceptions.RequestException as e:
        raise HTTPException(status_code=500, detail=f"Scheduler communication error: {e}")

    return {"message": "Test group added successfully", "id": new_test_group.id.hex()}


@router.put("/edit_test_group/{id}/")
async def edit_test_group(id: UUID, test_group: TestGroupUpdate, db: Session = Depends(get_db)):
    logger.info("editing test group")
    test_group_obj = db.get(TestGroup, id.bytes)
    if not test_group_obj:
        raise HTTPException(status_code=404, detail="Test group not found")

    if test_group.name is not None:
        test_group_obj.name = test_group.name
    if test_group.server is not None:
        test_group_obj.server = test_group.server
    if test_group.port is not None:
        test_group_obj.port = test_group.port
    if test_group.schedule is not None:
        test_group_obj.schedule = test_group.schedule
    if test_group.tls is not None:
        test_group_obj.tls = test_group.tls

    db.commit()

    # Notify the scheduler to update the job
    try:
        response = requests.post(f"{SCHEDULER_URL}/update_job/{id.hex}")
        if response.status_code != 200:
            raise HTTPException(status_code=500, detail="Failed to update scheduler")
    except requests.exceptions.RequestException as e:
        raise HTTPException(status_code=500, detail=f"Scheduler communication error: {e}")

    return {"message": "Test group updated successfully"}

@router.delete("/delete_test_group/{id}/")
async def delete_test_group(id: UUID, db: Session = Depends(get_db)):
    logger.info(f"deleting test group with id: {id}")
    test_group_obj = db.get(TestGroup, id.bytes)
    if not test_group_obj:
        raise HTTPException(status_code=404, detail="Test group not found")

    db.delete(test_group_obj)
    db.commit()

    # Notify the scheduler to remove the job
    try:
        response = requests.delete(f"{SCHEDULER_URL}/remove_job/{id.hex}")
        if response.status_code != 200:
            raise HTTPException(status_code=500, detail="Failed to update scheduler")
    except requests.exceptions.RequestException as e:
        raise HTTPException(status_code=500, detail=f"Scheduler communication error: {e}")

    return {"message": "Test group deleted successfully"}

@router.get("/test_groups/")
async def get_test_groups(db: Session = Depends(get_db)):
    logger.info("getting test groups")
    test_groups = db.query(TestGroup).all()
    groups_data = [
        {
            "id": group.id.hex(),
            "name": group.name,
            "server": group.server,
            "port": group.port,
            "schedule": group.schedule,
            "tls": group.tls
        } for group in test_groups
    ]
    return groups_data

@router.get("/get_test_group_stats/")
async def get_test_group_stats(date: str, group_id: Optional[UUID] = None, db: Session = Depends(get_db)):
    logger.info("getting test group stats")
    try:
        specific_date = datetime.strptime(date, '%d-%m-%Y').date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format, should be DD-MM-YYYY")

    passed_count_query = db.query(func.count(TestResult.id)).join(TestCase).filter(
        TestResult.date_run == specific_date,
        TestResult.pass_status == True
    )

    failed_count_query = db.query(func.count(TestResult.id)).join(TestCase).filter(
        TestResult.date_run == specific_date,
        TestResult.pass_status == False
    )

    if group_id:
        passed_count_query = passed_count_query.filter(TestCase.group_id == group_id.bytes)
        failed_count_query = failed_count_query.filter(TestCase.group_id == group_id.bytes)

    passed_count = passed_count_query.scalar()
    failed_count = failed_count_query.scalar()

    return {
        "total_passed": passed_count,
        "total_failed": failed_count
    }

