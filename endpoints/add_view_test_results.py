from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, case, desc
from datetime import datetime, timedelta
from pydantic import BaseModel
from typing import List, Optional
import time
from math import floor

from models.models import TestResult, TestCase, TestGroup
from dependencies import get_db
from config import PAGE_SIZE

router = APIRouter()

class TestResultCreate(BaseModel):
    test_case_id: int
    date_run: Optional[datetime] = None
    time_taken: float
    pass_status: bool
    error_message: Optional[str] = None


@router.post("/add_test_result/")
async def add_test_result(test_result: TestResultCreate, db: Session = Depends(get_db)):
    start_time = time.time()
    
    new_test_result = TestResult(
        test_case_id=test_result.test_case_id,
        date_run=test_result.date_run or datetime.utcnow(),
        time_taken=test_result.time_taken,
        pass_status=test_result.pass_status,
        error_message=test_result.error_message
    )
    db.add(new_test_result)
    db.commit()
    print("time taken to add test result: ", time.time() - start_time)
    return {"message": "Test result added successfully", "id": new_test_result.id}, 201


@router.get("/get_test_results_30_days/")
async def get_test_results_30_days(group_id: Optional[int] = None, db: Session = Depends(get_db)):
    stTime = time.time()

    end_date = datetime.utcnow().date()
    start_date = end_date - timedelta(days=30)

    query = db.query(
        TestResult.date_run,
        func.sum(case((TestResult.pass_status == True, 1), else_=0)).label('passed'),
        func.sum(case((TestResult.pass_status == False, 1), else_=0)).label('failed')
    ).filter(
        TestResult.date_run >= start_date,
        TestResult.date_run <= end_date
    )

    if group_id:
        query = query.filter(TestResult.group_id == group_id)

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
    group_id: Optional[int] = None,
    page_number: int = 1,
    sortOption: str = "",
    db: Session = Depends(get_db)
):
    stTime = time.time()

    try:
        specific_date = datetime.strptime(date, '%d-%m-%Y').date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format, should be DD-MM-YYYY")

    query = db.query(TestResult).join(TestCase).join(TestGroup).filter(
        TestResult.date_run == specific_date
    )

    if group_id:
        query = query.filter(TestCase.group_id == group_id)

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
    for result in test_results:
        results_data.append({
            'id': result.id,
            'test_case_id': result.test_case_id,
            'Test Name': result.test_case.test_name,
            'Time Taken': result.time_taken,
            'Status': result.pass_status,
            'Error Message': result.error_message,
            'group_id': result.test_case.group.id,
            'group_name': result.test_case.group.name
        })

    run_test_case_ids = db.query(TestResult.test_case_id).join(TestCase).filter(
        TestResult.date_run == specific_date
    ).distinct()

    if group_id:
        run_test_case_ids = run_test_case_ids.filter(TestCase.group_id == group_id)

    run_test_case_ids = run_test_case_ids.subquery()

    unrun_tests_count = db.query(TestCase).filter(
        TestCase.group_id == group_id,
        ~TestCase.id.in_(run_test_case_ids)
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
                TestCase.group_id == group_id,
                ~TestCase.id.in_(run_test_case_ids)
            ).offset(unrun_offset).limit(unrun_limit)

            unrun_tests = unrun_tests_query.all()
            print("timeTaken for db query (unrun tests): ", time.time() - stTime)
            stTime = time.time()

            for test in unrun_tests:
                results_data.append({
                    'id': None,
                    'test_case_id': test.id,
                    'Test Name': test.test_name,
                    'Time Taken': None,
                    'Status': None,
                    'Error Message': None,
                    'group_id': test.group.id,
                    'group_name': test.group.name
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
            "id": group.id,
            "Name": group.name,
            "Machine": group.server,
            "Port": group.port,
            "Scheduled": group.schedule,
            "Passed": group_summary['passed'],
            "Failed": group_summary['failed']
        })

    column_list = ["Name", "Machine", "Port", "Scheduled", "Passed", "Failed"]
    print("Total time taken: ", time.time() - stTime)

    return {"groups_data": groups_data, "columnList": column_list}
