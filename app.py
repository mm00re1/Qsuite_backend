from flask import Flask, request, jsonify
from datetime import datetime, timedelta
import time
from flask_cors import CORS
from KdbSubs import *
from math import floor
from sqlalchemy import asc, desc
from models import db, TestCase, TestResult, TestGroup, TestDependency  # Importing models and db from models.py
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate

app = Flask(__name__)
CORS(app)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///test_platform.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)  # Initialize db with the app
migrate = Migrate(app, db)

kdb_host = "localhost"
kdb_port = 5001
PAGE_SIZE = 50


cache = {
    'unique_dates': [],
    'start_date': None,
    'latest_date': None,
    'missing_dates': []
}

def initialize_cache():
    start_time = time.time()
    
    # Query to get unique dates
    unique_dates_query = db.session.query(TestResult.date_run.distinct().label('date_run')).order_by(TestResult.date_run)
    unique_dates = [date[0] for date in unique_dates_query]

    cache['unique_dates'] = unique_dates

    if unique_dates:
        cache['start_date'] = unique_dates[0]
        cache['latest_date'] = unique_dates[-1]
        
        # Generate a set of all dates in the range
        all_dates = set(cache['start_date'] + timedelta(days=x) for x in range((cache['latest_date'] - cache['start_date']).days + 1))

        # Find the missing dates
        missing_dates = all_dates - set(unique_dates)
        cache['missing_dates'] = sorted(missing_dates)
    
    print("Cache initialized in:", time.time() - start_time, "seconds")


@app.route('/get_unique_dates/', methods=['GET'])
def get_unique_dates():
    if not cache['unique_dates']:
        return jsonify({"start_date": None, "latest_date": None, "missing_dates": []}), 200

    start_date = cache['start_date']
    latest_date = cache['latest_date']
    missing_dates_str = [date.strftime('%Y-%m-%d') for date in cache['missing_dates']]

    print(start_date.strftime('%Y-%m-%d'))
    print(latest_date.strftime('%Y-%m-%d'))
    return jsonify({
        "start_date": start_date.strftime('%Y-%m-%d'),
        "latest_date": latest_date.strftime('%Y-%m-%d'),
        "missing_dates": missing_dates_str
    }), 200


@app.route('/add_test_case/', methods=['POST'])
def add_test_case():
    start_time = time.time()
    data = request.json
    group_id = data.get('group_id')
    dependencies = data.get('dependencies', [])  # Get dependencies from the request, default to an empty list
    print("adding dependencies: ",dependencies)

    # Check if the group_id is provided
    if not group_id:
        return jsonify({"message": "Group ID is required"}), 400

    # Find the test group by ID
    test_group = TestGroup.query.get(group_id)
    if not test_group:
        return jsonify({"message": "Test group not found"}), 404

    new_test_case = TestCase(
        group_id=test_group.id,
        test_name=data['test_name'],
        test_code=data['test_code'],
        creation_date=datetime.utcnow(),
        free_form=data['free_form']
    )
    db.session.add(new_test_case)
    db.session.commit()

    # Add dependencies if any
    for dep_id in dependencies:
        dependency = TestDependency(test_id=new_test_case.id, dependent_test_id=dep_id)
        db.session.add(dependency)
    db.session.commit()

    print("time taken to add test case: ", time.time() - start_time)
    return jsonify({"message": "Test case added successfully", "id": new_test_case.id}), 201

@app.route('/edit_test_case/', methods=['PUT'])
def edit_test_case():
    start_time = time.time()
    data = request.json
    test_case_id = data.get('id')
    dependencies = data.get('dependencies', [])  # Get dependencies from the request, default to an empty list
    print("editing dependencies: ", dependencies)

    # Check if the test_case_id is provided
    if not test_case_id:
        return jsonify({"message": "Test Case ID is required"}), 400

    # Find the test case by ID
    test_case = TestCase.query.get(test_case_id)
    if not test_case:
        return jsonify({"message": "Test case not found"}), 404

    # Update test case fields
    if 'test_name' in data:
        test_case.test_name = data['test_name']
    if 'test_code' in data:
        test_case.test_code = data['test_code']
    test_case.last_modified_date = datetime.utcnow()
    db.session.commit()

    # Update dependencies
    # First, remove existing dependencies
    TestDependency.query.filter_by(test_id=test_case.id).delete()
    db.session.commit()

    # Add new dependencies if any
    for dep_id in dependencies:
        dependency = TestDependency(test_id=test_case.id, dependent_test_id=dep_id)
        db.session.add(dependency)
    db.session.commit()

    print("time taken to edit test case: ", time.time() - start_time)
    return jsonify({"message": "Test case edited successfully"}), 200


@app.route('/add_test_result/', methods=['POST'])
def add_test_result():
    start_time = time.time()
    data = request.json
    new_test_result = TestResult(
        test_case_id=data['test_case_id'],
        date_run=data.get('date_run', datetime.utcnow()),  # Allow specifying the run date
        time_taken=data['time_taken'],
        pass_status=data['pass_status'],
        error_message=data['error_message']
    )
    db.session.add(new_test_result)
    db.session.commit()
    print("time taken to add test result: ", time.time() - start_time)
    return jsonify({"message": "Test result added successfully", "id": new_test_result.id}), 201

@app.route('/add_test_group/', methods=['POST'])
def add_test_group():
    data = request.json
    new_test_group = TestGroup(
        name=data['name'],
        server=data['server'],
        port=data['port'],
        schedule=data.get('schedule')
    )
    db.session.add(new_test_group)
    db.session.commit()
    return jsonify({"message": "Test group added successfully", "id": new_test_group.id}), 201

@app.route('/edit_test_group/<int:id>/', methods=['PUT'])
def edit_test_group(id):
    data = request.json
    test_group = TestGroup.query.get(id)
    if not test_group:
        return jsonify({"message": "Test group not found"}), 404

    test_group.name = data.get('name', test_group.name)
    test_group.server = data.get('server', test_group.server)
    test_group.port = data.get('port', test_group.port)
    test_group.schedule = data.get('schedule', test_group.schedule)

    db.session.commit()
    return jsonify({"message": "Test group updated successfully"}), 200

@app.route('/test_groups/', methods=['GET'])
def get_test_groups():
    test_groups = TestGroup.query.all()
    groups_data = []
    for group in test_groups:
        groups_data.append({
            "id": group.id,
            "name": group.name,
            "server": group.server,
            "port": group.port,
            "schedule": group.schedule
        })
    return jsonify(groups_data), 200

@app.route('/get_test_results_30_days/', methods=['GET'])
def get_test_results_30_days():
    stTime = time.time()
    group_id = request.args.get('group_id')

    # Calculate the date 30 days ago
    end_date = datetime.utcnow().date()
    start_date = end_date - timedelta(days=30)

    # Base query
    query = db.session.query(
        TestResult.date_run,
        db.func.sum(db.case((TestResult.pass_status == True, 1), else_=0)).label('passed'),
        db.func.sum(db.case((TestResult.pass_status == False, 1), else_=0)).label('failed')
    ).filter(
        TestResult.date_run >= start_date,
        TestResult.date_run <= end_date
    )

    # Add group_id filter if provided
    if group_id:
        try:
            group_id = int(group_id)
            query = query.filter(TestResult.group_id == group_id)
        except ValueError:
            return jsonify({"message": "Invalid Group ID format, should be an integer"}), 400

    # Group by date
    results_summary = query.group_by(
        TestResult.date_run
    ).all()

    # Prepare the response data
    results_data = []
    for result in results_summary:
        results_data.append({
            "date": result.date_run.strftime('%Y-%m-%d'),
            "passed": result.passed,
            "failed": result.failed
        })

    print("time taken: ", time.time() - stTime)
    return jsonify(results_data), 200

@app.route('/get_test_group_stats/', methods=['GET'])
def get_test_group_stats():
    stTime = time.time()
    date_str = request.args.get('date')
    group_id = request.args.get('group_id')
    try:
        specific_date = datetime.strptime(date_str, '%d-%m-%Y').date()
    except ValueError:
        return jsonify({"message": "Invalid date format, should be DD-MM-YYYY"}), 400
    
        # Additional query to get the total number of passed and failed tests
    passed_count = db.session.query(db.func.count(TestResult.id)).join(TestCase).filter(
        TestResult.date_run == specific_date,
        TestResult.pass_status == True
    )
    failed_count = db.session.query(db.func.count(TestResult.id)).join(TestCase).filter(
        TestResult.date_run == specific_date,
        TestResult.pass_status == False
    )

    if group_id:
        passed_count = passed_count.filter(TestCase.group_id == group_id)
        failed_count = failed_count.filter(TestCase.group_id == group_id)

    passed_count = passed_count.scalar()
    failed_count = failed_count.scalar()

    print("timeTaken to get total passed/faield amount: ", time.time() - stTime)
    
    return jsonify({
        "total_passed": passed_count,
        "total_failed": failed_count
    }), 200


@app.route('/get_test_results_by_day/', methods=['GET'])
def get_test_results_by_day():
    stTime = time.time()
    date_str = request.args.get('date')
    group_id = request.args.get('group_id')
    page_number = request.args.get('page_number', 1, type=int)
    sort_option = request.args.get('sortOption', '')  # Get sort option, default is empty string

    # Convert date from DD-MM-YYYY to YYYY-MM-DD for SQL compatibility
    try:
        specific_date = datetime.strptime(date_str, '%d-%m-%Y').date()
    except ValueError:
        return jsonify({"message": "Invalid date format, should be DD-MM-YYYY"}), 400

    # Query for test results
    query = db.session.query(TestResult).join(TestCase).join(TestGroup).filter(
        TestResult.date_run == specific_date
    )

    if group_id:
        query = query.filter(TestCase.group_id == group_id)

    # Apply sorting based on sortOption
    if sort_option == 'Failed':
        query = query.order_by(desc(TestResult.pass_status == False))
    elif sort_option == 'Passed':
        query = query.order_by(desc(TestResult.pass_status == True))
    elif sort_option == 'Time Taken':
        query = query.order_by(desc(TestResult.time_taken))

    total_test_results = query.count()  # Get the total number of test results
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
            'group_id': result.test_case.group.id,  # Return group ID
            'group_name': result.test_case.group.name  # Return group name
        })

    # Query to get un-run test cases count
    run_test_case_ids = db.session.query(TestResult.test_case_id).join(TestCase).filter(
        TestResult.date_run == specific_date
    ).distinct()

    if group_id:
        run_test_case_ids = run_test_case_ids.filter(TestCase.group_id == group_id)

    run_test_case_ids = run_test_case_ids.subquery()

    unrun_tests_count = db.session.query(TestCase).filter(
        TestCase.group_id == group_id,
        ~TestCase.id.in_(run_test_case_ids)
    ).count()

    total_pages_with_unrun = 1 + floor((total_test_results + unrun_tests_count) / PAGE_SIZE)

    # Determine the number of un-run tests to fetch on the current page
    if page_number >= total_pages_test_results:
        print("total_pages_test_results: ", total_pages_test_results)
        if page_number > total_pages_test_results:
            rows_in_first_page = PAGE_SIZE - (total_test_results % PAGE_SIZE)
            unrun_limit = PAGE_SIZE
        else:
            rows_in_first_page = 0
            unrun_limit = PAGE_SIZE - (total_test_results % PAGE_SIZE)

        print("total_test_results: ", total_test_results)
        print("page_number: ", page_number)
        print("rows_in_first_page: ", rows_in_first_page)
        print("unrun_limit: ", unrun_limit)

        unrun_offset = rows_in_first_page + max(0, (page_number - total_pages_test_results - 1) * PAGE_SIZE)
        print("unrun_offset: ", unrun_offset)

        if unrun_limit > 0:
            unrun_tests_query = db.session.query(TestCase).filter(
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
                    'group_id': test.group.id,  # Return group ID
                    'group_name': test.group.name  # Return group name
                })

    column_list = ["Test Name", "Time Taken", "Status", "Error Message"]
    print("timeTaken to format result: ", time.time() - stTime)

    return jsonify({
        "test_data": results_data,
        "columnList": column_list,
        "total_pages": total_pages_with_unrun,
        "current_page": page_number,
    }), 200

@app.route('/get_tests_by_group/', methods=['GET'])
def get_tests_by_group():
    stTime = time.time()
    group_id = request.args.get('group_id')
    date_str = request.args.get('date')
    page_number = request.args.get('page_number', 1, type=int)

    if not group_id:
        return jsonify({"message": "Group ID is required"}), 400

    if not date_str:
        return jsonify({"message": "Date is required"}), 400

    # Convert date from DD-MM-YYYY to YYYY-MM-DD for SQL compatibility
    try:
        specific_date = datetime.strptime(date_str, '%d-%m-%Y').date()
    except ValueError:
        return jsonify({"message": "Invalid date format, should be DD-MM-YYYY"}), 400

    # Query to get test cases that have been run on the specified date
    run_test_case_ids = db.session.query(TestResult.test_case_id).join(TestCase).filter(
        TestResult.date_run == specific_date,
        TestCase.group_id == group_id
    ).distinct()

    # Query to get un-run test cases
    query = db.session.query(TestCase).filter(
        TestCase.group_id == group_id,
        ~TestCase.id.in_(run_test_case_ids)
    )

    total_results = query.count()  # Get the total number of results for pagination

    query = query.offset((page_number - 1) * PAGE_SIZE).limit(PAGE_SIZE)
    results = query.all()
    print("timeTaken for db query: ", time.time() - stTime)
    stTime = time.time()

    results_data = []
    for test in results:
        results_data.append({
            'test_case_id': test.id,
            'Test Name': test.test_name
        })

    total_pages = 1 + floor(total_results / PAGE_SIZE)
    column_list = ["Test Name"]
    print("timeTaken to format result: ", time.time() - stTime)

    return jsonify({
        "test_data": results_data,
        "columnList": column_list,
        "total_pages": total_pages,
        "current_page": page_number,
    }), 200

@app.route('/get_tests_by_ids/', methods=['GET'])
def get_tests_by_ids():
    stTime = time.time()
    test_ids_str = request.args.get('test_ids')
    date_str = request.args.get('date')
    group_id = request.args.get('group_id')
    
    try:
        specific_date = datetime.strptime(date_str, '%d-%m-%Y').date()
    except ValueError:
        return jsonify({"message": "Invalid date format, should be DD-MM-YYYY"}), 400
    
    if not test_ids_str:
        return jsonify({"message": "Test IDs are required"}), 400

    try:
        test_ids = [int(id_str) for id_str in test_ids_str.split(',')]
    except ValueError:
        return jsonify({"message": "Invalid test IDs format, should be a comma-separated list of integers"}), 400

    # Query to get test results for the given test IDs
    query = db.session.query(TestResult).join(TestCase).join(TestGroup).filter(
        TestResult.date_run == specific_date
    )

    if group_id:
        query = query.filter(TestCase.group_id == group_id)

    query = query.filter(TestCase.id.in_(test_ids))
    test_results = query.all()

    # Find which test IDs are not in the test results
    found_test_ids = {result.test_case_id for result in test_results}
    missing_test_ids = set(test_ids) - found_test_ids

    # Query to get test cases for the missing test IDs
    missing_test_cases = db.session.query(TestCase).filter(TestCase.id.in_(missing_test_ids)).all()

    results_data = []
    for result in test_results:
        results_data.append({
            'id': result.id,
            'test_case_id': result.test_case_id,
            'Test Name': result.test_case.test_name,
            'Time Taken': result.time_taken,
            'Status': result.pass_status,
            'Error Message': result.error_message,
            'group_id': result.test_case.group.id,  # Return group ID
            'group_name': result.test_case.group.name  # Return group name
        })

    for test in missing_test_cases:
        results_data.append({
            'id': None,
            'test_case_id': test.id,
            'Test Name': test.test_name,
            'Time Taken': None,
            'Status': None,
            'Error Message': '',
            'group_id': test.group.id,  # Return group ID
            'group_name': test.group.name  # Return group name
        })

    column_list = ["Test Name", "Time Taken", "Status", "Error Message"]
    print("timeTaken for db query and formatting result: ", time.time() - stTime)
    
    return jsonify({
        "test_data": results_data,
        "columnList": column_list,
    }), 200

@app.route('/get_test_info/', methods=['GET'])
def get_test_info():
    stTime = time.time()
    date_str = request.args.get('date')
    test_id = request.args.get('test_id')
    print("date_str: ", date_str)
    print("test_id: ", test_id)

    # Convert date from DD-MM-YYYY to YYYY-MM-DD for SQL compatibility
    try:
        specific_date = datetime.strptime(date_str, '%d-%m-%Y').date()
    except ValueError:
        return jsonify({"message": "Invalid date format, should be DD-MM-YYYY"}), 400

    # Query to get the test case and related group information
    test_case = db.session.query(TestCase).join(TestGroup).filter(
        TestCase.id == test_id
    ).first()

    if not test_case:
        return jsonify({"message": "Test case not found"}), 404

    # Query to get the test results for the specific date
    test_result = db.session.query(TestResult).filter(
        TestResult.test_case_id == test_id,
        TestResult.date_run == specific_date
    ).first()

    # Query to get the dependencies for the test case
    dependencies = db.session.query(TestDependency).filter(
        TestDependency.test_id == test_id
    ).all()

    dependent_tests = []
    for dep in dependencies:
        print(dep)
        dependent_test_case = db.session.query(TestCase).filter(TestCase.id == dep.dependent_test_id).first()
        if dependent_test_case:
            # Query to get the pass status of the dependent test for the specific date
            dependent_test_result = db.session.query(TestResult).filter(
                TestResult.test_case_id == dependent_test_case.id,
                TestResult.date_run == specific_date
            ).first()
            dependent_tests.append({
                'test_case_id': dependent_test_case.id,
                'Test Name': dependent_test_case.test_name,
                'Status': dependent_test_result.pass_status if dependent_test_result else None,  # Add pass status
                'Error Message': dependent_test_result.error_message if dependent_test_result else None
            })

    # Get the last 30 days of results
    last_30_days = datetime.utcnow() - timedelta(days=30)
    last_30_days_results = db.session.query(TestResult).filter(
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
        'dependent_tests': dependent_tests,  # Add the list of dependent tests with pass status
        'dependent_tests_columns': ["Test Name", "Status", "Error Message"],
        'last_30_days_dates': dates,
        'last_30_days_statuses': statuses,
        'last_30_days_timeTaken': time_taken  # Add time taken for the last 30 days
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

    print("total time taken: ", time.time() - stTime)
    return jsonify(test_info), 200

@app.route('/get_test_result_summary/', methods=['GET'])
def get_test_result_summary():
    stTime = time.time()
    print("starting query")
    date_str = request.args.get('date')

    # Convert date from DD-MM-YYYY to YYYY-MM-DD for SQL compatibility
    try:
        specific_date = datetime.strptime(date_str, '%d-%m-%Y').date()
    except ValueError:
        return jsonify({"message": "Invalid date format, should be DD-MM-YYYY"}), 400

    # Step 1: Query to get counts of passed and failed tests per group for a specific date
    start_query_time = time.time()
    results_summary = db.session.query(
        TestResult.group_id,
        db.func.sum(db.case((TestResult.pass_status == True, 1), else_=0)).label('passed'),
        db.func.sum(db.case((TestResult.pass_status == False, 1), else_=0)).label('failed')
    ).filter(
        TestResult.date_run == specific_date
    ).group_by(
        TestResult.group_id
    ).all()
    print("timeTaken for results summary query: ", time.time() - start_query_time)

    # Step 2: Query to get test group information
    start_query_time = time.time()
    test_groups = TestGroup.query.all()
    print("timeTaken for test groups query: ", time.time() - start_query_time)

    # Step 3: Merge the results
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

    return jsonify({"groups_data": groups_data, "columnList": column_list}), 200

@app.route('/search_tests', methods=['GET'])
def search_tests():
    query = request.args.get('query', '')
    limit = request.args.get('limit', 10, type=int)
    group_id = request.args.get('group_id')

    if not query:
        return jsonify([]), 200

    # Base query for searching tests
    query_stmt = db.session.query(TestCase).filter(TestCase.test_name.ilike(f'%{query}%'))

    # Apply additional filter if group_id is provided
    if group_id:
        query_stmt = query_stmt.filter(TestCase.group_id == group_id)

    tests = query_stmt.limit(limit).all()

    results = [{'id': test.id, 'Test Name': test.test_name} for test in tests]
    return jsonify(results), 200

@app.route('/search_functional_tests', methods=['GET'])
def search_functional_tests():
    query = request.args.get('query', '')
    limit = request.args.get('limit', 10, type=int)
    group_id = request.args.get('group_id')
    if not query:
        return jsonify([]), 200

    # in future extract the port from the group_id ***********
    matchingTestNames = sendKdbQuery('.qsuite.showMatchingTests', kdb_host, kdb_port, query)
    matchingTestNames = matchingTestNames[:limit]
    results = [x.decode('latin') for x in matchingTestNames]
    return jsonify(results), 200

@app.route('/all_functional_tests', methods=['GET'])
def all_functional_tests():
    limit = request.args.get('limit', 10, type=int)
    group_id = request.args.get('group_id')

    # in future extract the port from the group_id ***********
    TestNames = sendKdbQuery('.qsuite.showAllTests', kdb_host, kdb_port, [])
    TestNames = TestNames[:limit]
    results = [x.decode('latin') for x in TestNames]
    return jsonify(results), 200

@app.route('/view_test_code', methods=['GET'])
def view_test_code():
    # this is for functional tests
    group_id = request.args.get('group_id')
    test_name = request.args.get('test_name')

    # in future extract the port from the group_id ***********
    test_code = sendKdbQuery('.qsuite.parseTestCode', kdb_host, kdb_port, test_name)
    print("test_code")
    print(test_code)
    results = test_code.decode('latin')
    print("test_code after stringify")
    print(test_code)
    return jsonify(results), 200

@app.route('/execute_q_code/', methods=['POST'])
def execute_q_code():
    try:
        data = request.json
        kdbQuery = wrapQcode(data['code'])
        result = sendFreeFormQuery(kdbQuery, kdb_host, kdb_port, [])
        return jsonify(result), 200  # Return as JSON with HTTP 200 OK
    
    except Exception as e:
        return jsonify({"success":False, "data": "", "message": "Python Error => " + str(e)}), 500

@app.route('/execute_q_function/', methods=['GET'])
def execute_q_function():
    # this is for functional tests
    group_id = request.args.get('group_id')
    test_name = request.args.get('test_name')

    # in future extract the port from the group_id ***********
    try:
        result = sendFunctionalQuery(test_name, kdb_host, kdb_port)
        return jsonify(result), 200  # Return as JSON with HTTP 200 OK
    
    except Exception as e:
        return jsonify({"success":False, "data": "", "message": "Python Error => " + str(e)}), 500 

if __name__ == '__main__':
    with app.app_context():
        db.create_all()  # Create tables and index
        initialize_cache()  # Initialize cache on startup
        app.run(debug=True)
