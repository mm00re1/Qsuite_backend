from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, case
from pydantic import BaseModel
from datetime import datetime
from typing import List, Optional
from math import floor

from models.models import TestGroup, TestCase, TestResult
from dependencies import get_db
from KdbSubs import *

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
    tls: bool

@router.post("/test_kdb_connection/")
async def test_kdb_connection(test_group: ConnectionTest, db: Session = Depends(get_db)):
    try:
        # Assuming this function exists and tests the connection to kdb
        result = test_kdb_conn(host=test_group.server, port=test_group.port, tls=test_group.tls)
        return {"message": "success", "details": result}

    except Exception as e:
        return {"message": "failed", "details": str(e)}

@router.post("/add_test_group/")
async def add_test_group(test_group: TestGroupCreate, db: Session = Depends(get_db)):
    new_test_group = TestGroup(
        name=test_group.name,
        server=test_group.server,
        port=test_group.port,
        schedule=test_group.schedule,
        tls=test_group.tls
    )
    db.add(new_test_group)
    db.commit()
    return {"message": "Test group added successfully", "id": new_test_group.id}, 201

@router.put("/edit_test_group/{id}/")
async def edit_test_group(id: int, test_group: TestGroupUpdate, db: Session = Depends(get_db)):
    test_group_obj = db.query(TestGroup).get(id)
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
    return {"message": "Test group updated successfully"}

@router.get("/test_groups/")
async def get_test_groups(db: Session = Depends(get_db)):
    test_groups = db.query(TestGroup).all()
    groups_data = [
        {
            "id": group.id,
            "name": group.name,
            "server": group.server,
            "port": group.port,
            "schedule": group.schedule,
            "tls": group.tls
        } for group in test_groups
    ]
    return groups_data

@router.get("/get_test_group_stats/")
async def get_test_group_stats(date: str, group_id: Optional[int] = None, db: Session = Depends(get_db)):
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
        passed_count_query = passed_count_query.filter(TestCase.group_id == group_id)
        failed_count_query = failed_count_query.filter(TestCase.group_id == group_id)

    passed_count = passed_count_query.scalar()
    failed_count = failed_count_query.scalar()

    return {
        "total_passed": passed_count,
        "total_failed": failed_count
    }
