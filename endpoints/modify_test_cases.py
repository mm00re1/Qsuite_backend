from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from datetime import datetime
import time
from typing import List

from models.models import TestGroup, TestCase, TestDependency
from dependencies import get_db

router = APIRouter()

class TestCaseCreate(BaseModel):
    group_id: int
    test_name: str
    test_code: str
    free_form: bool
    dependencies: List[int] = []

class TestCaseEdit(BaseModel):
    id: int
    test_name: str = None
    test_code: str = None
    dependencies: List[int] = []


@router.post("/add_test_case/")
async def add_test_case(test_case: TestCaseCreate, db: Session = Depends(get_db)):
    start_time = time.time()
    
    group_id = test_case.group_id
    dependencies = test_case.dependencies

    print("adding dependencies: ", dependencies)

    if not group_id:
        raise HTTPException(status_code=400, detail="Group ID is required")

    test_group = db.query(TestGroup).get(group_id)
    if not test_group:
        raise HTTPException(status_code=404, detail="Test group not found")

    new_test_case = TestCase(
        group_id=test_group.id,
        test_name=test_case.test_name,
        test_code=test_case.test_code,
        creation_date=datetime.utcnow(),
        free_form=test_case.free_form
    )
    db.add(new_test_case)
    db.commit()
    db.refresh(new_test_case)

    for dep_id in dependencies:
        dependency = TestDependency(test_id=new_test_case.id, dependent_test_id=dep_id)
        db.add(dependency)
    db.commit()

    print("time taken to add test case: ", time.time() - start_time)
    return {"message": "Test case added successfully", "id": new_test_case.id}


@router.put("/edit_test_case/")
async def edit_test_case(test_case: TestCaseEdit, db: Session = Depends(get_db)):
    start_time = time.time()
    
    test_case_id = test_case.id
    dependencies = test_case.dependencies

    print("editing dependencies: ", dependencies)

    if not test_case_id:
        raise HTTPException(status_code=400, detail="Test Case ID is required")

    test_case_obj = db.query(TestCase).get(test_case_id)
    if not test_case_obj:
        raise HTTPException(status_code=404, detail="Test case not found")

    if test_case.test_name:
        test_case_obj.test_name = test_case.test_name
    if test_case.test_code:
        test_case_obj.test_code = test_case.test_code
    test_case_obj.last_modified_date = datetime.utcnow()
    db.commit()

    db.query(TestDependency).filter_by(test_id=test_case_obj.id).delete()
    db.commit()

    for dep_id in dependencies:
        dependency = TestDependency(test_id=test_case_obj.id, dependent_test_id=dep_id)
        db.add(dependency)
    db.commit()

    print("time taken to edit test case: ", time.time() - start_time)
    return {"message": "Test case edited successfully"}
