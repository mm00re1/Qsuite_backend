from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from datetime import datetime
import time
from typing import List
import logging
from uuid import UUID

from models.models import TestResult, TestCase, TestDependency
from dependencies import get_db

logger = logging.getLogger(__name__)

router = APIRouter()


class TestCaseUpsert(BaseModel):
    id: UUID
    group_id: UUID
    test_name: str
    test_code: str
    test_type: str  # "Functional", "Free-Form", or "Subscription"
    dependencies: List[UUID] = []

@router.post("/upsert_test_case/")
async def upsert_test_case(test_case: TestCaseUpsert, db: Session = Depends(get_db)):
    start_time = time.time()

    # Check if a test case with the same name already exists (excluding the current test case)
    existing_name = db.query(TestCase).filter(
        TestCase.test_name == test_case.test_name,
        TestCase.id != test_case.id.bytes
    ).first()

    if existing_name:
        raise HTTPException(status_code=400, detail="A test case with this name already exists")

    # Attempt to find an existing test case by ID
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
            test_type=test_case.test_type,
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


@router.delete("/delete_test_case/{test_case_id}")
async def delete_test_case(test_case_id: UUID, db: Session = Depends(get_db)):
    logger.info(f"Deleting test case with ID: {test_case_id}")
    start_time = time.time()

    test_case = db.get(TestCase, test_case_id.bytes)
    if not test_case:
        raise HTTPException(status_code=404, detail="Test case not found")

    # Delete associated test results
    db.query(TestResult).filter(TestResult.test_case_id == test_case_id.bytes).delete()

    # Delete associated dependencies
    db.query(TestDependency).filter(
        (TestDependency.test_id == test_case_id.bytes) | 
        (TestDependency.dependent_test_id == test_case_id.bytes)
    ).delete()

    # Delete the test case
    db.delete(test_case)
    db.commit()

    logger.info(f"Time taken to delete test case: {time.time() - start_time}")
    return {"message": "Test case deleted successfully"}
