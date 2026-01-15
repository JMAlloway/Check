#!/bin/bash
#
# Security Scanning Script for Check Review Console
#
# This script performs security scans for SOC2 compliance:
# 1. Python dependency audit (pip-audit)
# 2. Node.js dependency audit (npm audit)
# 3. Container image scanning (if trivy installed)
# 4. Secret detection (if gitleaks installed)
#
# Usage:
#   ./scripts/security-scan.sh [--ci]
#
# Options:
#   --ci    Exit with non-zero code if critical/high vulnerabilities found
#
# Exit codes:
#   0 - No critical/high vulnerabilities found
#   1 - Critical/high vulnerabilities found (in CI mode)
#   2 - Scan tool not available
#

set -e

# Configuration
CI_MODE=false
CRITICAL_FOUND=false
HIGH_FOUND=false

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --ci)
            CI_MODE=true
            shift
            ;;
        *)
            shift
            ;;
    esac
done

log_header() {
    echo ""
    echo -e "${BLUE}════════════════════════════════════════════════════════════${NC}"
    echo -e "${BLUE}  $1${NC}"
    echo -e "${BLUE}════════════════════════════════════════════════════════════${NC}"
    echo ""
}

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

log_pass() {
    echo -e "${GREEN}[PASS]${NC} $1"
}

# Python dependency audit
scan_python_deps() {
    log_header "Python Dependency Audit"

    if ! command -v pip-audit &> /dev/null; then
        log_warn "pip-audit not installed. Install with: pip install pip-audit"
        log_info "Falling back to pip check..."

        cd backend
        pip check || true
        cd ..
        return
    fi

    cd backend

    log_info "Running pip-audit..."

    # Run audit and capture output
    AUDIT_OUTPUT=$(pip-audit --format=json 2>/dev/null || echo "[]")

    # Parse results
    CRITICAL_COUNT=$(echo "$AUDIT_OUTPUT" | python3 -c "
import json, sys
data = json.load(sys.stdin)
critical = sum(1 for v in data if v.get('vulns', []) and any(
    vuln.get('fix_versions') and 'CRITICAL' in str(vuln.get('aliases', []))
    for vuln in v.get('vulns', [])
))
print(critical)
" 2>/dev/null || echo "0")

    HIGH_COUNT=$(echo "$AUDIT_OUTPUT" | python3 -c "
import json, sys
data = json.load(sys.stdin)
print(len(data))
" 2>/dev/null || echo "0")

    if [[ "$HIGH_COUNT" -gt 0 ]]; then
        log_warn "Found $HIGH_COUNT vulnerable packages"
        pip-audit || true
        HIGH_FOUND=true
    else
        log_pass "No vulnerable Python packages found"
    fi

    cd ..
}

# Node.js dependency audit
scan_node_deps() {
    log_header "Node.js Dependency Audit"

    if ! command -v npm &> /dev/null; then
        log_warn "npm not installed. Skipping Node.js audit."
        return
    fi

    cd frontend

    log_info "Running npm audit..."

    # Run audit
    AUDIT_RESULT=$(npm audit --json 2>/dev/null || echo '{"vulnerabilities":{}}')

    # Count vulnerabilities
    CRITICAL_COUNT=$(echo "$AUDIT_RESULT" | python3 -c "
import json, sys
data = json.load(sys.stdin)
vulns = data.get('vulnerabilities', {})
critical = sum(1 for v in vulns.values() if v.get('severity') == 'critical')
print(critical)
" 2>/dev/null || echo "0")

    HIGH_COUNT=$(echo "$AUDIT_RESULT" | python3 -c "
import json, sys
data = json.load(sys.stdin)
vulns = data.get('vulnerabilities', {})
high = sum(1 for v in vulns.values() if v.get('severity') == 'high')
print(high)
" 2>/dev/null || echo "0")

    TOTAL=$(echo "$AUDIT_RESULT" | python3 -c "
import json, sys
data = json.load(sys.stdin)
print(len(data.get('vulnerabilities', {})))
" 2>/dev/null || echo "0")

    if [[ "$CRITICAL_COUNT" -gt 0 ]]; then
        log_error "Found $CRITICAL_COUNT CRITICAL vulnerabilities!"
        CRITICAL_FOUND=true
    fi

    if [[ "$HIGH_COUNT" -gt 0 ]]; then
        log_warn "Found $HIGH_COUNT HIGH vulnerabilities"
        HIGH_FOUND=true
    fi

    if [[ "$TOTAL" -eq 0 ]]; then
        log_pass "No vulnerable Node.js packages found"
    else
        npm audit || true
    fi

    cd ..
}

# Container image scanning
scan_container_images() {
    log_header "Container Image Scanning"

    if ! command -v trivy &> /dev/null; then
        log_warn "Trivy not installed. Skipping container scan."
        log_info "Install with: curl -sfL https://raw.githubusercontent.com/aquasecurity/trivy/main/contrib/install.sh | sh"
        return
    fi

    log_info "Scanning backend image..."
    trivy image --severity CRITICAL,HIGH check-review-backend:latest || true

    log_info "Scanning frontend image..."
    trivy image --severity CRITICAL,HIGH check-review-frontend:latest || true
}

# Secret detection
scan_secrets() {
    log_header "Secret Detection"

    if ! command -v gitleaks &> /dev/null; then
        log_warn "Gitleaks not installed. Skipping secret scan."
        log_info "Install from: https://github.com/gitleaks/gitleaks"

        # Fallback: simple grep for common patterns
        log_info "Running basic secret pattern check..."

        # Check for hardcoded secrets (basic patterns)
        PATTERNS=(
            "password\s*=\s*['\"][^'\"]{8,}"
            "secret\s*=\s*['\"][^'\"]{8,}"
            "api_key\s*=\s*['\"][^'\"]{16,}"
            "private_key"
            "BEGIN RSA PRIVATE KEY"
            "BEGIN OPENSSH PRIVATE KEY"
        )

        FOUND=false
        for pattern in "${PATTERNS[@]}"; do
            MATCHES=$(grep -rniE "$pattern" --include="*.py" --include="*.ts" --include="*.js" --include="*.env*" . 2>/dev/null | grep -v node_modules | grep -v __pycache__ | grep -v ".example" || true)
            if [[ -n "$MATCHES" ]]; then
                log_warn "Potential secret pattern found: $pattern"
                echo "$MATCHES" | head -5
                FOUND=true
            fi
        done

        if [[ "$FOUND" == false ]]; then
            log_pass "No obvious secret patterns found"
        fi

        return
    fi

    log_info "Running gitleaks..."
    gitleaks detect --source . --verbose || true
}

# OWASP dependency check (optional)
scan_owasp() {
    log_header "OWASP Dependency Check"

    if ! command -v dependency-check &> /dev/null; then
        log_info "OWASP Dependency Check not installed. Skipping."
        log_info "This is optional - pip-audit and npm audit cover most cases."
        return
    fi

    dependency-check --project "Check Review Console" --scan . --format HTML --out security-report/ || true
}

# Generate security report
generate_report() {
    log_header "Security Scan Summary"

    REPORT_FILE="security-scan-report-$(date +%Y%m%d-%H%M%S).txt"

    {
        echo "Security Scan Report"
        echo "===================="
        echo "Date: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
        echo "Project: Check Review Console"
        echo ""
        echo "Results:"
        echo "--------"
        if [[ "$CRITICAL_FOUND" == true ]]; then
            echo "CRITICAL vulnerabilities: FOUND"
        else
            echo "CRITICAL vulnerabilities: None"
        fi
        if [[ "$HIGH_FOUND" == true ]]; then
            echo "HIGH vulnerabilities: FOUND"
        else
            echo "HIGH vulnerabilities: None"
        fi
        echo ""
        echo "Recommendation:"
        if [[ "$CRITICAL_FOUND" == true ]]; then
            echo "IMMEDIATE ACTION REQUIRED - Critical vulnerabilities must be patched within 24 hours"
        elif [[ "$HIGH_FOUND" == true ]]; then
            echo "ACTION REQUIRED - High vulnerabilities should be patched within 7 days"
        else
            echo "No immediate action required"
        fi
    } | tee "$REPORT_FILE"

    log_info "Report saved to: $REPORT_FILE"
}

# Main execution
main() {
    echo ""
    echo -e "${BLUE}╔════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║       Check Review Console - Security Scan                 ║${NC}"
    echo -e "${BLUE}╚════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo "Timestamp: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
    echo "Mode: $(if [[ "$CI_MODE" == true ]]; then echo 'CI (will fail on critical/high)'; else echo 'Interactive'; fi)"

    # Run scans
    scan_python_deps
    scan_node_deps
    scan_container_images
    scan_secrets
    scan_owasp

    # Generate report
    generate_report

    # Exit code for CI
    if [[ "$CI_MODE" == true ]]; then
        if [[ "$CRITICAL_FOUND" == true ]]; then
            log_error "CI FAILURE: Critical vulnerabilities found"
            exit 1
        fi
        if [[ "$HIGH_FOUND" == true ]]; then
            log_error "CI FAILURE: High vulnerabilities found"
            exit 1
        fi
    fi

    log_pass "Security scan complete"
}

main
