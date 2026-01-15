# Check Review Console - Definitions

This document defines key banking and application terms used throughout the Check Review Console.

## Check Processing Terms

### On-Us Check
A check drawn on the same bank where it is being deposited. The bank is both the paying bank and the collecting bank. These checks can be processed immediately without going through the Federal Reserve or correspondent banks.

### Transit Check
A check drawn on a different bank than where it is being deposited. These checks must be routed through the banking system (Federal Reserve or correspondent banks) for collection. Also called "foreign checks" or "clearing items."

### Presented Date
The date a check was submitted for deposit or cashing. This is when the item enters the bank's processing queue.

### Posted Date
The date a check was officially credited to or debited from an account. May differ from presented date due to holds or processing delays.

## Workflow Terms

### Dual Control
A security requirement where two authorized individuals must independently approve a transaction. Used for high-value checks, high-risk items, or checks flagged by fraud detection. The first reviewer makes a recommendation, and a second approver confirms or rejects.

**Triggers:**
- Amount exceeds threshold (configurable, e.g., $5,000+)
- Check flagged as high-risk by AI
- Network fraud alerts present
- New account with large deposit
- Policy rule requirement

### Hold
A temporary delay placed on funds availability. The check amount is not available for withdrawal until the hold period expires or is manually released. Holds protect the bank from losses if a check is returned.

**Hold Types:**
- **Standard Hold**: Reg CC defined hold periods based on check type
- **Exception Hold**: Extended hold for new accounts, large amounts, or re-deposited items
- **Case-by-Case Hold**: Manual hold placed by reviewer for specific concerns

### Release
The action of making held funds available before the standard hold period expires. Requires appropriate authorization and may require dual control for large amounts.

### SLA (Service Level Agreement)
The expected time to complete check review from presentation. Measured in hours from when an item enters a queue until a decision is made.

**Example SLAs:**
- High Priority: 2 hours
- Standard: 4 hours
- Large Dollar: 6 hours (due to additional review requirements)

## Decision Terms

### Reason Code
A standardized code explaining why a check was approved, returned, or held. Used for audit trails and reporting.

**Categories:**
- **Approval Codes (APR-)**: Approved with specific conditions or notes
- **Return Codes (RET-)**: Check rejected and returned to depositor
- **Hold Codes (HLD-)**: Funds placed on hold pending further verification
- **Escalation Codes (ESC-)**: Item escalated for management review

### Decision Types
- **APPROVE**: Check accepted, funds will be made available
- **RETURN**: Check rejected, returned to depositor with reason code
- **HOLD**: Check accepted but funds held for specified period
- **ESCALATE**: Item requires additional review by senior staff

### Override
When a reviewer makes a decision that differs from an AI recommendation or standard policy. All overrides require documented justification and may trigger dual control.

## Image and Document Terms

### Check Image
Digital image of the physical check, captured during deposit. Includes front (MICR line, payee, amount) and back (endorsements).

### Image Archive
Long-term storage system for check images. Images are retained per regulatory requirements (typically 7 years minimum).

### Audit Packet
A comprehensive record of a check transaction including:
- Check images (front and back)
- MICR data
- Decision history with timestamps
- Reviewer notes and reason codes
- AI analysis results
- Any associated fraud alerts

Used for regulatory examination, dispute resolution, and internal audit.

### Image Source
Where the check image originated:
- **Core System**: Bank's primary processing system
- **Image Archive**: Historical image retrieval system
- **RDC (Remote Deposit Capture)**: Mobile or scanner deposit
- **ATM**: Automated teller machine deposit
- **Branch Scanner**: In-branch capture device

## Fraud and Risk Terms

### Risk Level
Assessment of potential fraud or loss risk:
- **Low**: Standard processing, no unusual indicators
- **Medium**: Some risk factors present, requires careful review
- **High**: Multiple risk factors, may require dual control
- **Critical**: Immediate attention required, possible fraud

### Network Alert
Notification from the inter-bank fraud sharing network that this check or related indicators have been flagged by another institution. Alerts include severity and indicator type.

### Indicator Hash
Privacy-preserving hash of sensitive data (routing numbers, account numbers, payee names) used to match fraud patterns across institutions without exposing actual PII.

### Fraud Event
A confirmed or suspected fraud case documented for network sharing and internal tracking. Includes fraud type classification and contributing indicators.

## Account Terms

### Account Type
- **Consumer**: Personal/individual account
- **Business**: Small business account
- **Commercial**: Large business/corporate account

### Account Tenure
How long the account has been open. New accounts (< 90 days) often receive additional scrutiny for large deposits.

### Account Standing
Current status of the account:
- **Good Standing**: No issues, normal processing
- **Watch List**: Account flagged for additional monitoring
- **Restricted**: Limited transaction capabilities

## Technical Terms

### MICR (Magnetic Ink Character Recognition)
The machine-readable line at the bottom of checks containing:
- Routing number (9 digits)
- Account number
- Check number
- Amount (added during processing)

### Image Connector
Secure connection between the SaaS platform and the bank's on-premise image archive. Uses JWT authentication and RSA encryption.

### Tenant
A bank or credit union instance in the multi-tenant SaaS platform. Each tenant has isolated data and configurable policies.
