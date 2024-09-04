from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from datetime import datetime
import time
from typing import List, Optional
import logging
from uuid import UUID

from models.models import TestGroup, TestCase, TestDependency
from dependencies import get_db

logger = logging.getLogger(__name__)

router = APIRouter()


class TestCaseUpsert(BaseModel):
    id: UUID
    group_id: UUID
    test_name: str
    test_code: str
    free_form: bool
    dependencies: List[UUID] = []

@router.post("/upsert_test_case/")
async def upsert_test_case(test_case: TestCaseUpsert, db: Session = Depends(get_db)):
    logger.info("upsert_test_case")
    start_time = time.time()

    # Check if a test case with the same name already exists (excluding the current test case)
    existing_name = db.query(TestCase).filter(
        TestCase.test_name == test_case.test_name,
        TestCase.id != test_case.id.bytes
    ).first()

    if existing_name:
        raise HTTPException(status_code=400, detail="A test case with this name already exists")

    existing_test_case = db.get(TestCase, test_case.id.bytes)

    if existing_test_case:
        # Update existing test case
        existing_test_case.test_name = test_case.test_name
        existing_test_case.test_code = test_case.test_code
        
        # Remove existing dependencies
        db.query(TestDependency).filter_by(test_id=existing_test_case.id).delete()
        message = "Test case edited successfully"

    else:
        # Create new test case
        existing_test_case = TestCase(
            id=test_case.id.bytes,
            group_id=test_case.group_id.bytes,
            test_name=test_case.test_name,
            test_code=test_case.test_code,
            creation_date=datetime.utcnow(),
            free_form=test_case.free_form
        )
        db.add(existing_test_case)
        message = "Test case added successfully"

    db.commit()
    db.refresh(existing_test_case)

    # Add new dependencies
    for dep_id in test_case.dependencies:
        new_dependency = TestDependency(test_id=existing_test_case.id, dependent_test_id=dep_id.bytes)
        db.add(new_dependency)

    db.commit()

    print("time taken to upsert test case: ", time.time() - start_time)
    return {"message": message, "id": existing_test_case.id.hex()}

