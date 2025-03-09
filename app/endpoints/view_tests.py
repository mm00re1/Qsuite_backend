from fastapi import APIRouter, Depends, HTTPException, Query, Body
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from typing import List, Optional
import logging
from uuid import UUID
import time
from pydantic import BaseModel

from models.models import TestResult, TestCase, TestGroup, TestDependency
from dependencies import get_db
from KdbSubs import *

logger = logging.getLogger(__name__)

router = APIRouter()

@router.get("/get_test_info/")
async def get_test_info(
    date: str,
    test_result_id: UUID,
    db: Session = Depends(get_db)
):
    logger.info("get_test_info")

    try:
        specific_date = datetime.strptime(date, '%d-%m-%Y').date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format, should be DD-MM-YYYY")

    # Step 1: Retrieve the TestResult to get the test_case_id
    test_result = db.query(TestResult).filter(
        TestResult.id == test_result_id.bytes,
        TestResult.date_run == specific_date
    ).first()

    if not test_result:
        raise HTTPException(status_code=404, detail="Test result not found")

    # Step 2: Retrieve the TestCase using test_case_id from TestResult
    test_case = db.query(TestCase).filter(TestCase.id == test_result.test_case_id).first()

    if not test_case:
        raise HTTPException(status_code=404, detail="Test case not found")

    dependencies = db.query(TestDependency).filter(TestDependency.test_id == test_case.id).all()

    dependent_tests = []
    for dep in dependencies:
        dependent_test_case = db.query(TestCase).filter(TestCase.id == dep.dependent_test_id).first()
        if dependent_test_case:
            dependent_test_result = db.query(TestResult).filter(
                TestResult.test_case_id == dependent_test_case.id,
                TestResult.date_run == specific_date
            ).first()
            dependent_tests.append({
                'test_case_id': dependent_test_case.id.hex(),
                'Test Name': dependent_test_case.test_name,
                'Status': dependent_test_result.pass_status if dependent_test_result else None,
                'Error Message': dependent_test_result.error_message if dependent_test_result else None
            })

    last_30_days = datetime.utcnow() - timedelta(days=30)
    last_30_days_results = db.query(TestResult).filter(
        TestResult.test_case_id == test_case.id,
        TestResult.date_run >= last_30_days
    ).order_by(TestResult.date_run).all()

    dates = [result.date_run.strftime('%Y-%m-%d') for result in last_30_days_results]
    statuses = [1 if result.pass_status else 0 for result in last_30_days_results]
    time_taken = [result.time_taken for result in last_30_days_results]

    test_info = {
        'id': test_case.id.hex(),
        'test_name': test_case.test_name,
        'test_code': test_case.test_code,
        'creation_date': test_case.creation_date,
        'test_type': test_case.test_type,
        'group_id': test_case.group.id.hex(),
        'group_name': test_case.group.name,
        'dependent_tests': dependent_tests,
        'dependent_tests_columns': ["Test Name", "Status", "Error Message"],
        'last_30_days_dates': dates,
        'last_30_days_statuses': statuses,
        'last_30_days_timeTaken': time_taken
    }

    if test_result:
        test_info.update({
            'time_taken': test_result.time_taken,
            'pass_status': test_result.pass_status,
            'error_message': test_result.error_message,
        })
    else:
        test_info.update({
            'time_taken': None,
            'pass_status': None,
            'error_message': None,
        })

    return test_info

@router.get("/all_functional_tests/")
async def all_functional_tests(
    limit: int = 10,
    group_id: Optional[UUID] = None,
    db: Session = Depends(get_db)
):
    logger.info("all_functional_tests")
    if group_id is None:
        raise HTTPException(status_code=400, detail="group_id is required")

    # Query the TestGroup table to get the server, port, and tls values
    test_group = db.query(TestGroup).filter(TestGroup.id == group_id.bytes).first()

    if not test_group:
        raise HTTPException(status_code=404, detail="TestGroup not found")

    # Call sendKdbQuery with the fetched parameters
    try:
        TestNames = sendKdbQuery('.qsuite.showAllTests', test_group.server, test_group.port, test_group.tls, test_group.scope, [])
        TestNames = TestNames[:limit]
        results = [x.decode('latin') for x in TestNames]
        return {"success": True, "results": results, "message": ""}
    except Exception as e:
        return {"success": False, "results": [], "message": "Kdb Error during retrieval of available q functions => " + str(e)}

@router.get("/all_subscription_tests/")
async def all_subscription_tests(
    limit: int = 10,
    group_id: Optional[UUID] = None,
    db: Session = Depends(get_db)
):
    logger.info("all_subscription_tests")
    if group_id is None:
        raise HTTPException(status_code=400, detail="group_id is required")

    # Query the TestGroup table to get the server, port, and tls values
    test_group = db.query(TestGroup).filter(TestGroup.id == group_id.bytes).first()

    if not test_group:
        raise HTTPException(status_code=404, detail="TestGroup not found")

    # Call sendKdbQuery with the fetched parameters
    try:
        TestNames = sendKdbQuery('.qsuite.showAllSubTests', test_group.server, test_group.port, test_group.tls, test_group.scope, [])
        TestNames = TestNames[:limit]
        results = [x.decode('latin') for x in TestNames]
        return {"success": True, "results": results, "message": ""}
    except Exception as e:
        return {"success": False, "results": [], "message": "Kdb Error during retrieval of available q sub functions => " + str(e)}

@router.get("/view_test_code/")
async def view_test_code(
    group_id: UUID,
    test_name: str,
    db: Session = Depends(get_db)
):
    logger.info("view_test_code")
    # Query the TestGroup table to get the server, port, and tls values
    test_group = db.query(TestGroup).filter(TestGroup.id == group_id.bytes).first()

    if not test_group:
        raise HTTPException(status_code=404, detail="TestGroup not found")

    # Call sendKdbQuery with the fetched parameters
    try:
        test_code = sendKdbQuery('.qsuite.parseTestCode', test_group.server, test_group.port, test_group.tls, test_group.scope, test_name)
        results = test_code.decode('latin')
        return {"success": True, "results": results, "message": ""}
    except Exception as e:
        return {"success": False, "results": [], "message": "Kdb Error while reading code for function '" + test_name + "' => " + str(e)}


@router.get("/get_tests_per_group/")
async def get_test_ids(
    group_id: UUID,
    db: Session = Depends(get_db)
):
    logger.info("get_test_ids")
    stTime = time.time()

    # Check if the group_id is in the TestGroup table
    test_group = db.query(TestGroup).filter(TestGroup.id == group_id.bytes).first()
    if not test_group:
        raise HTTPException(status_code=404, detail="TestGroup not found")

    try:
        # Query all test cases for the group
        test_cases = db.query(TestCase).filter(TestCase.group_id == group_id.bytes).all()

        # Get all test IDs
        test_ids = [test.id for test in test_cases]

        # Query all dependencies for these tests in a single query
        dependencies = db.query(TestDependency).filter(TestDependency.test_id.in_(test_ids)).all()

        # Create a dictionary to store dependencies for each test
        dependency_map = {test_id: [] for test_id in test_ids}
        for dep in dependencies:
            dependency_map[dep.test_id].append(dep.dependent_test_id.hex())

        # Format the response with all information including dependencies
        results_data = []
        for test in test_cases:
            results_data.append({
                'test_case_id': test.id.hex(),
                'Test Name': test.test_name,
                'Creation Date': test.creation_date,
                'test_type': test.test_type,
                'test_code': test.test_code,
                'dependencies': dependency_map[test.id]
            })

        logger.info(f"timeTaken for db query: {time.time() - stTime}")

        return {
            "test_data": results_data,
        }

    except Exception as e:
        logger.error(f"Error fetching test cases and dependencies: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")
