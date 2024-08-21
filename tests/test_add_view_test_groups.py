from unittest.mock import patch
import pytest
from sqlalchemy.orm import sessionmaker
from datetime import datetime
from models.models import TestCase, TestGroup, TestResult
from sqlalchemy import func

#############################
###### test_kdb_connection ###
#############################

@patch('endpoints.add_view_test_groups.test_kdb_conn')  # Mocking the kdb connection function
def test_test_kdb_connection(mock_test_kdb_conn, client, db_session):
    # Mock the response from the kdb connection function
    mock_test_kdb_conn.return_value = "Kdb connection successful"

    data = {
        "server": "localhost",
        "port": 1234,
        "tls": True,
    }

    # Simulate a POST request to the /test_kdb_connection/ endpoint
    response = client.post("/test_kdb_connection/", json=data)
    
    # Validate the response
    assert response.status_code == 200
    assert response.json() == {"message": "success", "details": "Kdb connection successful"}

#############################
###### add_test_group ########
#############################

@patch('endpoints.add_view_test_groups.requests.post')  # Mocking the HTTP request to the scheduler
def test_add_test_group(mock_requests_post, client, db_session):
    # Mock the scheduler response
    mock_requests_post.return_value.status_code = 200

    data = {
        "name": "New Test Group",
        "server": "localhost",
        "port": 1234,
        "schedule": "16:34",
        "tls": True
    }

    # Simulate a POST request to the /add_test_group/ endpoint
    response = client.post("/add_test_group/", json=data)

    # Validate the response
    assert response.status_code == 200
    assert "message" in response.json()
    assert response.json()["message"] == "Test group added successfully"
    assert "id" in response.json()

    # Ensure the group was added to the database
    group_id = response.json()["id"]
    added_group = db_session.query(TestGroup).filter_by(id=group_id).first()
    assert added_group is not None
    assert added_group.name == "New Test Group"
    assert added_group.server == "localhost"
    assert added_group.port == 1234
    assert added_group.schedule == "16:34"
    assert added_group.tls is True


#############################
##### edit_test_group #######
#############################

@patch('endpoints.add_view_test_groups.requests.post')  # Mocking the HTTP request to the scheduler
def test_edit_test_group(mock_requests_post, client, db_session):
    # Mock the scheduler response
    mock_requests_post.return_value.status_code = 200

    # Set up a test group in the database
    group = TestGroup(name="Old Test Group", server="localhost", port=1234, schedule="16:00", tls=True)
    db_session.add(group)
    db_session.commit()

    # Get the group's ID for later verification
    group_id = group.id

    # Define the update data (adjust to match your TestGroupUpdate schema)
    update_data = {
        "name": "Updated Test Group",
        "server": "127.0.0.1",
        "port": 5678,
        "schedule": "16:35",
        "tls": False
    }

    # Simulate a PUT request to the /edit_test_group/{group_id}/ endpoint
    response = client.put(f"/edit_test_group/{group_id}/", json=update_data)

    # Validate the response
    assert response.status_code == 200
    assert response.json() == {"message": "Test group updated successfully"}

    # Create a new session using the same sessionmaker for verification
    Session = sessionmaker(bind=db_session.get_bind())  # Get the sessionmaker from the current session
    new_session = Session()  # Create a new session

    try:
        # Query the group to verify the update
        updated_group = new_session.query(TestGroup).filter_by(id=group_id).first()

        # Ensure the group was updated in the database
        assert updated_group.name == "Updated Test Group"
        assert updated_group.server == "127.0.0.1"
        assert updated_group.port == 5678
        assert updated_group.schedule == "16:35"
        assert updated_group.tls is False
    finally:
        # Close the new session
        new_session.close()

#############################
##### get_test_groups #######
#############################

def test_get_test_groups(client, db_session):
    # Set up some test groups in the database
    group_1 = TestGroup(name="Test Group 1", server="localhost", port=1234, schedule="16:00", tls=True)
    group_2 = TestGroup(name="Test Group 2", server="127.0.0.1", port=5678, schedule="16:35", tls=False)
    db_session.add(group_1)
    db_session.add(group_2)
    db_session.commit()

    # Simulate a GET request to the /test_groups/ endpoint
    response = client.get("/test_groups/")

    # Validate the response
    assert response.status_code == 200
    assert len(response.json()) == 2
    assert response.json() == [
        {
            "id": group_1.id,
            "name": "Test Group 1",
            "server": "localhost",
            "port": 1234,
            "schedule": "16:00",
            "tls": True
        },
        {
            "id": group_2.id,
            "name": "Test Group 2",
            "server": "127.0.0.1",
            "port": 5678,
            "schedule": "16:35",
            "tls": False
        }
    ]

#############################
### get_test_group_stats ####
#############################

# Fixture to set up mock data
@pytest.fixture(scope="function")
def setup_mock_data_for_stats(db_session):
    # Set up a test group and test cases with results
    group = TestGroup(id=1, name="Test Group 1", server="localhost", port=1234, schedule="16:00", tls=True)
    
    test_case_passed = TestCase(id=1, test_name="Test Case Passed", group_id=1, test_code="print('Passed')")
    test_case_failed = TestCase(id=2, test_name="Test Case Failed", group_id=1, test_code="print('Failed')")

    test_result_passed = TestResult(
        id=1, test_case_id=1, group_id=1, date_run=datetime(2023, 8, 1).date(),
        time_taken=5.0, pass_status=True
    )
    test_result_failed = TestResult(
        id=2, test_case_id=2, group_id=1, date_run=datetime(2023, 8, 1).date(),
        time_taken=7.0, pass_status=False
    )

    db_session.add(group)
    db_session.add(test_case_passed)
    db_session.add(test_case_failed)
    db_session.add(test_result_passed)
    db_session.add(test_result_failed)
    db_session.commit()

# Test 1: Query stats for a specific date and group
def test_get_test_group_stats(client, setup_mock_data_for_stats):
    # Simulate a GET request to the /get_test_group_stats/ endpoint
    response = client.get("/get_test_group_stats/?date=01-08-2023&group_id=1")
    
    # Validate the response
    assert response.status_code == 200
    assert response.json() == {
        "total_passed": 1,
        "total_failed": 1
    }

# Test 3: Test with no results for the date
def test_get_test_group_stats_no_results(client, setup_mock_data_for_stats):
    # Simulate a GET request to the /get_test_group_stats/ endpoint for a date with no results
    response = client.get("/get_test_group_stats/?date=02-08-2023&group_id=1")
    
    # Validate the response
    assert response.status_code == 200
    assert response.json() == {
        "total_passed": 0,
        "total_failed": 0
    }

