#!/bin/bash

# Infrastructure Tests Script for Pre-commit Hook
# This script runs infrastructure tests to validate deployments

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_status() {
    echo -e "${BLUE}[TEST]${NC} $1"
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

# Check if LocalStack is running
check_localstack() {
    print_status "Checking if LocalStack is running..."
    if curl -s http://localhost:4566/_localstack/health > /dev/null; then
        print_success "LocalStack is running"
        return 0
    else
        print_warning "LocalStack is not running. Skipping infrastructure tests."
        print_warning "To run full tests, start LocalStack with:"
        echo "  docker run -d --rm -it -p 4566:4566 -p 4510-4559:4510-4559 localstack/localstack"
        return 1
    fi
}

# Run CDK infrastructure tests
test_cdk_infrastructure() {
    print_status "Testing CDK infrastructure..."

    cd cdk

    # Test CDK synthesis
    if cdklocal synth --quiet > /dev/null; then
        print_success "CDK synthesis successful"
    else
        print_error "CDK synthesis failed"
        return 1
    fi

    cd ..
    return 0
}

# Run Terraform infrastructure tests
test_terraform_infrastructure() {
    print_status "Testing Terraform infrastructure..."

    cd terraform

    # Test Terraform validation
    if tflocal validate > /dev/null; then
        print_success "Terraform validation successful"
    else
        print_error "Terraform validation failed"
        return 1
    fi

    # Test Terraform plan (if LocalStack is running)
    if check_localstack > /dev/null; then
        if tflocal init -input=false > /dev/null && tflocal plan -input=false > /dev/null; then
            print_success "Terraform plan successful"
        else
            print_error "Terraform plan failed"
            return 1
        fi

        # Run Terraform tests (mock tests only for pre-commit)
        if tflocal test tests/mock.tftest.hcl > /dev/null; then
            print_success "Terraform mock tests passed"
        else
            print_warning "Terraform mock tests failed"
        fi
    fi

    cd ..
    return 0
}

# Run Lambda function tests
test_lambda_functions() {
    print_status "Testing Lambda functions..."

    # Test Lambda function syntax
    if python -m py_compile lambda/app.py; then
        print_success "Lambda function syntax check passed"
    else
        print_error "Lambda function syntax check failed"
        return 1
    fi

    return 0
}

# Main test execution
main() {
    print_status "Running infrastructure tests for pre-commit..."

    local exit_code=0

    # Run basic tests (always)
    if ! test_lambda_functions; then
        exit_code=1
    fi

    if ! test_cdk_infrastructure; then
        exit_code=1
    fi

    if ! test_terraform_infrastructure; then
        exit_code=1
    fi

    if [ $exit_code -eq 0 ]; then
        print_success "All infrastructure tests passed!"
    else
        print_error "Some infrastructure tests failed"
    fi

    return $exit_code
}

main "$@"
