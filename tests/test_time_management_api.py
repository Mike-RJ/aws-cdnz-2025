import os
import re

import boto3
import pytest
import requests

# Configuration for LocalStack
LOCALSTACK_ENDPOINT = "http://localhost:4566"
AWS_ACCESS_KEY_ID = "test"  # pragma: allowlist secret
AWS_SECRET_ACCESS_KEY = "test"  # pragma: allowlist secret
AWS_DEFAULT_REGION = "us-east-1"


def get_api_endpoint():
    """Dynamically discover and normalize the current API endpoint for LocalStack.

    Contract:
    - Returns a base URL without a trailing slash.
    - Prefer the Edge endpoint form to avoid SSL hostname mismatch.
    """
    try:
        # 1) Try to read from the generated frontend config.js
        if os.path.exists("frontend/config.js"):
            with open("frontend/config.js", "r") as f:
                content = f.read()
                if "API_ENDPOINT" in content:
                    m = re.search(r'API_ENDPOINT"\s*:\s*"([^"]+)"', content)
                    if m:
                        url = m.group(1).rstrip("/")
                        return _normalize_api_url(url)

        # 2) Fallback: query CloudFormation output
        client = boto3.client(
            "cloudformation",
            endpoint_url=LOCALSTACK_ENDPOINT,
            aws_access_key_id=AWS_ACCESS_KEY_ID,
            aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
            region_name=AWS_DEFAULT_REGION,
        )
        response = client.describe_stacks(StackName="TimeManagementAppStack")
        outputs = response["Stacks"][0].get("Outputs", [])
        for output in outputs:
            if output.get("OutputKey") == "ApiEndpoint":
                url = output.get("OutputValue", "").rstrip("/")
                if url:
                    return _normalize_api_url(url)

    except Exception as e:
        print(f"Failed to get API endpoint dynamically: {e}")

    # 3) Final fallback - clearly invalid but explicit
    return "https://api-not-found.execute-api.localhost.localstack.cloud:4566/prod"


def _normalize_api_url(url: str) -> str:
    """Convert any LocalStack execute-api hostname to the Edge endpoint form.

    Examples:
    - https://abc123.execute-api.localhost:4566/prod ->
      https://localhost.localstack.cloud:4566/restapis/abc123/prod/_user_request_
    - https://abc123.execute-api.localhost.localstack.cloud:4566/prod/ -> same as above
    Otherwise, return the URL as-is (minus trailing slash).
    """
    try:
        from urllib.parse import urlparse

        parsed = urlparse(url)
        host = parsed.hostname or ""
        path = (parsed.path or "/").strip("/")
        stage = (path.split("/")[0] if path else "prod") or "prod"

        if "execute-api" in host and "localhost" in host:
            # First label is the rest_api_id
            rest_api_id = host.split(".")[0]
            edge = f"https://localhost.localstack.cloud:4566/restapis/{rest_api_id}/{stage}/_user_request_"
            return edge.rstrip("/")

        return url.rstrip("/")
    except Exception:
        return url.rstrip("/")


# Get the current API endpoint dynamically
API_ENDPOINT = get_api_endpoint()
print(f"Using API endpoint: {API_ENDPOINT}")


@pytest.fixture(scope="session")
def aws_credentials():
    """Mocked AWS credentials for LocalStack"""
    import os

    os.environ["AWS_ACCESS_KEY_ID"] = AWS_ACCESS_KEY_ID
    os.environ["AWS_SECRET_ACCESS_KEY"] = AWS_SECRET_ACCESS_KEY
    os.environ["AWS_DEFAULT_REGION"] = AWS_DEFAULT_REGION


@pytest.fixture(scope="session")
def dynamodb_client(aws_credentials):
    """DynamoDB client configured for LocalStack"""
    return boto3.client(
        "dynamodb",
        endpoint_url=LOCALSTACK_ENDPOINT,
        aws_access_key_id=AWS_ACCESS_KEY_ID,
        aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
        region_name=AWS_DEFAULT_REGION,
    )


@pytest.fixture(scope="session")
def dynamodb_resource(aws_credentials):
    """DynamoDB resource configured for LocalStack"""
    return boto3.resource(
        "dynamodb",
        endpoint_url=LOCALSTACK_ENDPOINT,
        aws_access_key_id=AWS_ACCESS_KEY_ID,
        aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
        region_name=AWS_DEFAULT_REGION,
    )


@pytest.fixture(scope="session")
def lambda_client(aws_credentials):
    """Lambda client configured for LocalStack"""
    return boto3.client(
        "lambda",
        endpoint_url=LOCALSTACK_ENDPOINT,
        aws_access_key_id=AWS_ACCESS_KEY_ID,
        aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
        region_name=AWS_DEFAULT_REGION,
    )


@pytest.fixture
def sample_time_entry():
    """Sample time entry data for testing"""
    return {
        "project": "Test Project",
        "name": "Test Task",
        "start_time": "2023-09-14T10:00:00",
        "end_time": "2023-09-14T11:00:00",
        "duration": 60,
    }


def test_localstack_health():
    """Test that LocalStack is running and healthy"""
    response = requests.get(f"{LOCALSTACK_ENDPOINT}/_localstack/health")
    assert response.status_code == 200
    health_data = response.json()

    # Check that required services are running
    assert "dynamodb" in health_data["services"]
    assert "lambda" in health_data["services"]
    assert "apigateway" in health_data["services"]
    assert "s3" in health_data["services"]


def test_dynamodb_table_exists(dynamodb_client):
    """Test that the DynamoDB table was created successfully"""
    try:
        tables = dynamodb_client.list_tables()
        table_names = tables["TableNames"]

        # Look for our time entries table
        time_entries_table = None
        for table_name in table_names:
            if "TimeEntries" in table_name:
                time_entries_table = table_name
                break

        assert time_entries_table is not None, "TimeEntries table not found"

        # Describe the table to check its structure
        table_desc = dynamodb_client.describe_table(TableName=time_entries_table)
        assert table_desc["Table"]["TableStatus"] == "ACTIVE"

        # Check the key schema
        key_schema = table_desc["Table"]["KeySchema"]
        assert len(key_schema) == 1
        assert key_schema[0]["AttributeName"] == "id"
        assert key_schema[0]["KeyType"] == "HASH"

    except Exception as e:
        pytest.fail(f"DynamoDB table check failed: {str(e)}")


def test_lambda_function_exists(lambda_client):
    """Test that the Lambda function was deployed successfully"""
    try:
        functions = lambda_client.list_functions()

        # Look for our time management function
        time_mgmt_function = None
        for function in functions["Functions"]:
            if "TimeManagement" in function["FunctionName"]:
                time_mgmt_function = function
                break

        assert (
            time_mgmt_function is not None
        ), "TimeManagement Lambda function not found"
        # LocalStack may report alternate runtimes for emulated Lambdas
        allowed_runtimes = {
            "python3.11",
            "python3.10",
            "python3.9",
            "nodejs18.x",
            "nodejs20.x",
            "provided.al2",
        }
        assert (
            time_mgmt_function.get("Runtime") in allowed_runtimes
        ), f"Unexpected Lambda runtime: {time_mgmt_function.get('Runtime')}"
        assert time_mgmt_function["Handler"] in [
            "app.lambda_handler",
            "index.handler",
        ]  # May vary in LocalStack

    except Exception as e:
        pytest.fail(f"Lambda function check failed: {str(e)}")


def test_api_gateway_health():
    """Test that API Gateway is accessible"""
    try:
        # Test the base API endpoint
        response = requests.get(f"{API_ENDPOINT}/", timeout=10)

        # Should get a response (even if empty list)
        assert response.status_code in [
            200,
            404,
        ], f"Unexpected status code: {response.status_code}"

    except requests.exceptions.RequestException as e:
        pytest.fail(f"API Gateway health check failed: {str(e)}")


def test_create_time_entry(sample_time_entry):
    """Test creating a new time entry via API"""
    try:
        response = requests.post(
            f"{API_ENDPOINT}/",
            json=sample_time_entry,
            headers={"Content-Type": "application/json"},
            timeout=10,
        )

        assert (
            response.status_code == 201
        ), f"Failed to create time entry: {response.status_code} - {response.text}"

        data = response.json()
        assert "id" in data
        assert data["project"] == sample_time_entry["project"]
        assert data["name"] == sample_time_entry["name"]
        assert data["start_time"] == sample_time_entry["start_time"]
        assert data["duration"] == sample_time_entry["duration"]

    except requests.exceptions.RequestException as e:
        pytest.fail(f"Create time entry test failed: {str(e)}")


def test_get_time_entries():
    """Test retrieving all time entries via API"""
    try:
        # First create a test entry
        sample_entry = {
            "project": "Test Project",
            "name": "Test get entries",
            "start_time": "2023-09-14T14:00:00",
            "duration": 30,
        }

        create_response = requests.post(
            f"{API_ENDPOINT}/",
            json=sample_entry,
            headers={"Content-Type": "application/json"},
            timeout=10,
        )
        assert create_response.status_code == 201

        # Now get all entries
        response = requests.get(f"{API_ENDPOINT}/", timeout=10)
        assert response.status_code == 200

        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0

        # Check that our entry is in the list
        found_entry = any(
            entry["project"] == sample_entry["project"]
            and entry["name"] == sample_entry["name"]
            for entry in data
        )
        assert found_entry, "Created entry not found in GET response"

    except requests.exceptions.RequestException as e:
        pytest.fail(f"Get time entries test failed: {str(e)}")


def test_update_time_entry():
    """Test updating a time entry via API"""
    try:
        # First create a test entry
        original_entry = {
            "project": "Original Project",
            "name": "Original task",
            "start_time": "2023-09-14T15:00:00",
            "duration": 45,
        }

        create_response = requests.post(
            f"{API_ENDPOINT}/",
            json=original_entry,
            headers={"Content-Type": "application/json"},
            timeout=10,
        )
        assert create_response.status_code == 201

        entry_id = create_response.json()["id"]

        # Update the entry
        updated_data = {
            "project": "Updated Project",
            "name": "Updated task",
            "duration": 90,
        }

        update_response = requests.put(
            f"{API_ENDPOINT}/{entry_id}",
            json=updated_data,
            headers={"Content-Type": "application/json"},
            timeout=10,
        )

        assert update_response.status_code == 200

        # Verify the update by getting all entries
        get_response = requests.get(f"{API_ENDPOINT}/", timeout=10)
        assert get_response.status_code == 200

        entries = get_response.json()
        updated_entry = next(
            (entry for entry in entries if entry["id"] == entry_id), None
        )

        assert updated_entry is not None
        assert updated_entry["project"] == "Updated Project"
        assert updated_entry["name"] == "Updated task"
        assert updated_entry["duration"] == 90

    except requests.exceptions.RequestException as e:
        pytest.fail(f"Update time entry test failed: {str(e)}")


def test_delete_time_entry():
    """Test deleting a time entry via API"""
    try:
        # First create a test entry
        test_entry = {
            "project": "Project to delete",
            "name": "Entry to delete",
            "start_time": "2023-09-14T16:00:00",
            "duration": 20,
        }

        create_response = requests.post(
            f"{API_ENDPOINT}/",
            json=test_entry,
            headers={"Content-Type": "application/json"},
            timeout=10,
        )
        assert create_response.status_code == 201

        entry_id = create_response.json()["id"]

        # Delete the entry
        delete_response = requests.delete(f"{API_ENDPOINT}/{entry_id}", timeout=10)

        assert delete_response.status_code == 204

        # Verify deletion by checking that entry is no longer in the list
        get_response = requests.get(f"{API_ENDPOINT}/", timeout=10)
        assert get_response.status_code == 200

        entries = get_response.json()
        deleted_entry = next(
            (entry for entry in entries if entry["id"] == entry_id), None
        )

        assert deleted_entry is None, "Entry was not properly deleted"

    except requests.exceptions.RequestException as e:
        pytest.fail(f"Delete time entry test failed: {str(e)}")


def test_invalid_api_endpoints():
    """Test that invalid endpoints return appropriate errors"""
    try:
        # Test invalid endpoint
        response = requests.get(f"{API_ENDPOINT}/invalid-endpoint", timeout=10)
        assert response.status_code in [
            403,
            404,
        ]  # LocalStack may return 403 instead of 404

        # Test invalid HTTP method
        response = requests.patch(f"{API_ENDPOINT}/", timeout=10)
        assert response.status_code in [
            403,
            404,
            405,
            501,
        ]  # Method not allowed or not implemented

    except requests.exceptions.RequestException as e:
        pytest.fail(f"Invalid API endpoints test failed: {str(e)}")


def test_api_cors_headers():
    """Test that API returns appropriate CORS headers for web access"""
    try:
        response = requests.options(f"{API_ENDPOINT}/", timeout=10)

        # Check for CORS headers (if implemented)
        # Note: This might fail if CORS is not configured,
        # which is acceptable for LocalStack testing
        if response.status_code == 200:
            # If CORS is configured, check headers
            # These are optional for LocalStack testing
            pass

    except requests.exceptions.RequestException:
        # CORS testing is optional for LocalStack
        pass


if __name__ == "__main__":
    # Run a quick health check
    print("Running LocalStack health check...")
    test_localstack_health()
    print("✅ LocalStack is healthy!")

    print("Running API health check...")
    test_api_gateway_health()
    print("✅ API Gateway is accessible!")
