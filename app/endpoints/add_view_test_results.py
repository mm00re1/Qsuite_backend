from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, case, desc
from sqlalchemy import select
from datetime import datetime, timedelta
from pydantic import BaseModel
from typing import List, Optional
import time
from math import floor
import logging
from uuid import UUID

from models.models import TestResult, TestCase, TestGroup
from dependencies import get_db
from config.config import PAGE_SIZE

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/get_test_results_30_days/")
async def get_test_results_30_days(group_id: Optional[UUID] = None, db: Session = Depends(get_db)):
    logger.info("get_test_results_30_days")
    stTime = time.time()

    end_date = datetime.utcnow().date()
    start_date = end_date - timedelta(days=29)

    query = db.query(
        TestResult.date_run,
        func.sum(case((TestResult.pass_status == True, 1), else_=0)).label('passed'),
        func.sum(case((TestResult.pass_status == False, 1), else_=0)).label('failed')
    ).filter(
        TestResult.date_run >= start_date,
        TestResult.date_run <= end_date
    )

    if group_id:
        query = query.filter(TestResult.group_id == group_id.bytes)

    results_summary = query.group_by(TestResult.date_run).all()

    results_data = []
    for result in results_summary:
        results_data.append({
            "date": result.date_run.strftime('%Y-%m-%d'),
            "passed": result.passed,
            "failed": result.failed
        })

    print("time taken: ", time.time() - stTime)
    return results_data


@router.get("/get_test_results_by_day/")
async def get_test_results_by_day(
    date: str,
    group_id: UUID,
    page_number: int = 1,
    sortOption: str = "",
    db: Session = Depends(get_db)
):
    logger.info("get_test_results_by_day")
    stTime = time.time()

    try:
        specific_date = datetime.strptime(date, '%d-%m-%Y').date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format, should be DD-MM-YYYY")

    query = db.query(TestResult, TestCase.creation_date).join(TestCase).join(TestGroup).filter(
        TestResult.date_run == specific_date
    )
    
    query = query.filter(TestCase.group_id == group_id.bytes)

    print("sort option: ", sortOption)
    print("page_number: ", page_number)
    if sortOption == 'Failed':
        query = query.order_by(desc(TestResult.pass_status == False))
    elif sortOption == 'Passed':
        query = query.order_by(desc(TestResult.pass_status == True))
    elif sortOption == 'Time Taken':
        query = query.order_by(desc(TestResult.time_taken))

    total_test_results = query.count()
    print("count run tests: ", total_test_results)
    total_pages_test_results = 1 + floor(total_test_results / PAGE_SIZE)

    query = query.offset((page_number - 1) * PAGE_SIZE).limit(PAGE_SIZE)
    test_results = query.all()
    print("timeTaken for db query (test results): ", time.time() - stTime)
    stTime = time.time()

    results_data = []
    for result, creation_date in test_results:
        results_data.append({
            'id': result.id.hex(),
            'test_case_id': result.test_case_id.hex(),
            'Test Name': result.test_case.test_name,
            'Time Taken': result.time_taken,
            'Status': result.pass_status,
            'Error Message': result.error_message,
            'group_id': result.test_case.group.id.hex(),
            'group_name': result.test_case.group.name,
            'time_run': result.time_run,
            'Creation Date': creation_date
        })

    run_test_case_ids = db.query(TestResult.test_case_id).join(TestCase).filter(
        TestResult.date_run == specific_date
    ).distinct()

    run_test_case_ids = run_test_case_ids.filter(TestCase.group_id == group_id.bytes)

    run_test_case_ids = run_test_case_ids.subquery()
    select_run_test_case_ids = select(run_test_case_ids.c.test_case_id)

    unrun_tests_count = db.query(TestCase).filter(
        TestCase.group_id == group_id.bytes,
        ~TestCase.id.in_(select_run_test_case_ids)
    ).count()

    print("count un-run tests: ", unrun_tests_count)

    total_pages_with_unrun = 1 + floor((total_test_results + unrun_tests_count) / PAGE_SIZE)

    if page_number >= total_pages_test_results:
        if page_number > total_pages_test_results:
            rows_in_first_page = PAGE_SIZE - (total_test_results % PAGE_SIZE)
            unrun_limit = PAGE_SIZE
        else:
            rows_in_first_page = 0
            unrun_limit = PAGE_SIZE - (total_test_results % PAGE_SIZE)

        unrun_offset = rows_in_first_page + max(0, (page_number - total_pages_test_results - 1) * PAGE_SIZE)

        if unrun_limit > 0:
            unrun_tests_query = db.query(TestCase).filter(
                TestCase.group_id == group_id.bytes,
                ~TestCase.id.in_(select_run_test_case_ids)
            ).offset(unrun_offset).limit(unrun_limit)

            unrun_tests = unrun_tests_query.all()
            print("timeTaken for db query (unrun tests): ", time.time() - stTime)
            stTime = time.time()

            for test in unrun_tests:
                results_data.append({
                    'id': None,
                    'test_case_id': test.id.hex(),
                    'Test Name': test.test_name,
                    'Time Taken': None,
                    'Status': None,
                    'Error Message': None,
                    'group_id': test.group.id.hex(),
                    'group_name': test.group.name,
                    'time_run': None,
                    'Creation Date': test.creation_date
                })

    column_list = ["Test Name", "Time Taken", "Status", "Error Message"]
    print("timeTaken to format result: ", time.time() - stTime)

    return {
        "test_data": results_data,
        "columnList": column_list,
        "total_pages": total_pages_with_unrun,
        "current_page": page_number,
    }


@router.get("/get_test_result_summary/")
async def get_test_result_summary(date: str, db: Session = Depends(get_db)):
    logger.info("get_test_result_summary")
    stTime = time.time()
    print("starting query")

    try:
        specific_date = datetime.strptime(date, '%d-%m-%Y').date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format, should be DD-MM-YYYY")

    start_query_time = time.time()
    results_summary = db.query(
        TestResult.group_id,
        func.sum(case((TestResult.pass_status == True, 1), else_=0)).label('passed'),
        func.sum(case((TestResult.pass_status == False, 1), else_=0)).label('failed')
    ).filter(
        TestResult.date_run == specific_date
    ).group_by(
        TestResult.group_id
    ).all()
    print("timeTaken for results summary query: ", time.time() - start_query_time)

    start_query_time = time.time()
    test_groups = db.query(TestGroup).all()
    print("timeTaken for test groups query: ", time.time() - start_query_time)

    summary_dict = {result.group_id: {'passed': result.passed, 'failed': result.failed} for result in results_summary}

    groups_data = []
    for group in test_groups:
        group_summary = summary_dict.get(group.id, {'passed': 0, 'failed': 0})
        groups_data.append({
            "id": group.id.hex(),
            "Name": group.name,
            "Machine": group.server,
            "Port": group.port,
            "Scheduled": group.schedule,
            "Passed": group_summary['passed'],
            "Failed": group_summary['failed'],
            "TLS": group.tls,
            "Scope": group.scope
        })

    column_list = ["Name", "Machine", "Port", "Scheduled", "Passed", "Failed", "TLS"]
    print("Total time taken: ", time.time() - stTime)

    return {"groups_data": groups_data, "columnList": column_list}

