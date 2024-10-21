from unittest.mock import patch
import pytest
from models.models import TestCase, TestGroup, TestResult, TestDependency
from datetime import datetime, timedelta
from uuid import uuid4  # Import uuid4 for generating UUIDs

#############################
###### get_test_info ########
#############################

# Fixture to set up mock data for /get_test_info/
@pytest.fixture(scope="function")
def setup_mock_data_for_test_info(db_session):
    # Generate UUIDs for test group and test cases
    group_id = uuid4()
    test_case_id = uuid4()
    dependent_case_id = uuid4()

    group = TestGroup(id=group_id.bytes, name="Test Group", server="localhost", port=1234, schedule="16:00", tls=True)
    db_session.add(group)
    db_session.commit()

    test_case = TestCase(id=test_case_id.bytes, test_name="Test Case", group_id=group_id.bytes, test_code="print('Test')", creation_date=datetime.utcnow(), free_form=True)
    dependent_case = TestCase(id=dependent_case_id.bytes, test_name="Dependent Test", group_id=group_id.bytes, test_code="print('Dependent Test')")
    
    db_session.add(test_case)
    db_session.add(dependent_case)
    db_session.commit()

    test_result = TestResult(test_case_id=test_case_id.bytes, group_id=group_id.bytes, date_run=datetime.strptime("01-08-2023", '%d-%m-%Y').date(), time_taken=5.0, pass_status=True)
    dependent_result = TestResult(test_case_id=dependent_case_id.bytes, group_id=group_id.bytes, date_run=datetime.strptime("01-08-2023", '%d-%m-%Y').date(), time_taken=4.0, pass_status=False)
    
    db_session.add(test_result)
    db_session.add(dependent_result)
    db_session.commit()

    dependency = TestDependency(test_id=test_case_id.bytes, dependent_test_id=dependent_case_id.bytes)
    db_session.add(dependency)
    db_session.commit()

    return {
        "test_case_id": test_case_id,
        "dependent_case_id": dependent_case_id,
        "group_id": group_id
    }

# Test 1: Query for a test case with results and dependencies
def test_get_test_info_with_results_and_dependencies(client, setup_mock_data_for_test_info):
    test_case_id = setup_mock_data_for_test_info["test_case_id"]
    response = client.get(f"/get_test_info/?date=01-08-2023&test_id={test_case_id.hex}")
    assert response.status_code == 200
    data = response.json()

    # Validate the main test case info
    assert data["test_name"] == "Test Case"
    assert data["pass_status"] == True
    assert data["time_taken"] == 5.0

    # Validate the dependent test info
    assert len(data["dependent_tests"]) == 1
    dependent_test = data["dependent_tests"][0]
    assert dependent_test["Test Name"] == "Dependent Test"
    assert dependent_test["Status"] == False

# Test 2: Query for a test case with no results
def test_get_test_info_no_results(client, setup_mock_data_for_test_info):
    test_case_id = setup_mock_data_for_test_info["test_case_id"]
    response = client.get(f"/get_test_info/?date=02-08-2023&test_id={test_case_id.hex}")
    assert response.status_code == 200
    data = response.json()

    # Validate that there's no result for the test case on the given date
    assert data["test_name"] == "Test Case"
    assert data["pass_status"] is None
    assert data["time_taken"] is None

# Test 3: Query for a test case with no dependencies
def test_get_test_info_no_dependencies(client, setup_mock_data_for_test_info):
    dependent_case_id = setup_mock_data_for_test_info["dependent_case_id"]
    response = client.get(f"/get_test_info/?date=01-08-2023&test_id={dependent_case_id.hex}")
    assert response.status_code == 200
    data = response.json()

    # Validate that there's no dependencies for this test case
    assert data["test_name"] == "Dependent Test"
    assert len(data["dependent_tests"]) == 0


#############################
###### all_functional_tests ##
#############################

@patch('endpoints.view_tests.sendKdbQuery')
def test_all_functional_tests(mock_send_kdb_query, client, db_session):
    # Generate UUID for the test group
    group_id = uuid4()

    # Set up test group in the database
    group = TestGroup(id=group_id.bytes, name="Test Group", server="localhost", port=1234, schedule=None, tls=True)
    db_session.add(group)
    db_session.commit()

    # Mock the sendKdbQuery function to return some test names
    mock_send_kdb_query.return_value = [b"Test Function 1", b"Test Function 2"]

    # Simulate a GET request to the /all_functional_tests/ endpoint
    response = client.get(f"/all_functional_tests/?group_id={group_id.hex}&limit=2")
    assert response.status_code == 200
    data = response.json()

    # Validate the response
    assert data["success"] == True
    assert data["results"] == ["Test Function 1", "Test Function 2"]

@patch('endpoints.view_tests.sendKdbQuery')
def test_all_functional_tests_error_handling(mock_send_kdb_query, client, db_session):
    # Generate UUID for the test group
    group_id = uuid4()

    # Set up test group in the database
    group = TestGroup(id=group_id.bytes, name="Test Group", server="localhost", port=1234, schedule=None, tls=True)
    db_session.add(group)
    db_session.commit()

    # Mock the sendKdbQuery function to raise an exception
    mock_send_kdb_query.side_effect = Exception("Kdb Error")

    # Simulate a GET request to the /all_functional_tests/ endpoint
    response = client.get(f"/all_functional_tests/?group_id={group_id.hex}&limit=2")
    assert response.status_code == 200
    data = response.json()

    # Validate the error response
    assert data["success"] == False
    assert "Kdb Error" in data["message"]

#############################
###### view_test_code #######
#############################

@patch('endpoints.view_tests.sendKdbQuery')
def test_view_test_code(mock_send_kdb_query, client, db_session):
    # Generate UUID for the test group
    group_id = uuid4()

    # Set up test group in the database
    group = TestGroup(id=group_id.bytes, name="Test Group", server="localhost", port=1234, schedule=None, tls=True)
    db_session.add(group)
    db_session.commit()

    # Mock the sendKdbQuery function to return test code
    mock_send_kdb_query.return_value = b"print('Test Code')"

    # Simulate a GET request to the /view_test_code/ endpoint
    response = client.get(f"/view_test_code/?group_id={group_id.hex}&test_name=TestFunction")
    assert response.status_code == 200
    data = response.json()

    # Validate the response
    assert data["success"] == True
    assert data["results"] == "print('Test Code')"

@patch('endpoints.view_tests.sendKdbQuery')
def test_view_test_code_error_handling(mock_send_kdb_query, client, db_session):
    # Generate UUID for the test group
    group_id = uuid4()

    # Set up test group in the database
    group = TestGroup(id=group_id.bytes, name="Test Group", server="localhost", port=1234, schedule=None, tls=True)
    db_session.add(group)
    db_session.commit()

    # Mock the sendKdbQuery function to raise an exception
    mock_send_kdb_query.side_effect = Exception("Kdb Error")

    # Simulate a GET request to the /view_test_code/ endpoint
    response = client.get(f"/view_test_code/?group_id={group_id.hex}&test_name=TestFunction")
    assert response.status_code == 200
    data = response.json()

    # Validate the error response
    assert data["success"] == False
    assert "Kdb Error" in data["message"]

