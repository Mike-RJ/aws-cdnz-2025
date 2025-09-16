import os
import sys

# Add lambda directory to Python path
lambda_dir = os.path.join(os.path.dirname(__file__), "..", "lambda")
sys.path.insert(0, lambda_dir)

# Set environment variables for testing
os.environ["AWS_ACCESS_KEY_ID"] = "test"
os.environ["AWS_SECRET_ACCESS_KEY"] = "test"
os.environ["AWS_DEFAULT_REGION"] = "us-east-1"
os.environ["TABLE_NAME"] = "test-table"
