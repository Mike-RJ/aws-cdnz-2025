#!/bin/bash

# Comprehensive API Endpoint Testing Script
# Tests API endpoints and functionality for both CDK and Terraform deployments

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_status() {
    echo -e "${BLUE}[API-TEST]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[PASS]${NC} $1"
}

print_error() {
    echo -e "${RED}[FAIL]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

# Get the current API endpoint from various sources
get_api_endpoint() {
    local endpoint=""

    # Try CDK CloudFormation outputs first
    endpoint=$(aws --endpoint-url=http://localhost:4566 --no-paginate cloudformation describe-stacks \
        --stack-name TimeManagementAppStack \
        --query 'Stacks[0].Outputs[?OutputKey==`ApiEndpoint`].OutputValue' \
        --output text 2>/dev/null || echo "")

    if [ -n "$endpoint" ] && [ "$endpoint" != "None" ]; then
        echo "$endpoint"
        return 0
    fi

    # Try SSM parameter
    endpoint=$(aws --endpoint-url=http://localhost:4566 ssm get-parameter \
        --name "/time-management-app/api-endpoint" \
        --query 'Parameter.Value' \
        --output text 2>/dev/null || echo "")

    if [ -n "$endpoint" ] && [ "$endpoint" != "None" ]; then
        echo "$endpoint"
        return 0
    fi

    # Try to find API Gateway directly
    local api_id=$(aws --endpoint-url=http://localhost:4566 apigateway get-rest-apis \
        --query 'items[?name==`time-management-api`] | [-1].id' \
        --output text 2>/dev/null || echo "")

    if [ -n "$api_id" ] && [ "$api_id" != "None" ]; then
        echo "https://${api_id}.execute-api.localhost.localstack.cloud:4566/prod"
        return 0
    fi

    return 1
}

# Test API health and functionality
test_api_endpoints() {
    local api_endpoint="$1"
    local test_passed=true

    print_status "Testing API endpoints at: $api_endpoint"

    # Remove trailing slash
    api_endpoint=${api_endpoint%/}

    # Test 1: Config endpoint
    print_status "Testing /config endpoint..."
    local config_response=$(curl -s "${api_endpoint}/config" || echo "")
    if echo "$config_response" | grep -q "apiEndpoint"; then
        print_success "Config endpoint working"
    else
        print_error "Config endpoint failed: $config_response"
        test_passed=false
    fi

    # Test 2: Time entries GET (should return empty array)
    print_status "Testing GET /time-entries..."
    local get_response=$(curl -s "${api_endpoint}/time-entries" || echo "")
    if [ "$get_response" = "[]" ]; then
        print_success "GET /time-entries working (empty array)"
    else
        print_error "GET /time-entries failed: $get_response"
        test_passed=false
    fi

    # Test 3: Time entries POST (create test entry)
    print_status "Testing POST /time-entries..."
    local test_entry='{"project":"test-project","name":"test-task","start_time":"2023-01-01T10:00:00Z","end_time":"2023-01-01T11:00:00Z","duration":60}'
    local post_response=$(curl -s -X POST \
        -H "Content-Type: application/json" \
        -d "$test_entry" \
        "${api_endpoint}/time-entries" || echo "")

    if echo "$post_response" | grep -q "id"; then
        print_success "POST /time-entries working"

        # Extract the ID for cleanup
        local entry_id=$(echo "$post_response" | grep -o '"id":"[^"]*"' | cut -d'"' -f4)

        # Test 4: Time entries GET (should now have one entry)
        print_status "Testing GET /time-entries after POST..."
        local get_after_post=$(curl -s "${api_endpoint}/time-entries" || echo "")
        if echo "$get_after_post" | grep -q "$entry_id"; then
            print_success "GET /time-entries after POST working"
        else
            print_error "GET /time-entries after POST failed"
            test_passed=false
        fi

        # Test 5: Time entries DELETE
        if [ -n "$entry_id" ]; then
            print_status "Testing DELETE /time-entries/$entry_id..."
            local delete_response=$(curl -s -X DELETE "${api_endpoint}/time-entries/${entry_id}" || echo "")
            if echo "$delete_response" | grep -q "deleted successfully"; then
                print_success "DELETE /time-entries working"
            else
                print_warning "DELETE /time-entries may have issues: $delete_response"
            fi
        fi

    else
        print_error "POST /time-entries failed: $post_response"
        test_passed=false
    fi

    # Test 6: CORS preflight
    print_status "Testing CORS preflight..."
    local cors_response=$(curl -s -X OPTIONS \
        -H "Origin: http://example.com" \
        -H "Access-Control-Request-Method: POST" \
        -H "Access-Control-Request-Headers: Content-Type" \
        "${api_endpoint}/time-entries" || echo "")

    # Check if we get 200 status (LocalStack doesn't always return headers in curl output)
    local cors_status=$(curl -s -o /dev/null -w "%{http_code}" -X OPTIONS \
        -H "Origin: http://example.com" \
        "${api_endpoint}/time-entries" || echo "000")

    if [ "$cors_status" = "200" ]; then
        print_success "CORS preflight working"
    else
        print_warning "CORS preflight may have issues (status: $cors_status)"
    fi

    if $test_passed; then
        return 0
    else
        return 1
    fi
}

# Main execution
main() {
    print_status "Starting API endpoint tests..."

    # Check if LocalStack is running
    if ! curl -s http://localhost:4566/_localstack/health > /dev/null; then
        print_error "LocalStack is not running. Please start LocalStack first."
        return 1
    fi

    # Get API endpoint
    local api_endpoint
    if api_endpoint=$(get_api_endpoint); then
        print_success "Found API endpoint: $api_endpoint"
    else
        print_error "Could not find API endpoint. Make sure the stack is deployed."
        return 1
    fi

    # Run API tests
    if test_api_endpoints "$api_endpoint"; then
        print_success "All API tests passed!"
        return 0
    else
        print_error "Some API tests failed"
        return 1
    fi
}

# Allow script to be sourced or run directly
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi
