from unittest.mock import patch
import pytest
from datetime import datetime
from uuid import uuid4  # Import uuid4 for generating UUIDs
from models.models import TestCase, TestGroup, TestResult

#############################
##### get_tests_by_ids ######
#############################

# Fixture to set up mock data
@pytest.fixture(scope="function")
def setup_mock_data(db_session):
    # Generate UUIDs for test group and test cases
    group_id = uuid4()
    test_case_ran_id = uuid4()
    test_case_unran_id = uuid4()
    test_result_id = uuid4()

    # Set up mock data once for all tests
    group = TestGroup(id=group_id.bytes, name="Test Group 1", server="localhost", port=1234, tls=True)

    test_case_ran = TestCase(id=test_case_ran_id.bytes, test_name="Test Case Ran", group_id=group_id.bytes, test_code="print('Hello World')")
    test_result = TestResult(id=test_result_id.bytes, test_case_id=test_case_ran_id.bytes, group_id=group_id.bytes,
                             date_run=datetime(2023, 8, 1).date(), time_taken=5.0, pass_status=True)

    test_case_unran = TestCase(id=test_case_unran_id.bytes, test_name="Test Case Unran", group_id=group_id.bytes, test_code="print('Test')")

    db_session.add(group)
    db_session.add(test_case_ran)
    db_session.add(test_result)
    db_session.add(test_case_unran)
    db_session.commit()

    return {
        "group_id": group_id,
        "test_result_id": test_result_id,
        "test_case_ran_id": test_case_ran_id,
        "test_case_unran_id": test_case_unran_id
    }

# Test 1: Query for the test case that has been run
def test_get_tests_by_ids_ran_test(client, setup_mock_data):
    test_case_ran_id = setup_mock_data["test_case_ran_id"]

    # Simulate API request to get the test case that has been run
    response = client.get(f"/get_tests_by_ids/?test_ids={test_case_ran_id.hex}&date=01-08-2023")
    assert response.status_code == 200

    # Print the actual response to troubleshoot
    print(response.json())

    assert response.json() == {
        "test_data": [
            {
                "id": setup_mock_data["test_result_id"].hex,
                "test_case_id": test_case_ran_id.hex,
                "Test Name": "Test Case Ran",
                "Time Taken": 5.0,
                "Status": True,
                "Error Message": None,
                "group_id": setup_mock_data["group_id"].hex,
                "group_name": "Test Group 1",
            }
        ],
        "columnList": ["Test Name", "Time Taken", "Status", "Error Message"],
    }

# Test 2: Query for the test case that has not been run
def test_get_tests_by_ids_unran_test(client, setup_mock_data):
    test_case_unran_id = setup_mock_data["test_case_unran_id"]

    # Simulate API request to get the test case that has not been run
    response = client.get(f"/get_tests_by_ids/?test_ids={test_case_unran_id.hex}&date=01-08-2023")
    assert response.status_code == 200
    assert response.json() == {
        "test_data": [
            {
                "id": None,
                "test_case_id": test_case_unran_id.hex,
                "Test Name": "Test Case Unran",
                "Time Taken": None,
                "Status": None,
                "Error Message": '',
                "group_id": setup_mock_data["group_id"].hex,
                "group_name": "Test Group 1",
            }
        ],
        "columnList": ["Test Name", "Time Taken", "Status", "Error Message"],
    }

# Test 3: Query for both test cases (one with results, one without)
def test_get_tests_by_ids_both_tests(client, setup_mock_data):
    test_case_ran_id = setup_mock_data["test_case_ran_id"]
    test_case_unran_id = setup_mock_data["test_case_unran_id"]

    # Simulate API request to get both test cases
    response = client.get(f"/get_tests_by_ids/?test_ids={test_case_ran_id.hex},{test_case_unran_id.hex}&date=01-08-2023")
    assert response.status_code == 200
    assert response.json() == {
        "test_data": [
            {
                "id": setup_mock_data["test_result_id"].hex,
                "test_case_id": test_case_ran_id.hex,
                "Test Name": "Test Case Ran",
                "Time Taken": 5.0,
                "Status": True,
                "Error Message": None,
                "group_id": setup_mock_data["group_id"].hex,
                "group_name": "Test Group 1",
            },
            {
                "id": None,
                "test_case_id": test_case_unran_id.hex,
                "Test Name": "Test Case Unran",
                "Time Taken": None,
                "Status": None,
                "Error Message": '',
                "group_id": setup_mock_data["group_id"].hex,
                "group_name": "Test Group 1",
            }
        ],
        "columnList": ["Test Name", "Time Taken", "Status", "Error Message"],
    }

#############################
###### search_tests #########
#############################

# Fixture to set up mock data
@pytest.fixture(scope="function")
def setup_mock_data_for_search(db_session):
    # Generate UUIDs for test group and test cases
    group_id = uuid4()
    test_case_1_id = uuid4()
    test_case_2_id = uuid4()
    test_case_3_id = uuid4()

    # Set up mock data once for all tests
    group = TestGroup(id=group_id.bytes, name="Test Group 1", server="localhost", port=1234, schedule=None, tls=True)

    test_case_1 = TestCase(id=test_case_1_id.bytes, test_name="Test Case Alpha", group_id=group_id.bytes, test_code="print('Alpha')")
    test_case_2 = TestCase(id=test_case_2_id.bytes, test_name="Test Case Beta", group_id=group_id.bytes, test_code="print('Beta')")
    test_case_3 = TestCase(id=test_case_3_id.bytes, test_name="Another Case", group_id=group_id.bytes, test_code="print('Another')")

    db_session.add(group)
    db_session.add(test_case_1)
    db_session.add(test_case_2)
    db_session.add(test_case_3)
    db_session.commit()

    return {
        "test_case_1_id": test_case_1_id,
        "test_case_2_id": test_case_2_id,
    }

# Test 1: Search for a pattern that returns 2 tests
def test_search_tests_matching_two_tests(client, setup_mock_data_for_search):
    # Simulate API request to search for tests matching "Test Case"
    response = client.get("/search_tests/?query=Test Case")
    assert response.status_code == 200
    assert len(response.json()) == 2
    assert response.json() == [
        {"id": setup_mock_data_for_search["test_case_1_id"].hex, "Test Name": "Test Case Alpha"},
        {"id": setup_mock_data_for_search["test_case_2_id"].hex, "Test Name": "Test Case Beta"}
    ]

# Test 2: Search for a pattern that returns no tests
def test_search_tests_no_matching_tests(client, setup_mock_data_for_search):
    # Simulate API request to search for tests matching "Nonexistent"
    response = client.get("/search_tests/?query=Nonexistent")
    assert response.status_code == 200
    assert len(response.json()) == 0
    assert response.json() == []

#############################
## search_functional_tests ##
#############################
def test_search_functional_tests(client, db_session):
    # Generate UUID for the test group
    group_id = uuid4()

    # Set up test data
    group = TestGroup(id=group_id.bytes, name="Test Group 1", server="localhost", port=1234, tls=True)
    db_session.add(group)
    db_session.commit()

    # Mock the external Kdb interaction
    with patch('endpoints.search_tests.sendKdbQuery') as mock_send_kdb_query:
        mock_send_kdb_query.return_value = [b"Test Function 1"]

        response = client.get(f"/search_functional_tests/?query=Function&limit=10&group_id={group_id.hex}")
        assert response.status_code == 200
        assert response.json() == {"success": True, "results": ["Test Function 1"], "message": ""}

