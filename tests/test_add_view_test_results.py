import pytest
from datetime import datetime, timedelta
from models.models import TestCase, TestGroup, TestResult
from sqlalchemy import func, case

##############################
## get_test_results_30_days ##
##############################

# Fixture to set up mock data
@pytest.fixture(scope="function")
def setup_mock_data_for_30_days(db_session):
    # Set up two test groups
    group_1 = TestGroup(id=1, name="Test Group More Than 30 Days", server="localhost", port=1234, schedule="16:00", tls=True)
    group_2 = TestGroup(id=2, name="Test Group Less Than 30 Days", server="127.0.0.1", port=5678, schedule="16:30", tls=False)
    
    db_session.add(group_1)
    db_session.add(group_2)
    db_session.commit()

    # Create TestCases for both groups
    test_case_1 = TestCase(id=1, test_name="Test Case 1", group_id=1, test_code="print('Test 1')")
    test_case_2 = TestCase(id=2, test_name="Test Case 2", group_id=2, test_code="print('Test 2')")

    db_session.add(test_case_1)
    db_session.add(test_case_2)
    db_session.commit()

    # Generate 35 days of data for group_1 (more than 30 days)
    for i in range(35):
        date_run = datetime.utcnow().date() - timedelta(days=i)
        result = TestResult(
            test_case_id=1,
            group_id=1,
            date_run=date_run,
            time_taken=5.0,
            pass_status=(i % 2 == 0)  # Alternate between pass and fail
        )
        db_session.add(result)
    
    # Generate 20 days of data for group_2 (less than 30 days)
    for i in range(20):
        date_run = datetime.utcnow().date() - timedelta(days=i)
        result = TestResult(
            test_case_id=2,
            group_id=2,
            date_run=date_run,
            time_taken=5.0,
            pass_status=(i % 2 == 0)  # Alternate between pass and fail
        )
        db_session.add(result)
    
    db_session.commit()

# Test 1: Query results for group_1 with more than 30 days of data
def test_get_test_results_30_days_more_than_30(client, setup_mock_data_for_30_days):
    # Simulate a GET request to the /get_test_results_30_days/ endpoint without group_id (all data)
    response = client.get("/get_test_results_30_days/")
    
    # Validate the response
    assert response.status_code == 200
    assert len(response.json()) == 30  # Should only return results for the last 30 days

# Test 2: Query results for group_2 with less than 30 days of data, filtering by group_id
def test_get_test_results_30_days_less_than_30_with_group(client, setup_mock_data_for_30_days):
    # Simulate a GET request to the /get_test_results_30_days/ endpoint with group_id=2
    response = client.get("/get_test_results_30_days/?group_id=2")
    
    # Validate the response
    assert response.status_code == 200
    assert len(response.json()) == 20  # Should return the 20 available results for this group

    # Further validation of the response content (optional)
    for result in response.json():
        assert result["passed"] >= 0
        assert result["failed"] >= 0

# Test 3: Query results without passing a group_id (should return data for all groups)
def test_get_test_results_30_days_all_groups(client, setup_mock_data_for_30_days):
    # Simulate a GET request to the /get_test_results_30_days/ endpoint without any group_id
    response = client.get("/get_test_results_30_days/")

    # Validate the response
    assert response.status_code == 200

    # We expect the combined results from both groups within the last 30 days
    # Group 1 has 30 days of data (we're limiting to 30), and Group 2 has 20 days of data
    assert len(response.json()) == 30  # The limit is 30 days, so it should return the most recent 30 days

    # Further validation of the response content (optional)
    for result in response.json():
        assert result["passed"] >= 0
        assert result["failed"] >= 0



#############################
## get_test_results_by_day ##
#############################
TEST_DATE = "01-08-2023"

# Fixture to set up mock data
@pytest.fixture(scope="function")
def setup_mock_data_for_results_by_day(db_session):
    # Set up a test group
    group = TestGroup(id=1, name="Test Group", server="localhost", port=1234, schedule="16:00", tls=True)
    db_session.add(group)
    db_session.commit()

    # Create 200 TestCases
    for i in range(200):
        test_case = TestCase(id=i+1, test_name=f"Test Case {i+1}", group_id=1, test_code=f"print('Test {i+1}')")
        db_session.add(test_case)

    db_session.commit()

    # Add results for 75 TestCases (all on the same date)
    for i in range(75):
        test_result = TestResult(
            test_case_id=i+1,
            group_id=1,
            date_run=datetime.strptime(TEST_DATE, '%d-%m-%Y').date(),
            time_taken=5.0,
            pass_status=(i % 2 == 0)  # Alternate between pass and fail
        )
        db_session.add(test_result)

    db_session.commit()

    # Print the count of TestCases and TestResults for debugging
    total_test_cases = db_session.query(TestCase).count()
    total_test_results = db_session.query(TestResult).count()
    print(f"Total TestCases: {total_test_cases}")
    print(f"Total TestResults: {total_test_results}")

# Test 1: Query page 1 – All run tests (50 results)
def test_get_test_results_by_day_page_1(client, setup_mock_data_for_results_by_day, db_session):
    # Print the first 10 TestResults for debugging
    first_10_results = db_session.query(TestResult).limit(10).all()
    for result in first_10_results:
        print(f"TestResult ID: {result.id}, Test Case ID: {result.test_case_id}, Date Run: {result.date_run}")

    # Simulate a GET request to the /get_test_results_by_day/ endpoint for page 1
    response = client.get(f"/get_test_results_by_day/?date={TEST_DATE}&group_id=1&page_number=1")

    # Validate the response
    assert response.status_code == 200
    data = response.json()

    assert len(data["test_data"]) == 50  # Page size is 50, so we expect the first 50 run tests
    assert all(item["Status"] is not None for item in data["test_data"])  # All should be run tests

# Test 2: Query page 2 – Mix of run and unrun tests
def test_get_test_results_by_day_page_2(client, setup_mock_data_for_results_by_day, db_session):
    # Simulate a GET request to the /get_test_results_by_day/ endpoint for page 2
    response = client.get(f"/get_test_results_by_day/?date={TEST_DATE}&group_id=1&page_number=2")

    # Validate the response
    assert response.status_code == 200
    data = response.json()

    print(f"Page 2 Results: {data['test_data']}")
    assert len(data["test_data"]) == 50  # Expect 50 results on the second page
    for i in range(25):
        assert data["test_data"][i]["Status"] is not None  # Run tests
    for i in range(25, 50):
        assert data["test_data"][i]["Status"] is None  # Unrun tests

# Test 3: Query page 3 – All unrun tests
def test_get_test_results_by_day_page_3(client, setup_mock_data_for_results_by_day, db_session):
    # Simulate a GET request to the /get_test_results_by_day/ endpoint for page 3
    response = client.get(f"/get_test_results_by_day/?date={TEST_DATE}&group_id=1&page_number=3")

    # Validate the response
    assert response.status_code == 200
    data = response.json()

    print(f"Page 3 Results: {data['test_data']}")
    assert len(data["test_data"]) == 50  # Expect 50 unrun tests on the third page
    assert all(item["Status"] is None for item in data["test_data"])  # All should be unrun tests

###############################
### get_test_result_summary ###
###############################

# Fixture to set up mock data
@pytest.fixture(scope="function")
def setup_mock_data_for_summary(db_session):
    # Set up two test groups
    group_1 = TestGroup(id=1, name="Test Group 1", server="localhost", port=1234, schedule="16:00", tls=True)
    group_2 = TestGroup(id=2, name="Test Group 2", server="127.0.0.1", port=5678, schedule="16:30", tls=False)

    db_session.add(group_1)
    db_session.add(group_2)
    db_session.commit()

    # Create TestCases for both groups
    test_case_1 = TestCase(id=1, test_name="Test Case 1", group_id=1, test_code="print('Test 1')")
    test_case_2 = TestCase(id=2, test_name="Test Case 2", group_id=2, test_code="print('Test 2')")

    db_session.add(test_case_1)
    db_session.add(test_case_2)
    db_session.commit()

    # Add TestResults for both groups
    test_result_1 = TestResult(
        test_case_id=1,
        group_id=1,
        date_run=datetime.strptime(TEST_DATE, '%d-%m-%Y').date(),
        time_taken=5.0,
        pass_status=True
    )
    test_result_2 = TestResult(
        test_case_id=2,
        group_id=2,
        date_run=datetime.strptime(TEST_DATE, '%d-%m-%Y').date(),
        time_taken=7.0,
        pass_status=False
    )

    db_session.add(test_result_1)
    db_session.add(test_result_2)
    db_session.commit()

# Test 1: Query for a specific date where results exist in multiple test groups
def test_get_test_result_summary_with_results(client, setup_mock_data_for_summary):
    # Simulate a GET request to the /get_test_result_summary/ endpoint
    response = client.get(f"/get_test_result_summary/?date={TEST_DATE}")

    # Validate the response
    assert response.status_code == 200
    data = response.json()

    # We expect two groups, with one passed test in group_1 and one failed test in group_2
    assert len(data["groups_data"]) == 2
    group_1_data = next(group for group in data["groups_data"] if group["id"] == 1)
    group_2_data = next(group for group in data["groups_data"] if group["id"] == 2)

    assert group_1_data["Passed"] == 1
    assert group_1_data["Failed"] == 0

    assert group_2_data["Passed"] == 0
    assert group_2_data["Failed"] == 1

# Test 2: Query for a specific date with no results
def test_get_test_result_summary_no_results(client, setup_mock_data_for_summary):
    # Simulate a GET request to the /get_test_result_summary/ endpoint for a date with no results
    response = client.get("/get_test_result_summary/?date=02-08-2023")

    # Validate the response
    assert response.status_code == 200
    data = response.json()

    # We expect two groups, with 0 passed and 0 failed tests for both
    assert len(data["groups_data"]) == 2
    for group_data in data["groups_data"]:
        assert group_data["Passed"] == 0
        assert group_data["Failed"] == 0
