#!/bin/bash
#
# Smoke Test Script for Check Review Console Pilot Deployment
#
# This script verifies that the deployment is working correctly by:
# 1. Checking health endpoints
# 2. Testing authentication
# 3. Verifying tenant-scoped endpoints
# 4. Testing security headers
#
# Usage:
#   ./scripts/smoke-test.sh [BASE_URL]
#
# Examples:
#   ./scripts/smoke-test.sh                      # Uses https://localhost
#   ./scripts/smoke-test.sh https://pilot.bank.com
#
# Exit codes:
#   0 - All tests passed
#   1 - One or more tests failed
#

set -e

# Configuration
BASE_URL="${1:-https://localhost}"
CURL_OPTS="-sk --connect-timeout 10 --max-time 30"
PASSED=0
FAILED=0
WARNINGS=0

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Helper functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_pass() {
    echo -e "${GREEN}[PASS]${NC} $1"
    ((PASSED++))
}

log_fail() {
    echo -e "${RED}[FAIL]${NC} $1"
    ((FAILED++))
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
    ((WARNINGS++))
}

log_header() {
    echo ""
    echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
    echo -e "${BLUE}  $1${NC}"
    echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
}

# Test functions
test_http_redirect() {
    log_header "Testing HTTP to HTTPS Redirect"

    HTTP_URL="${BASE_URL/https:/http:}"
    RESPONSE=$(curl $CURL_OPTS -I -o /dev/null -w "%{http_code}" "$HTTP_URL/" 2>/dev/null || echo "000")

    if [[ "$RESPONSE" == "301" ]] || [[ "$RESPONSE" == "302" ]]; then
        log_pass "HTTP redirects to HTTPS (status: $RESPONSE)"
    elif [[ "$RESPONSE" == "200" ]]; then
        log_warn "HTTP returns 200 - HTTPS redirect not enforced"
    else
        log_fail "HTTP redirect test failed (status: $RESPONSE)"
    fi
}

test_nginx_health() {
    log_header "Testing Nginx Health Endpoint"

    HTTP_URL="${BASE_URL/https:/http:}"
    RESPONSE=$(curl $CURL_OPTS "$HTTP_URL/health" 2>/dev/null || echo "")

    if [[ "$RESPONSE" == *"healthy"* ]]; then
        log_pass "Nginx health endpoint responding"
    else
        log_fail "Nginx health endpoint not responding (response: $RESPONSE)"
    fi
}

test_api_health() {
    log_header "Testing API Health Endpoint"

    RESPONSE=$(curl $CURL_OPTS "$BASE_URL/api/v1/health" 2>/dev/null || echo "")

    if [[ "$RESPONSE" == *"status"* ]] || [[ "$RESPONSE" == *"healthy"* ]] || [[ "$RESPONSE" == *"ok"* ]]; then
        log_pass "API health endpoint responding"
        echo "  Response: ${RESPONSE:0:100}..."
    else
        # Try the backend health endpoint directly
        BACKEND_RESPONSE=$(curl $CURL_OPTS "$BASE_URL/health" 2>/dev/null || echo "")
        if [[ "$BACKEND_RESPONSE" == *"status"* ]] || [[ "$BACKEND_RESPONSE" == *"healthy"* ]]; then
            log_pass "Backend health endpoint responding (via /health)"
        else
            log_fail "API health endpoint not responding"
        fi
    fi
}

test_security_headers() {
    log_header "Testing Security Headers"

    HEADERS=$(curl $CURL_OPTS -I "$BASE_URL/" 2>/dev/null || echo "")

    # Check HSTS
    if echo "$HEADERS" | grep -qi "Strict-Transport-Security"; then
        log_pass "HSTS header present"
    else
        log_warn "HSTS header missing"
    fi

    # Check X-Frame-Options
    if echo "$HEADERS" | grep -qi "X-Frame-Options"; then
        log_pass "X-Frame-Options header present"
    else
        log_warn "X-Frame-Options header missing"
    fi

    # Check X-Content-Type-Options
    if echo "$HEADERS" | grep -qi "X-Content-Type-Options"; then
        log_pass "X-Content-Type-Options header present"
    else
        log_warn "X-Content-Type-Options header missing"
    fi

    # Check X-XSS-Protection
    if echo "$HEADERS" | grep -qi "X-XSS-Protection"; then
        log_pass "X-XSS-Protection header present"
    else
        log_warn "X-XSS-Protection header missing"
    fi

    # Check Referrer-Policy
    if echo "$HEADERS" | grep -qi "Referrer-Policy"; then
        log_pass "Referrer-Policy header present"
    else
        log_warn "Referrer-Policy header missing"
    fi
}

test_auth_endpoint() {
    log_header "Testing Authentication Endpoint"

    # Test that auth endpoint exists and rejects invalid credentials
    RESPONSE=$(curl $CURL_OPTS -X POST "$BASE_URL/api/v1/auth/login" \
        -H "Content-Type: application/json" \
        -d '{"username":"test","password":"test"}' \
        -w "\n%{http_code}" 2>/dev/null || echo "000")

    HTTP_CODE=$(echo "$RESPONSE" | tail -1)
    BODY=$(echo "$RESPONSE" | head -n -1)

    if [[ "$HTTP_CODE" == "401" ]] || [[ "$HTTP_CODE" == "422" ]]; then
        log_pass "Auth endpoint responding (rejects invalid creds: $HTTP_CODE)"
    elif [[ "$HTTP_CODE" == "200" ]]; then
        log_fail "Auth endpoint accepted test credentials - security issue!"
    elif [[ "$HTTP_CODE" == "000" ]]; then
        log_fail "Auth endpoint not responding"
    else
        log_warn "Auth endpoint returned unexpected status: $HTTP_CODE"
    fi
}

test_admin_login() {
    log_header "Testing Admin Login (if demo mode enabled)"

    # Try demo admin credentials (only works if DEMO_MODE=true)
    RESPONSE=$(curl $CURL_OPTS -X POST "$BASE_URL/api/v1/auth/login" \
        -H "Content-Type: application/json" \
        -d '{"username":"admin","password":"admin123"}' \
        -w "\n%{http_code}" 2>/dev/null || echo "000")

    HTTP_CODE=$(echo "$RESPONSE" | tail -1)
    BODY=$(echo "$RESPONSE" | head -n -1)

    if [[ "$HTTP_CODE" == "200" ]] && echo "$BODY" | grep -q "access_token"; then
        log_pass "Demo admin login successful"

        # Extract token for further tests
        ACCESS_TOKEN=$(echo "$BODY" | grep -o '"access_token":"[^"]*"' | cut -d'"' -f4)
        export ACCESS_TOKEN

        # Test a protected endpoint
        test_protected_endpoint
    elif [[ "$HTTP_CODE" == "401" ]]; then
        log_info "Demo credentials rejected (demo mode likely disabled)"
    else
        log_info "Admin login test skipped (status: $HTTP_CODE)"
    fi
}

test_protected_endpoint() {
    log_header "Testing Protected Endpoint (with auth)"

    if [[ -z "$ACCESS_TOKEN" ]]; then
        log_info "Skipping - no access token available"
        return
    fi

    # Test checks endpoint (tenant-scoped)
    RESPONSE=$(curl $CURL_OPTS -X GET "$BASE_URL/api/v1/checks" \
        -H "Authorization: Bearer $ACCESS_TOKEN" \
        -H "Content-Type: application/json" \
        -w "\n%{http_code}" 2>/dev/null || echo "000")

    HTTP_CODE=$(echo "$RESPONSE" | tail -1)
    BODY=$(echo "$RESPONSE" | head -n -1)

    if [[ "$HTTP_CODE" == "200" ]]; then
        log_pass "Protected endpoint accessible with valid token"

        # Check if response is tenant-scoped (has items array)
        if echo "$BODY" | grep -q '"items"'; then
            log_pass "Response contains expected tenant-scoped data structure"
        fi
    elif [[ "$HTTP_CODE" == "401" ]]; then
        log_fail "Token rejected by protected endpoint"
    else
        log_warn "Protected endpoint returned: $HTTP_CODE"
    fi
}

test_unauthenticated_access() {
    log_header "Testing Unauthenticated Access Rejection"

    # Test that protected endpoints reject unauthenticated requests
    RESPONSE=$(curl $CURL_OPTS -X GET "$BASE_URL/api/v1/checks" \
        -H "Content-Type: application/json" \
        -w "\n%{http_code}" 2>/dev/null || echo "000")

    HTTP_CODE=$(echo "$RESPONSE" | tail -1)

    if [[ "$HTTP_CODE" == "401" ]] || [[ "$HTTP_CODE" == "403" ]]; then
        log_pass "Protected endpoint rejects unauthenticated requests ($HTTP_CODE)"
    elif [[ "$HTTP_CODE" == "200" ]]; then
        log_fail "Protected endpoint accessible without authentication - security issue!"
    else
        log_warn "Unexpected status for unauthenticated request: $HTTP_CODE"
    fi
}

test_image_endpoint_headers() {
    log_header "Testing Secure Image Endpoint Headers"

    # Test that image endpoint has correct security headers
    HEADERS=$(curl $CURL_OPTS -I "$BASE_URL/api/v1/images/secure/test-token" 2>/dev/null || echo "")

    # We expect 401 or 404, but headers should still be set
    if echo "$HEADERS" | grep -qi "Referrer-Policy.*no-referrer"; then
        log_pass "Image endpoint has Referrer-Policy: no-referrer"
    else
        log_warn "Image endpoint may not have strict Referrer-Policy"
    fi

    if echo "$HEADERS" | grep -qi "Cache-Control.*no-store"; then
        log_pass "Image endpoint has Cache-Control: no-store"
    else
        log_warn "Image endpoint may not have strict Cache-Control"
    fi
}

test_rate_limiting() {
    log_header "Testing Rate Limiting"

    # Send multiple rapid requests to auth endpoint
    BLOCKED=false
    for i in {1..20}; do
        RESPONSE=$(curl $CURL_OPTS -X POST "$BASE_URL/api/v1/auth/login" \
            -H "Content-Type: application/json" \
            -d '{"username":"test","password":"test"}' \
            -w "%{http_code}" -o /dev/null 2>/dev/null || echo "000")

        if [[ "$RESPONSE" == "429" ]]; then
            BLOCKED=true
            break
        fi
    done

    if [[ "$BLOCKED" == true ]]; then
        log_pass "Rate limiting is active (blocked after rapid requests)"
    else
        log_warn "Rate limiting may not be active (no 429 response after 20 requests)"
    fi
}

test_tls_configuration() {
    log_header "Testing TLS Configuration"

    # Check TLS version and cipher
    TLS_INFO=$(curl $CURL_OPTS -v "$BASE_URL/" 2>&1 | grep -E "(SSL connection|TLSv)" || echo "")

    if echo "$TLS_INFO" | grep -qE "TLSv1\.[23]"; then
        log_pass "TLS 1.2 or 1.3 in use"
    elif [[ -z "$TLS_INFO" ]]; then
        log_warn "Could not determine TLS version"
    else
        log_warn "TLS version may be outdated: $TLS_INFO"
    fi
}

# Print summary
print_summary() {
    log_header "Test Summary"

    echo ""
    echo -e "  ${GREEN}Passed:${NC}   $PASSED"
    echo -e "  ${RED}Failed:${NC}   $FAILED"
    echo -e "  ${YELLOW}Warnings:${NC} $WARNINGS"
    echo ""

    if [[ $FAILED -gt 0 ]]; then
        echo -e "${RED}Some tests failed. Please review the output above.${NC}"
        return 1
    elif [[ $WARNINGS -gt 0 ]]; then
        echo -e "${YELLOW}All tests passed with warnings. Review recommended.${NC}"
        return 0
    else
        echo -e "${GREEN}All tests passed!${NC}"
        return 0
    fi
}

# Main execution
main() {
    echo ""
    echo -e "${BLUE}╔═══════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║       Check Review Console - Pilot Smoke Tests                ║${NC}"
    echo -e "${BLUE}╚═══════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo "Target URL: $BASE_URL"
    echo "Timestamp:  $(date)"

    # Run all tests
    test_nginx_health
    test_http_redirect
    test_api_health
    test_security_headers
    test_tls_configuration
    test_auth_endpoint
    test_unauthenticated_access
    test_admin_login
    test_image_endpoint_headers
    test_rate_limiting

    # Print summary and exit
    print_summary
}

# Run main function
main
