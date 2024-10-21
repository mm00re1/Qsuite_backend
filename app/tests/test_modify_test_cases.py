import pytest
from uuid import uuid4  # Import uuid4 for generating UUIDs
from models.models import TestCase, TestGroup, TestDependency

#############################
###### add_test_case ########
#############################

# Test the /add_test_case/ endpoint
def test_add_test_case(client, db_session):
    # Set up a test group in the database
    group_id = uuid4()
    group = TestGroup(id=group_id.bytes, name="Test Group", server="localhost", port=1234, schedule="16:00", tls=True)
    db_session.add(group)
    db_session.commit()

    # Add a couple of test cases to be used as dependencies
    dependency_1_id = uuid4()
    dependency_2_id = uuid4()

    dependency_1 = TestCase(id=dependency_1_id.bytes, test_name="Dependency 1", group_id=group_id.bytes, test_code="print('Dep 1')")
    dependency_2 = TestCase(id=dependency_2_id.bytes, test_name="Dependency 2", group_id=group_id.bytes, test_code="print('Dep 2')")
    db_session.add(dependency_1)
    db_session.add(dependency_2)
    db_session.commit()

    # Define the input data for the new test case
    data = {
        "group_id": group_id.hex,
        "test_name": "New Test Case",
        "test_code": "print('Test')",
        "free_form": True,
        "dependencies": [dependency_1_id.hex, dependency_2_id.hex]  # Add dependencies
    }

    # Simulate a POST request to the /add_test_case/ endpoint
    response = client.post("/add_test_case/", json=data)

    # Validate the response
    assert response.status_code == 200
    assert response.json()["message"] == "Test case added successfully"

    # Ensure the test case was added to the database
    test_case_id = response.json()["id"]
    added_test_case = db_session.query(TestCase).filter_by(id=bytes.fromhex(test_case_id)).first()
    assert added_test_case is not None
    assert added_test_case.test_name == "New Test Case"

    # Ensure the dependencies were added correctly
    dependencies = db_session.query(TestDependency).filter_by(test_id=bytes.fromhex(test_case_id)).all()
    assert len(dependencies) == 2
    assert dependencies[0].dependent_test_id == dependency_1_id.bytes
    assert dependencies[1].dependent_test_id == dependency_2_id.bytes

#############################
###### edit_test_case #######
#############################

# Test the /edit_test_case/ endpoint
def test_edit_test_case(client, db_session):
    # Set up a test group in the database
    group_id = uuid4()
    group = TestGroup(id=group_id.bytes, name="Test Group", server="localhost", port=1234, schedule="16:00", tls=True)
    db_session.add(group)
    db_session.commit()

    # Add a test case and dependencies to the database
    test_case_id = uuid4()
    dependency_1_id = uuid4()
    dependency_2_id = uuid4()

    test_case = TestCase(id=test_case_id.bytes, test_name="Test Case", group_id=group_id.bytes, test_code="print('Test')")
    dependency_1 = TestCase(id=dependency_1_id.bytes, test_name="Dependency 1", group_id=group_id.bytes, test_code="print('Dep 1')")
    dependency_2 = TestCase(id=dependency_2_id.bytes, test_name="Dependency 2", group_id=group_id.bytes, test_code="print('Dep 2')")
    db_session.add(test_case)
    db_session.add(dependency_1)
    db_session.add(dependency_2)
    db_session.commit()

    # Add initial dependencies for the test case
    initial_dependency = TestDependency(test_id=test_case_id.bytes, dependent_test_id=dependency_1_id.bytes)
    db_session.add(initial_dependency)
    db_session.commit()

    # Define the update data for editing the test case
    data = {
        "id": test_case_id.hex,
        "test_name": "Updated Test Case",
        "test_code": "print('Updated Test')",
        "dependencies": [dependency_2_id.hex]  # Update the dependencies
    }

    # Simulate a PUT request to the /edit_test_case/ endpoint
    response = client.put("/edit_test_case/", json=data)

    # Validate the response
    assert response.status_code == 200
    assert response.json()["message"] == "Test case edited successfully"

    # Ensure the test case was updated in the database
    updated_test_case = db_session.query(TestCase).filter_by(id=test_case_id.bytes).first()
    assert updated_test_case.test_name == "Updated Test Case"
    assert updated_test_case.test_code == "print('Updated Test')"

    # Ensure the dependencies were updated correctly
    dependencies = db_session.query(TestDependency).filter_by(test_id=test_case_id.bytes).all()
    assert len(dependencies) == 1
    assert dependencies[0].dependent_test_id == dependency_2_id.bytes  # The dependency should now be the updated one

