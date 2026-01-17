# Check Review Console - Acceptance Criteria

This document provides Gherkin-style acceptance criteria for key workflows.

## 1. Authentication

### Login
```gherkin
Feature: User Login

  Scenario: Successful login with valid credentials
    Given I am on the login page
    And I have valid credentials for user "reviewer_demo"
    When I enter username "reviewer_demo" and password "DemoReviewer123!"
    And I click the login button
    Then I should be redirected to the dashboard
    And I should see "Welcome, Demo Reviewer User" in the header
    And an audit log entry should be created with action "LOGIN"
    Verify in logs: POST /api/v1/auth/login returns 200

  Scenario: Failed login with invalid password
    Given I am on the login page
    When I enter username "reviewer_demo" and password "wrongpassword"
    And I click the login button
    Then I should see an error message "Invalid username or password"
    And I should remain on the login page
    And an audit log entry should be created with action "LOGIN_FAILED"
    Verify in logs: POST /api/v1/auth/login returns 401

  Scenario: Account lockout after failed attempts
    Given user "test_user" exists with 4 failed login attempts
    When I enter incorrect password for "test_user"
    Then the account should be locked for 30 minutes
    And I should see "Account locked until [timestamp]"
    And an audit log entry should show "LOGIN_FAILED" and lockout

  Scenario: Rate limiting prevents brute force
    Given I am not authenticated
    When I send 6 login requests within 1 minute from the same IP
    Then the 6th request should return 429 Too Many Requests
    And I should see "Rate limit exceeded"
```

### Session Management
```gherkin
Feature: Session Management

  Scenario: Session expires after inactivity
    Given I am logged in as "reviewer_demo"
    And my session has been inactive for 31 minutes
    When I try to access any protected page
    Then I should be redirected to the login page
    And I should see "Session expired. Please log in again."

  Scenario: Token refresh extends session
    Given I am logged in as "reviewer_demo"
    And my access token expires in 2 minutes
    When I make an API request
    Then my access token should be automatically refreshed
    And I should remain logged in

  Scenario: Password change invalidates all sessions
    Given I am logged in as "reviewer_demo" on two devices
    When I change my password on Device A
    Then I should be logged out on Device A
    And I should be logged out on Device B
    And I should see "Password changed successfully. Please log in again."
    Verify in logs: All sessions for user marked as revoked
```

---

## 2. Check Review Workflow

### Queue Management
```gherkin
Feature: Queue Management

  Scenario: Reviewer views assigned queue
    Given I am logged in as "reviewer_demo"
    And I have permission to view "High Priority" queue
    When I navigate to the Queue page
    Then I should see items assigned to me
    And each item should show: check number, amount, presented date, SLA status
    Verify in API: GET /api/v1/queues returns items with status "NEW" or "IN_REVIEW"

  Scenario: Claim item from queue
    Given I am viewing the "Standard Review" queue
    And there is an unassigned item with ID "check-123"
    When I click "Claim" on that item
    Then the item should be assigned to me
    And the item status should change to "IN_REVIEW"
    And other reviewers should no longer see it in their queue
    Verify in logs: Audit entry with action "CLAIM_ITEM"

  Scenario: SLA warning displayed for items near breach
    Given an item was presented 3.5 hours ago
    And the SLA is 4 hours
    When I view the queue
    Then the item should display an amber SLA warning
    And the remaining time should show "30 minutes"
```

### Check Item Review
```gherkin
Feature: Check Item Review

  Scenario: View check item details
    Given I am logged in as "reviewer_demo"
    And I have claimed item "check-123"
    When I open the item details
    Then I should see the check front image
    And I should see the check back image
    And I should see MICR data (routing, account, check number)
    And I should see payee name and amount
    And I should see account information
    And I should see any AI risk flags
    Verify in logs: Audit entry with action "VIEW_CHECK"

  Scenario: AI risk indicators displayed
    Given item "check-456" has AI flags for "signature_mismatch"
    When I view the item details
    Then I should see a warning badge "Signature Concern"
    And I should see confidence score (e.g., "78% confidence")
    And I should see recommendation "REVIEW_REQUIRED"

  Scenario: Network fraud alert displayed
    Given item "check-789" has a network match alert
    When I view the item details
    Then I should see a red alert banner "Network Alert"
    And I should see severity level and match type
    And the item should be flagged for dual control
```

### Decision Making
```gherkin
Feature: Decision Making

  Scenario: Approve a standard check
    Given I am reviewing item "check-123" with amount $500
    And the item does not require dual control
    When I select decision "Approve"
    And I click "Submit Decision"
    Then the item status should change to "APPROVED"
    And the item should be removed from my queue
    And an audit log entry should record the decision
    Verify in API: POST /api/v1/decisions returns 201 with decision details

  Scenario: Return a check with reason code
    Given I am reviewing item "check-123"
    When I select decision "Return"
    And I select reason code "RET-SIG" (Signature discrepancy)
    And I add note "Signature does not match account records"
    And I click "Submit Decision"
    Then the item status should change to "RETURNED"
    And the reason code should be recorded
    And my note should be saved
    Verify in logs: Decision record includes reason_code and note

  Scenario: Place a hold on a check
    Given I am reviewing item "check-123"
    When I select decision "Hold"
    And I select hold type "Exception Hold"
    And I specify hold duration "7 days"
    And I add note "New account, large deposit - extended hold per policy"
    And I click "Submit Decision"
    Then the item status should change to "HELD"
    And the hold release date should be calculated
    Verify in API: Response includes hold_until date

  Scenario: Escalate a check for management review
    Given I am reviewing item "check-123" with risk level "HIGH"
    And I cannot resolve the issue at my level
    When I select decision "Escalate"
    And I select target queue "Management Review"
    And I add escalation reason
    And I click "Submit Decision"
    Then the item should move to "Management Review" queue
    And item status should be "ESCALATED"
    And my escalation notes should be preserved
```

### Dual Control
```gherkin
Feature: Dual Control

  Scenario: Item triggers dual control requirement
    Given I am reviewing item "check-123" with amount $15,000
    And the dual control threshold is $5,000
    When I select decision "Approve"
    Then I should see "This item requires dual control approval"
    And my decision should be "Pending Approval"
    And the item should appear in the Approver queue

  Scenario: Approver approves dual control item
    Given I am logged in as "approver_demo"
    And item "check-123" has a pending decision from "reviewer_demo"
    When I view the item and reviewer's recommendation
    And I select "Approve" to confirm
    And I click "Submit Approval"
    Then the item status should change to "APPROVED"
    And audit log should show both reviewer and approver
    Verify in logs: Two decision records linked to the same check

  Scenario: Approver rejects dual control item
    Given I am logged in as "approver_demo"
    And item "check-123" has a pending "Approve" from "reviewer_demo"
    When I select "Reject" with reason "Incomplete documentation"
    And I click "Submit"
    Then the item should return to "IN_REVIEW" status
    And the original reviewer should be notified
    And the rejection reason should be recorded
```

### Override AI Recommendation
```gherkin
Feature: Override AI Recommendation

  Scenario: Reviewer cannot override AI without approval
    Given I am logged in as "reviewer_demo"
    And item "check-123" has AI recommendation "RETURN"
    When I attempt to select "Approve"
    Then I should see "Overriding AI requires approver authorization"
    And the decision should require dual control

  Scenario: Approver overrides AI with justification
    Given I am logged in as "approver_demo"
    And item "check-123" has AI recommendation "RETURN"
    When I select decision "Approve"
    Then I should be required to enter override justification
    And I must select an override reason category
    When I enter "Verified with customer, signature is valid"
    And I click "Submit Override"
    Then the item should be approved
    And audit log should record: "AI_OVERRIDE" with justification
```

---

## 3. Fraud Management

### View Fraud Alerts
```gherkin
Feature: Fraud Alerts

  Scenario: View network fraud alert
    Given item "check-123" has a network match alert
    When I view the alert details
    Then I should see: severity level, indicator type, match count
    And I should see when the alert was generated
    And I should NOT see PII from other institutions
    Verify: Indicator hashes are displayed, not raw values

  Scenario: Dismiss false positive alert (Approver only)
    Given I am logged in as "approver_demo"
    And item "check-123" has a fraud alert that is a false positive
    When I click "Dismiss Alert"
    And I enter reason "Verified with customer - legitimate transaction"
    And I click "Confirm Dismiss"
    Then the alert should be marked as dismissed
    And audit log should record who dismissed and why
    Verify: Dismissed alerts don't appear in active alert list
```

### Create Fraud Event
```gherkin
Feature: Fraud Event Reporting

  Scenario: Report confirmed fraud
    Given I am logged in as "admin_demo"
    And I have confirmed fraud on item "check-123"
    When I navigate to Create Fraud Event
    And I select fraud type "Counterfeit Check"
    And I select fraud channel "Mobile RDC"
    And I enter loss amount
    And I click "Submit to Network"
    Then a fraud event should be created
    And indicator hashes should be generated
    And the event should be shared with the network
    Verify in API: POST /api/v1/fraud/events returns 201
    Verify: Indicator hashes use HMAC, not reversible
```

---

## 4. Administration

### User Management
```gherkin
Feature: User Management

  Scenario: Create new user
    Given I am logged in as "admin_demo"
    When I navigate to User Management
    And I click "Add User"
    And I fill in: email, username, full name, department
    And I assign role "Reviewer"
    And I click "Create User"
    Then the user should be created
    And they should receive an email with temporary password
    And audit log should record user creation
    Verify: New user can log in and access reviewer functions

  Scenario: Deactivate user
    Given user "john_doe" is active
    When I click "Deactivate" on the user
    And I confirm the deactivation
    Then the user should be marked as inactive
    And all their active sessions should be revoked
    And they should not be able to log in
    Verify: User record still exists for audit purposes
```

### Policy Management
```gherkin
Feature: Policy Management

  Scenario: Create new policy with rules
    Given I am logged in as "admin_demo"
    When I navigate to Policies
    And I click "Create Policy"
    And I enter name "High Value Consumer Checks"
    And I add rule: "Amount > $10,000 → Require Dual Control"
    And I add rule: "Account tenure < 30 days → Route to New Account Queue"
    And I click "Save Draft"
    Then the policy should be saved as draft
    And it should not be active yet

  Scenario: Activate policy
    Given policy "High Value Consumer Checks" is in draft status
    When I click "Activate"
    And I confirm activation
    Then the policy should become active
    And a new policy version should be created
    And audit log should record the activation
    Verify: New checks matching criteria are affected by rules
```

---

## 5. Audit and Reporting

### Export Audit Packet
```gherkin
Feature: Audit Packet Export

  Scenario: Export complete audit packet
    Given I am logged in as "auditor_demo"
    And I am viewing item "check-123" with complete history
    When I click "Export Audit Packet"
    Then I should receive a PDF document containing:
      | Component | Content |
      | Check images | Front and back images |
      | MICR data | Routing, account, check number |
      | Transaction details | Amount, dates, parties |
      | Decision history | All decisions with timestamps |
      | Reviewer notes | All notes added |
      | AI analysis | Flags, scores, recommendations |
      | Fraud alerts | Any network alerts received |
    And an audit log entry should record the export

  Scenario: Audit log search
    Given I am logged in as "auditor_demo"
    When I navigate to Audit Logs
    And I filter by: date range, user, action type
    And I click "Search"
    Then I should see matching audit entries
    And each entry should show: timestamp, user, action, resource, details
    And I should be able to export results to CSV
```

---

## Verification Checklist

For each scenario, verify:

- [ ] **UI**: Visual elements display correctly
- [ ] **API**: Correct HTTP status codes returned
- [ ] **Database**: Records created/updated correctly
- [ ] **Audit Log**: Appropriate entries created
- [ ] **Permissions**: Unauthorized users blocked
- [ ] **Error Handling**: Meaningful error messages displayed
- [ ] **Edge Cases**: Boundary conditions handled
