from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from KdbSubs import *
from datetime import datetime
import time
from flask_cors import CORS
#import pandas as pd

app = Flask(__name__)
CORS(app)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///test_platform.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)
kdb_host = "localhost"
kdb_port = 5001

"""
class TimeoutException(Exception):
    pass

def execute_with_timeout(qFunction, timeout):
    class QueryThread(threading.Thread):
        def __init__(self):
            threading.Thread.__init__(self)
            self.result = None
            self.err = None
        #
        def run(self):
            try:
                # Construct a Kdb query that checks the size before returning
                kdbQuery = "{[] response: " + qFunction + "[]; $[10000000 < -22!response; \"can't return preview of objects this large\"; response]}"
                self.result = sendKdbQuery(kdbQuery, kdb_host, kdb_port, [])
            except Exception as e:
                self.err = e
    #
    query_thread = QueryThread()
    query_thread.start()
    query_thread.join(timeout)
    if query_thread.is_alive():
        query_thread.join()  # Ensure thread is cleaned up correctly
        raise TimeoutException("The query timed out.")
    if query_thread.err:
        raise query_thread.err  # Propagate exceptions from the thread
    return query_thread.result
"""

class TestCase(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    group_name = db.Column(db.String(50), nullable=False)
    test_name = db.Column(db.String(50), nullable=False)
    test_code = db.Column(db.Text, nullable=False)
    expected_output = db.Column(db.Boolean, nullable=False)

class TestResult(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    test_case_id = db.Column(db.Integer, db.ForeignKey('test_case.id'), nullable=False)
    test_case = db.relationship('TestCase', backref=db.backref('results', lazy=True))
    date_run = db.Column(db.Date, nullable=False, default=datetime.utcnow, index=True)  # Index added here
    time_taken = db.Column(db.Float, nullable=False)
    creation_date = db.Column(db.DateTime, default=datetime.utcnow)
    pass_status = db.Column(db.Boolean, nullable=False)
    error_message = db.Column(db.Text, nullable=True)

@app.route('/add_test_case/', methods=['POST'])
def add_test_case():
    start_time = time.time()
    data = request.json
    new_test_case = TestCase(
        group_name=data['group_name'],
        test_name=data['test_name'],
        test_code=data['test_code'],
        expected_output=data['expected_output']
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

@app.route('/results_by_date/<date>/', methods=['GET'])
def get_results_by_date(date):
    start_time = time.time()
    results = TestResult.query.join(TestCase).filter(TestResult.date_run == date).all()
    result_data = [{
        'test_case_id': result.test_case_id,
        'group_name': result.test_case.group_name,
        'test_name': result.test_case.test_name,
        'date_run': result.date_run,
        'time_taken': result.time_taken,
        'pass_status': result.pass_status,
        'error_message': result.error_message
    } for result in results]
    print("time taken to retrieve test data: ", time.time() - start_time)
    return jsonify(result_data)

@app.route('/executeQcode/', methods=['POST'])
def execute_q_code():
    try:
        data = request.json
        qFunction = '{[] ' + ''.join(data['code']) + '}'  # Join the lines of code into a single line inside a function
        print(qFunction)
        #block from parsing result greater than 1MB in size, users can view head of result if necessary ie 10#table
        kdbQuery = "{[] response: " + qFunction + "[]; $[1000000 < -22!response; \"can't return preview of objects this large\"; response]}"
        result = sendKdbQuery(kdbQuery, kdb_host, kdb_port, [])
        return jsonify(result), 200  # Return as JSON with HTTP 200 OK
    
    except Exception as e:
        return jsonify({"success":False, "data": "", "message": "Python Error => " + str(e)}), 500
    

        # Return the execution result to the client
        """
        if isinstance(result, dict) or isinstance(result, list):
            return jsonify(result)
        elif isinstance(result, bool):
            return jsonify(success=result)
        elif isinstance(result, (int, float, str)):
            return jsonify(value=result)
        else:
            return jsonify(error="Unsupported data type"), 400  
    except TimeoutException:
        return "Query timed out", 408"""
    

if __name__ == '__main__':
    with app.app_context():
        db.create_all()  # Create tables and index
    app.run(debug=True)
