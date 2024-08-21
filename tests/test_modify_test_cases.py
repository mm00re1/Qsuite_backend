import pytest
from models.models import TestCase, TestGroup, TestDependency

#############################
###### add_test_case ########
#############################

# Test the /add_test_case/ endpoint
def test_add_test_case(client, db_session):
    # Set up a test group in the database
    group = TestGroup(id=1, name="Test Group", server="localhost", port=1234, schedule="16:00", tls=True)
    db_session.add(group)
    db_session.commit()

    # Add a couple of test cases to be used as dependencies
    dependency_1 = TestCase(id=1, test_name="Dependency 1", group_id=1, test_code="print('Dep 1')")
    dependency_2 = TestCase(id=2, test_name="Dependency 2", group_id=1, test_code="print('Dep 2')")
    db_session.add(dependency_1)
    db_session.add(dependency_2)
    db_session.commit()

    # Define the input data for the new test case
    data = {
        "group_id": 1,
        "test_name": "New Test Case",
        "test_code": "print('Test')",
        "free_form": True,
        "dependencies": [1, 2]  # Add dependencies
    }

    # Simulate a POST request to the /add_test_case/ endpoint
    response = client.post("/add_test_case/", json=data)

    # Validate the response
    assert response.status_code == 200
    assert response.json()["message"] == "Test case added successfully"

    # Ensure the test case was added to the database
    test_case_id = response.json()["id"]
    added_test_case = db_session.query(TestCase).filter_by(id=test_case_id).first()
    assert added_test_case is not None
    assert added_test_case.test_name == "New Test Case"

    # Ensure the dependencies were added correctly
    dependencies = db_session.query(TestDependency).filter_by(test_id=test_case_id).all()
    assert len(dependencies) == 2
    assert dependencies[0].dependent_test_id == 1
    assert dependencies[1].dependent_test_id == 2

#############################
###### edit_test_case #######
#############################

# Test the /edit_test_case/ endpoint
def test_edit_test_case(client, db_session):
    # Set up a test group in the database
    group = TestGroup(id=1, name="Test Group", server="localhost", port=1234, schedule="16:00", tls=True)
    db_session.add(group)
    db_session.commit()

    # Add a test case and dependencies to the database
    test_case = TestCase(id=1, test_name="Test Case", group_id=1, test_code="print('Test')")
    dependency_1 = TestCase(id=2, test_name="Dependency 1", group_id=1, test_code="print('Dep 1')")
    dependency_2 = TestCase(id=3, test_name="Dependency 2", group_id=1, test_code="print('Dep 2')")
    db_session.add(test_case)
    db_session.add(dependency_1)
    db_session.add(dependency_2)
    db_session.commit()

    # Add initial dependencies for the test case
    initial_dependency = TestDependency(test_id=1, dependent_test_id=2)
    db_session.add(initial_dependency)
    db_session.commit()

    # Define the update data for editing the test case
    data = {
        "id": 1,
        "test_name": "Updated Test Case",
        "test_code": "print('Updated Test')",
        "dependencies": [3]  # Update the dependencies
    }

    # Simulate a PUT request to the /edit_test_case/ endpoint
    response = client.put("/edit_test_case/", json=data)

    # Validate the response
    assert response.status_code == 200
    assert response.json()["message"] == "Test case edited successfully"

    # Ensure the test case was updated in the database
    updated_test_case = db_session.query(TestCase).filter_by(id=1).first()
    assert updated_test_case.test_name == "Updated Test Case"
    assert updated_test_case.test_code == "print('Updated Test')"

    # Ensure the dependencies were updated correctly
    dependencies = db_session.query(TestDependency).filter_by(test_id=1).all()
    assert len(dependencies) == 1
    assert dependencies[0].dependent_test_id == 3  # The dependency should now be the updated one

