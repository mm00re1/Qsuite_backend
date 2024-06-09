from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta
import time
from flask_cors import CORS
from KdbSubs import *
from math import ceil
from sqlalchemy import asc, desc

app = Flask(__name__)
CORS(app)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///test_platform.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

kdb_host = "localhost"
kdb_port = 5001
PAGE_SIZE = 50

class TestCase(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    group_id = db.Column(db.Integer, db.ForeignKey('test_group.id'), nullable=False)
    test_name = db.Column(db.String(50), nullable=False)
    test_code = db.Column(db.Text, nullable=False)
    creation_date = db.Column(db.DateTime, default=datetime.utcnow)
    group = db.relationship('TestGroup', backref=db.backref('test_cases', lazy=True))

class TestResult(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    test_case_id = db.Column(db.Integer, db.ForeignKey('test_case.id'), nullable=False)
    group_id = db.Column(db.Integer, db.ForeignKey('test_group.id'), nullable=False)  # Added group_id
    test_case = db.relationship('TestCase', backref=db.backref('results', lazy=True))
    date_run = db.Column(db.Date, nullable=False, default=datetime.utcnow, index=True)
    time_taken = db.Column(db.Float, nullable=False)
    pass_status = db.Column(db.Boolean, nullable=False)
    error_message = db.Column(db.Text, nullable=True)

class TestGroup(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False, unique=True)
    server = db.Column(db.String(100), nullable=False)
    port = db.Column(db.Integer, nullable=False)
    schedule = db.Column(db.String(100), nullable=True)

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
        creation_date=datetime.utcnow()
    )
    db.session.add(new_test_case)
    db.session.commit()
    print("time taken to add test case: ", time.time() - start_time)
    return jsonify({"message": "Test case added successfully", "id": new_test_case.id}), 201


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

    # Validate group_id
    if not group_id:
        return jsonify({"message": "Group ID is required"}), 400
    try:
        group_id = int(group_id)
    except ValueError:
        return jsonify({"message": "Invalid Group ID format, should be an integer"}), 400

    # Calculate the date 30 days ago
    end_date = datetime.utcnow().date()
    start_date = end_date - timedelta(days=30)

    # Query to get counts of passed and failed tests per day for the specific group
    results_summary = db.session.query(
        TestResult.date_run,
        db.func.sum(db.case((TestResult.pass_status == True, 1), else_=0)).label('passed'),
        db.func.sum(db.case((TestResult.pass_status == False, 1), else_=0)).label('failed')
    ).filter(
        TestResult.group_id == group_id,
        TestResult.date_run >= start_date,
        TestResult.date_run <= end_date
    ).group_by(
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

    query = db.session.query(TestResult).join(TestCase).join(TestGroup).filter(
        TestResult.date_run == specific_date
    )

    if group_id:
        query = query.filter(TestCase.group_id == group_id)

    # Apply sorting based on sortOption
    if sort_option == 'Failed':
        print("Failed")
        query = query.order_by(desc(TestResult.pass_status == False))
    elif sort_option == 'Passed':
        print("Passed")
        query = query.order_by(desc(TestResult.pass_status == True))
    elif sort_option == 'Time Taken':
        query = query.order_by(desc(TestResult.time_taken))

    total_results = query.count()  # Get the total number of results for pagination

    query = query.offset((page_number - 1) * PAGE_SIZE).limit(PAGE_SIZE)
    results = query.all()
    print("timeTaken for db query: ", time.time() - stTime)
    stTime = time.time()

    results_data = []
    for result in results:
        results_data.append({
            'id': result.id,
            'test_case_id': result.test_case_id,
            'Test Name': result.test_case.test_name,
            'Time Taken': result.time_taken,
            'Status': result.pass_status,
            'error_message': result.error_message,
            'group_id': result.test_case.group.id,  # Return group ID
            'group_name': result.test_case.group.name  # Return group name
        })

    column_list = ["Test Name", "Time Taken", "Status"]
    total_pages = ceil(total_results / PAGE_SIZE)
    print("timeTaken to format result: ", time.time() - stTime)    
    return jsonify({
        "test_run_data": results_data,
        "columnList": column_list,
        "total_pages": total_pages,
        "current_page": page_number
    }), 200

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

@app.route('/executeQcode/', methods=['POST'])
def execute_q_code():
    try:
        data = request.json
        kdbQuery = wrapQcode(data['code'])
        result = sendKdbQuery(kdbQuery, kdb_host, kdb_port, [])
        return jsonify(result), 200  # Return as JSON with HTTP 200 OK
    
    except Exception as e:
        return jsonify({"success":False, "data": "", "message": "Python Error => " + str(e)}), 500
        

if __name__ == '__main__':
    with app.app_context():
        db.create_all()  # Create tables and index
        initialize_cache()  # Initialize cache on startup
        app.run(debug=True)
