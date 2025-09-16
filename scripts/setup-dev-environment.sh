#!/bin/bash

# Setup script for development environment
# This script installs pre-commit hooks and sets up the development environment

set -e

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_status() {
    echo -e "${BLUE}[SETUP]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_status "Setting up Time Management App development environment..."

# Install pre-commit if not already installed
if ! command -v pre-commit &> /dev/null; then
    print_status "Installing pre-commit..."
    pip install pre-commit
fi

# Install pre-commit hooks
print_status "Installing pre-commit hooks..."
pre-commit install
pre-commit install --hook-type pre-push

# Create secrets baseline for detect-secrets
print_status "Creating secrets baseline..."
if [ ! -f .secrets.baseline ]; then
    detect-secrets scan --baseline .secrets.baseline
fi

# Install CDK dependencies
if [ -d "cdk" ]; then
    print_status "Installing CDK dependencies..."
    cd cdk
    npm install
    cd ..
fi

# Initialize Terraform if not already done
if [ -d "terraform" ] && [ ! -d "terraform/.terraform" ]; then
    print_status "Initializing Terraform..."
    cd terraform
    if command -v tflocal &> /dev/null; then
        tflocal init
    else
        print_status "tflocal not found. Installing terraform-local..."
        pip install terraform-local
        tflocal init
    fi
    cd ..
fi

# Create git hooks directory if it doesn't exist
mkdir -p .git/hooks

# Test pre-commit setup
print_status "Testing pre-commit setup..."
if pre-commit run --all-files; then
    print_success "Pre-commit hooks are working correctly!"
else
    print_status "Pre-commit found some issues. Running auto-fixes..."
    pre-commit run --all-files || true
fi

print_success "Development environment setup complete!"
echo ""
echo "🔧 Available commands:"
echo "  ./scripts/test-api-endpoints.sh     - Test API endpoints"
echo "  ./scripts/run-infrastructure-tests.sh - Run infrastructure tests"
echo "  ./deploy-complete.sh                - Deploy with CDK"
echo "  ./deploy-terraform.sh               - Deploy with Terraform"
echo ""
echo "🚀 Git hooks installed:"
echo "  pre-commit: Code quality, linting, security"
echo "  pre-push: Infrastructure tests"
echo ""
echo "📝 To run tests manually:"
echo "  pre-commit run --all-files          - Run all pre-commit hooks"
echo "  pytest tests/ -v                    - Run Python unit tests"
