from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from datetime import datetime
from typing import List, Optional
import logging
from uuid import UUID

from models.models import TestResult, TestCase, TestGroup
from dependencies import get_db
from KdbSubs import *

logger = logging.getLogger(__name__)

router = APIRouter()

@router.get("/get_tests_by_ids/")
async def get_tests_by_ids(
    test_ids: str,
    date: str,
    group_id: Optional[UUID] = None,
    run_number: Optional[int] = None,
    db: Session = Depends(get_db)
):
    logger.info("get_tests_by_ids")
    try:
        specific_date = datetime.strptime(date, '%d-%m-%Y').date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format, should be DD-MM-YYYY")

    if not test_ids:
        raise HTTPException(status_code=400, detail="Test IDs are required")

    try:
        test_ids_list = [UUID(id_str).bytes for id_str in test_ids.split(',')]
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid test IDs format, should be a comma-separated list of UUIDs")

    query = db.query(TestResult).join(TestCase).join(TestGroup).filter(
        TestResult.date_run == specific_date,
        TestCase.id.in_(test_ids_list)
    )

    if run_number is not None:
        query = query.filter(TestResult.run_number == run_number)

    if group_id:
        query = query.filter(TestCase.group_id == group_id.bytes)

    test_results = query.all()
    found_test_ids = {result.test_case_id for result in test_results}
    missing_test_ids = set(test_ids_list) - found_test_ids

    missing_test_cases = db.query(TestCase).filter(TestCase.id.in_(missing_test_ids)).all()

    results_data = []
    for result in test_results:
        results_data.append({
            'id': result.id.hex(),
            'test_case_id': result.test_case_id.hex(),
            'Test Name': result.test_case.test_name,
            'Time Taken': result.time_taken,
            'Status': result.pass_status,
            'Error Message': result.error_message,
            'group_id': result.test_case.group.id.hex(),
            'group_name': result.test_case.group.name
        })

    for test in missing_test_cases:
        results_data.append({
            'id': None,
            'test_case_id': test.id.hex(),
            'Test Name': test.test_name,
            'Time Taken': None,
            'Status': None,
            'Error Message': '',
            'group_id': test.group.id.hex(),
            'group_name': test.group.name
        })

    column_list = ["Test Name", "Time Taken", "Status", "Error Message"]

    return {
        "test_data": results_data,
        "columnList": column_list,
    }

@router.get("/search_tests/")
async def search_tests(
    query: str,
    limit: int = 10,
    group_id: Optional[UUID] = None,
    db: Session = Depends(get_db)
):
    logger.info("search_tests")
    if not query:
        return []

    query_stmt = db.query(TestCase).filter(TestCase.test_name.ilike(f'%{query}%'))

    if group_id:
        query_stmt = query_stmt.filter(TestCase.group_id == group_id.bytes)

    tests = query_stmt.limit(limit).all()

    results = [{'id': test.id.hex(), 'Test Name': test.test_name} for test in tests]
    return results

@router.get("/search_functional_tests/")
async def search_functional_tests(
    query: str,
    limit: int = 10,
    group_id: Optional[UUID] = None,
    db: Session = Depends(get_db)
):
    logger.info("search_functional_tests")
    if not query:
        return []

    # Query the TestGroup table to get the server, port, and tls values
    test_group = db.query(TestGroup).filter(TestGroup.id == group_id.bytes).first()

    if not test_group:
        raise HTTPException(status_code=404, detail="TestGroup not found")

    try:
        matchingTestNames = sendKdbQuery(
                '.qsuite.showMatchingTests',
                test_group.server,
                test_group.port,
                test_group.tls,
                test_group.scope,
                query
        )
        matchingTestNames = matchingTestNames[:limit]
        results = [x.decode('latin') for x in matchingTestNames]
        return {"success": True, "results": results, "message": ""}
    except Exception as e:
        return {"success": False, "results": [], "message": "Kdb Error while searching for matching q function => " + str(e)}


@router.get("/search_subscription_tests/")
async def search_subscription_tests(
    query: str,
    limit: int = 10,
    group_id: Optional[UUID] = None,
    db: Session = Depends(get_db)
):
    logger.info("search_subscription_tests")
    if not query:
        return []

    # Query the TestGroup table to get the server, port, and tls values
    test_group = db.query(TestGroup).filter(TestGroup.id == group_id.bytes).first()

    if not test_group:
        raise HTTPException(status_code=404, detail="TestGroup not found")

    try:
        matchingTestNames = sendKdbQuery(
                '.qsuite.showMatchingSubTests',
                test_group.server,
                test_group.port,
                test_group.tls,
                test_group.scope,
                query
        )
        matchingTestNames = matchingTestNames[:limit]
        results = [x.decode('latin') for x in matchingTestNames]
        return {"success": True, "results": results, "message": ""}
    except Exception as e:
        return {"success": False, "results": [], "message": "Kdb Error while searching for matching q function => " + str(e)}

