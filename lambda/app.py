#!/usr/bin/env python3

import json
import os
from datetime import datetime
from decimal import Decimal

import boto3

dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(os.environ["TABLE_NAME"])

# Common CORS headers
CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Headers": (
        "Content-Type,X-Amz-Date,Authorization," "X-Api-Key,X-Amz-Security-Token"
    ),
    "Access-Control-Allow-Methods": "GET,POST,PUT,DELETE,OPTIONS",
}


def decimal_default(obj):
    if isinstance(obj, Decimal):
        return float(obj)
    raise TypeError


def lambda_handler(event, context):
    http_method = event["httpMethod"]
    path = event.get("path", "/")

    # Handle CORS preflight requests
    if http_method == "OPTIONS":
        return {
            "statusCode": 200,
            "headers": CORS_HEADERS,
        }

    # Config endpoint not used anymore; static config.js is written during deploy

    # Handle invalid endpoints (anything that's not root or an ID)
    path_parts = path.strip("/").split("/")
    if len(path_parts) > 1 or (
        len(path_parts) == 1
        and path_parts[0]
        and not path_parts[0]
        .replace(".", "")
        .replace("-", "")
        .replace("_", "")
        .isdigit()
    ):
        # This is not a valid endpoint (not root "/" and not a numeric-like ID)
        if (
            path_parts[0] not in ["", "config"]
            and not path_parts[0]
            .replace(".", "")
            .replace("-", "")
            .replace("_", "")
            .isdigit()
        ):
            return {
                "statusCode": 404,
                "headers": {
                    "Content-Type": "application/json",
                    **CORS_HEADERS,
                },
                "body": json.dumps({"error": "Not Found"}),
            }

    # Handle time entries endpoints
    return handle_time_entries_request(event)


## Removed: handle_config_request and SSM usage


def handle_time_entries_request(event):
    """Handle requests to time entries endpoints"""
    http_method = event["httpMethod"]
    path = event.get("path", "/")

    # Parse path to extract ID for individual resource operations
    # Path formats: "/" for collections, "/{id}" for individual resources
    path_parts = path.strip("/").split("/")

    # If path has an ID component (e.g., "/123456"), extract it
    if len(path_parts) > 0 and path_parts[0] and path_parts[0] != "":
        # Create pathParameters structure for compatibility with existing functions
        if "pathParameters" not in event or event["pathParameters"] is None:
            event["pathParameters"] = {}
        event["pathParameters"]["id"] = path_parts[0]

    try:
        if http_method == "GET":
            return get_time_entries(event)
        elif http_method == "POST":
            return create_time_entry(event)
        elif http_method == "PUT":
            return update_time_entry(event)
        elif http_method == "DELETE":
            return delete_time_entry(event)
        else:
            return {
                "statusCode": 405,
                "headers": {
                    "Content-Type": "application/json",
                    **CORS_HEADERS,
                },
                "body": json.dumps({"error": "Method not allowed"}),
            }
    except Exception as e:
        return {
            "statusCode": 500,
            "headers": {
                "Content-Type": "application/json",
                # CORS_HEADERS
                "Access-Control-Allow-Headers": "Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token",
                "Access-Control-Allow-Methods": "GET,POST,PUT,DELETE,OPTIONS",
            },
            "body": json.dumps({"error": str(e)}),
        }


def get_time_entries(event):
    try:
        response = table.scan()
        items = response["Items"]
        return {
            "statusCode": 200,
            "headers": {
                "Content-Type": "application/json",
                **CORS_HEADERS,
            },
            "body": json.dumps(items, default=decimal_default),
        }
    except Exception as e:
        return {
            "statusCode": 500,
            "headers": {
                "Content-Type": "application/json",
                **CORS_HEADERS,
            },
            "body": json.dumps({"error": str(e)}),
        }


def create_time_entry(event):
    try:
        body = json.loads(event["body"])
        item = {
            "id": str(datetime.now().timestamp()),
            "project": body["project"],
            "name": body["name"],
            "start_time": body["start_time"],
            "end_time": body.get("end_time"),
            "duration": body.get("duration", 0),
            "created_at": datetime.now().isoformat(),
        }
        table.put_item(Item=item)
        return {
            "statusCode": 201,
            "headers": {
                "Content-Type": "application/json",
                **CORS_HEADERS,
            },
            "body": json.dumps(item, default=decimal_default),
        }
    except Exception as e:
        return {
            "statusCode": 500,
            "headers": {
                "Content-Type": "application/json",
                **CORS_HEADERS,
            },
            "body": json.dumps({"error": str(e)}),
        }


def update_time_entry(event):
    try:
        entry_id = event["pathParameters"]["id"]
        body = json.loads(event["body"])

        # Use expression attribute names for reserved keywords
        update_expression = (
            "SET #p = :project, #n = :name, #st = :start, #et = :end, #dur = :duration"
        )
        expression_attribute_names = {
            "#p": "project",
            "#n": "name",
            "#st": "start_time",
            "#et": "end_time",
            "#dur": "duration",
        }
        expression_attribute_values = {
            ":project": body.get("project"),
            ":name": body.get("name"),
            ":start": body.get("start_time"),
            ":end": body.get("end_time"),
            ":duration": body.get("duration", 0),
        }

        response = table.update_item(
            Key={"id": entry_id},
            UpdateExpression=update_expression,
            ExpressionAttributeNames=expression_attribute_names,
            ExpressionAttributeValues=expression_attribute_values,
            ReturnValues="ALL_NEW",
        )
        return {
            "statusCode": 200,
            "headers": {
                "Content-Type": "application/json",
                **CORS_HEADERS,
            },
            "body": json.dumps(response["Attributes"], default=decimal_default),
        }
    except Exception as e:
        return {
            "statusCode": 500,
            "headers": {
                "Content-Type": "application/json",
                **CORS_HEADERS,
            },
            "body": json.dumps({"error": str(e)}),
        }


def delete_time_entry(event):
    try:
        entry_id = event["pathParameters"]["id"]
        table.delete_item(Key={"id": entry_id})
        return {
            "statusCode": 204,
            "headers": {
                "Content-Type": "application/json",
                **CORS_HEADERS,
            },
        }
    except Exception as e:
        return {
            "statusCode": 500,
            "headers": {
                "Content-Type": "application/json",
                **CORS_HEADERS,
            },
            "body": json.dumps({"error": str(e)}),
        }
