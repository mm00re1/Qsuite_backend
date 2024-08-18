from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from typing import List, Optional
import logging

from models.models import TestResult, TestCase, TestGroup, TestDependency
from dependencies import get_db
from KdbSubs import *

logger = logging.getLogger(__name__)

router = APIRouter()

@router.get("/get_test_info/")
async def get_test_info(
    date: str,
    test_id: int,
    db: Session = Depends(get_db)
):
    logger.info("get_test_info")
    try:
        specific_date = datetime.strptime(date, '%d-%m-%Y').date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format, should be DD-MM-YYYY")

    test_case = db.query(TestCase).join(TestGroup).filter(TestCase.id == test_id).first()

    if not test_case:
        raise HTTPException(status_code=404, detail="Test case not found")

    test_result = db.query(TestResult).filter(
        TestResult.test_case_id == test_id,
        TestResult.date_run == specific_date
    ).first()

    dependencies = db.query(TestDependency).filter(TestDependency.test_id == test_id).all()

    dependent_tests = []
    for dep in dependencies:
        dependent_test_case = db.query(TestCase).filter(TestCase.id == dep.dependent_test_id).first()
        if dependent_test_case:
            dependent_test_result = db.query(TestResult).filter(
                TestResult.test_case_id == dependent_test_case.id,
                TestResult.date_run == specific_date
            ).first()
            dependent_tests.append({
                'test_case_id': dependent_test_case.id,
                'Test Name': dependent_test_case.test_name,
                'Status': dependent_test_result.pass_status if dependent_test_result else None,
                'Error Message': dependent_test_result.error_message if dependent_test_result else None
            })

    last_30_days = datetime.utcnow() - timedelta(days=30)
    last_30_days_results = db.query(TestResult).filter(
        TestResult.test_case_id == test_id,
        TestResult.date_run >= last_30_days
    ).order_by(TestResult.date_run).all()

    dates = [result.date_run.strftime('%Y-%m-%d') for result in last_30_days_results]
    statuses = [1 if result.pass_status else 0 for result in last_30_days_results]
    time_taken = [result.time_taken for result in last_30_days_results]

    test_info = {
        'id': test_case.id,
        'test_name': test_case.test_name,
        'test_code': test_case.test_code,
        'creation_date': test_case.creation_date,
        'free_form': test_case.free_form,
        'group_id': test_case.group.id,
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
    group_id: Optional[int] = None,
    db: Session = Depends(get_db)
):
    logger.info("all_functional_tests")
    if group_id is None:
        raise HTTPException(status_code=400, detail="group_id is required")

    # Query the TestGroup table to get the server, port, and tls values
    test_group = db.query(TestGroup).filter(TestGroup.id == group_id).first()

    if not test_group:
        raise HTTPException(status_code=404, detail="TestGroup not found")

    # Call sendKdbQuery with the fetched parameters
    try:
        TestNames = sendKdbQuery('.qsuite.showAllTests', test_group.server, test_group.port, test_group.tls, [])
        TestNames = TestNames[:limit]
        results = [x.decode('latin') for x in TestNames]
        return {"success": True, "results": results, "message": ""}
    except Exception as e:
        return {"success": False, "results": [], "message": "Kdb Error during retrieval of available q functions => " + str(e)}


@router.get("/view_test_code/")
async def view_test_code(
    group_id: int,
    test_name: str,
    db: Session = Depends(get_db)
):
    logger.info("view_test_code")
    # Query the TestGroup table to get the server, port, and tls values
    test_group = db.query(TestGroup).filter(TestGroup.id == group_id).first()

    if not test_group:
        raise HTTPException(status_code=404, detail="TestGroup not found")

    # Call sendKdbQuery with the fetched parameters
    try:
        test_code = sendKdbQuery('.qsuite.parseTestCode', test_group.server, test_group.port, test_group.tls, test_name)
        results = test_code.decode('latin')
        return {"success": True, "results": results, "message": ""}
    except Exception as e:
        return {"success": False, "results": [], "message": "Kdb Error while reading code for function '" + test_name + "' => " + str(e)}

