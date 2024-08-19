from unittest.mock import patch
import pytest
from models.models import TestGroup

#############################
###### test_kdb_connection ###
#############################

# Test the /test_kdb_connection/ endpoint
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

# Test the /add_test_group/ endpoint
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

