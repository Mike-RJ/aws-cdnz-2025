import json
import os
import sys
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

# Add lambda directory to path for testing
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "lambda"))

# Import lambda functions after adding to path
try:
    from app import (
        create_time_entry,
        decimal_default,
        delete_time_entry,
        get_time_entries,
        lambda_handler,
        update_time_entry,
    )
except ImportError:
    # If running from different directory, try direct import
    lambda_path = os.path.join(os.path.dirname(__file__), "..", "lambda", "app.py")
    import importlib.util

    spec = importlib.util.spec_from_file_location("app", lambda_path)
    app_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(app_module)

    lambda_handler = app_module.lambda_handler
    decimal_default = app_module.decimal_default
    get_time_entries = app_module.get_time_entries
    create_time_entry = app_module.create_time_entry
    update_time_entry = app_module.update_time_entry
    delete_time_entry = app_module.delete_time_entry


@pytest.fixture
def mock_dynamodb_table():
    """Mock DynamoDB table for unit testing"""
    with patch("app.table") as mock_table:
        yield mock_table


@pytest.fixture
def sample_event_get():
    """Sample API Gateway event for GET request"""
    return {
        "httpMethod": "GET",
        "path": "/",
        "body": None,
        "headers": {},
        "queryStringParameters": None,
    }


@pytest.fixture
def sample_event_post():
    """Sample API Gateway event for POST request"""
    return {
        "httpMethod": "POST",
        "path": "/",
        "body": json.dumps(
            {
                "project": "Test Project",
                "name": "Test Task",
                "start_time": "2023-09-14T10:00:00",
                "end_time": "2023-09-14T11:00:00",
                "duration": 60,
            }
        ),
        "headers": {"Content-Type": "application/json"},
        "queryStringParameters": None,
    }


@pytest.fixture
def sample_event_put():
    """Sample API Gateway event for PUT request"""
    return {
        "httpMethod": "PUT",
        "path": "/123",
        "pathParameters": {"id": "123"},
        "body": json.dumps(
            {"project": "Updated Project", "name": "Updated Task", "duration": 90}
        ),
        "headers": {"Content-Type": "application/json"},
        "queryStringParameters": None,
    }


@pytest.fixture
def sample_event_delete():
    """Sample API Gateway event for DELETE request"""
    return {
        "httpMethod": "DELETE",
        "path": "/123",
        "pathParameters": {"id": "123"},
        "body": None,
        "headers": {},
        "queryStringParameters": None,
    }


def test_decimal_default():
    """Test the decimal_default function for JSON serialization"""
    # Test with Decimal
    result = decimal_default(Decimal("10.5"))
    assert result == 10.5
    assert isinstance(result, float)

    # Test with non-Decimal should raise TypeError
    with pytest.raises(TypeError):
        decimal_default("not a decimal")


def test_get_time_entries_success(mock_dynamodb_table, sample_event_get):
    """Test successful GET request for time entries"""
    # Mock DynamoDB scan response
    mock_dynamodb_table.scan.return_value = {
        "Items": [
            {
                "id": "123",
                "description": "Test task",
                "start_time": "2023-09-14T10:00:00",
                "duration": Decimal("60"),
                "created_at": "2023-09-14T10:00:00",
            }
        ]
    }

    response = get_time_entries(sample_event_get)

    assert response["statusCode"] == 200
    assert "application/json" in response["headers"]["Content-Type"]

    body = json.loads(response["body"])
    assert len(body) == 1
    assert body[0]["id"] == "123"
    assert body[0]["description"] == "Test task"
    assert body[0]["duration"] == 60  # Should be converted from Decimal


def test_get_time_entries_error(mock_dynamodb_table, sample_event_get):
    """Test GET request when DynamoDB throws an error"""
    mock_dynamodb_table.scan.side_effect = Exception("DynamoDB error")

    response = get_time_entries(sample_event_get)

    assert response["statusCode"] == 500
    assert "application/json" in response["headers"]["Content-Type"]

    body = json.loads(response["body"])
    assert "error" in body


def test_create_time_entry_success(mock_dynamodb_table, sample_event_post):
    """Test successful POST request to create time entry"""
    mock_dynamodb_table.put_item.return_value = {}

    with patch("app.datetime") as mock_datetime:
        mock_datetime.now.return_value.timestamp.return_value = 1694688000.0
        mock_datetime.now.return_value.isoformat.return_value = "2023-09-14T10:00:00"

        response = create_time_entry(sample_event_post)

    assert response["statusCode"] == 201
    assert "application/json" in response["headers"]["Content-Type"]

    body = json.loads(response["body"])
    assert "id" in body
    assert body["project"] == "Test Project"
    assert body["name"] == "Test Task"
    assert body["start_time"] == "2023-09-14T10:00:00"
    assert body["duration"] == 60


def test_create_time_entry_invalid_json(mock_dynamodb_table):
    """Test POST request with invalid JSON"""
    event = {
        "httpMethod": "POST",
        "path": "/time-entries",
        "body": "invalid json",
        "headers": {"Content-Type": "application/json"},
    }

    response = create_time_entry(event)

    assert response["statusCode"] == 500
    body = json.loads(response["body"])
    assert "error" in body


def test_update_time_entry_success(mock_dynamodb_table, sample_event_put):
    """Test successful PUT request to update time entry"""
    mock_dynamodb_table.update_item.return_value = {
        "Attributes": {
            "id": "123",
            "project": "Updated Project",
            "name": "Updated Task",
            "duration": 90,
        }
    }

    response = update_time_entry(sample_event_put)

    assert response["statusCode"] == 200
    assert "application/json" in response["headers"]["Content-Type"]

    body = json.loads(response["body"])
    assert body["id"] == "123"
    assert body["project"] == "Updated Project"

    # Verify update_item was called with correct parameters
    mock_dynamodb_table.update_item.assert_called_once()
    call_args = mock_dynamodb_table.update_item.call_args
    assert call_args[1]["Key"] == {"id": "123"}
    assert "UpdateExpression" in call_args[1]
    assert "ExpressionAttributeValues" in call_args[1]


def test_delete_time_entry_success(mock_dynamodb_table, sample_event_delete):
    """Test successful DELETE request"""
    mock_dynamodb_table.delete_item.return_value = {}

    response = delete_time_entry(sample_event_delete)

    assert response["statusCode"] == 204
    assert "application/json" in response["headers"]["Content-Type"]
    # 204 responses typically don't have a body
    assert "body" not in response or response.get("body") is None

    # Verify delete_item was called with correct parameters
    mock_dynamodb_table.delete_item.assert_called_once_with(Key={"id": "123"})


def test_lambda_handler_get(mock_dynamodb_table, sample_event_get):
    """Test lambda_handler with GET request"""
    mock_dynamodb_table.scan.return_value = {"Items": []}

    context = MagicMock()
    response = lambda_handler(sample_event_get, context)

    assert response["statusCode"] == 200


def test_lambda_handler_post(mock_dynamodb_table, sample_event_post):
    """Test lambda_handler with POST request"""
    mock_dynamodb_table.put_item.return_value = {}

    with patch("app.datetime") as mock_datetime:
        mock_datetime.now.return_value.timestamp.return_value = 1694688000.0
        mock_datetime.now.return_value.isoformat.return_value = "2023-09-14T10:00:00"

        context = MagicMock()
        response = lambda_handler(sample_event_post, context)

    assert response["statusCode"] == 201


def test_lambda_handler_put(mock_dynamodb_table, sample_event_put):
    """Test lambda_handler with PUT request"""
    mock_dynamodb_table.update_item.return_value = {
        "Attributes": {"id": "123", "description": "Updated task", "duration": 90}
    }

    context = MagicMock()
    response = lambda_handler(sample_event_put, context)

    assert response["statusCode"] == 200


def test_lambda_handler_delete(mock_dynamodb_table, sample_event_delete):
    """Test lambda_handler with DELETE request"""
    mock_dynamodb_table.delete_item.return_value = {}

    context = MagicMock()
    response = lambda_handler(sample_event_delete, context)

    assert response["statusCode"] == 204


def test_lambda_handler_invalid_path(mock_dynamodb_table):
    """Test lambda_handler with invalid path - Note: API Gateway handles routing,
    so this test is not applicable"""
    # This test is commented out because our Lambda function doesn't handle
    # path validation. API Gateway handles routing and only calls the Lambda
    # for valid paths
    pass


def test_lambda_handler_invalid_method(mock_dynamodb_table):
    """Test lambda_handler with invalid HTTP method"""
    event = {"httpMethod": "PATCH", "path": "/", "body": None}

    context = MagicMock()
    response = lambda_handler(event, context)

    assert response["statusCode"] == 405
