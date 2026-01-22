# API Documentation

## Overview

The Check Review Console API is a RESTful API built with FastAPI. All endpoints are prefixed with `/api/v1`.

## Authentication

The API uses JWT (JSON Web Token) authentication.

### Login

```http
POST /api/v1/auth/login
Content-Type: application/json

{
  "username": "string",
  "password": "string"
}
```

Response:
```json
{
  "access_token": "string",
  "refresh_token": "string",
  "token_type": "bearer",
  "expires_in": 1800
}
```

### Using Authentication

Include the access token in the Authorization header:

```http
Authorization: Bearer <access_token>
```

### Refresh Token

```http
POST /api/v1/auth/refresh
Content-Type: application/json

{
  "refresh_token": "string"
}
```

## Check Items

### List Check Items

```http
GET /api/v1/checks
```

Query Parameters:
- `page` (int): Page number (default: 1)
- `page_size` (int): Items per page (default: 20, max: 100)
- `status` (array): Filter by status
- `risk_level` (array): Filter by risk level
- `queue_id` (string): Filter by queue
- `assigned_to` (string): Filter by assigned user
- `has_ai_flags` (boolean): Filter items with AI flags
- `sla_breached` (boolean): Filter breached items

Response:
```json
{
  "items": [...],
  "total": 100,
  "page": 1,
  "page_size": 20,
  "total_pages": 5,
  "has_next": true,
  "has_previous": false
}
```

### Get Check Item

```http
GET /api/v1/checks/{item_id}
```

Response includes:
- Check details
- Account context
- AI flags
- Image URLs (signed)

### Get Check History

```http
GET /api/v1/checks/{item_id}/history
```

Returns historical checks for the same account.

### Sync Presented Items

```http
POST /api/v1/checks/sync?amount_min=5000
```

Syncs new presented items from the external system.

## Decisions

### Get Reason Codes

```http
GET /api/v1/decisions/reason-codes
```

Query Parameters:
- `category` (string): Filter by category
- `decision_type` (string): Filter by decision type

### Create Decision

```http
POST /api/v1/decisions
Content-Type: application/json

{
  "check_item_id": "string",
  "decision_type": "review_recommendation",
  "action": "approve",
  "reason_code_ids": ["string"],
  "notes": "string",
  "ai_assisted": false
}
```

Decision Types:
- `review_recommendation`: Initial review
- `approval_decision`: Final approval (dual control)

Actions:
- `approve`: Approve the check
- `return`: Return to drawer
- `reject`: Reject the check
- `hold`: Hold for more information
- `escalate`: Escalate to supervisor
- `needs_more_info`: Request additional information

### Dual Control Approval

```http
POST /api/v1/decisions/dual-control
Content-Type: application/json

{
  "decision_id": "string",
  "approve": true,
  "notes": "string"
}
```

## Queues

### List Queues

```http
GET /api/v1/queues
```

### Get Queue Stats

```http
GET /api/v1/queues/{queue_id}/stats
```

## Reports

### Dashboard Stats

```http
GET /api/v1/reports/dashboard
```

### Throughput Report

```http
GET /api/v1/reports/throughput?days=7
```

### Decision Report

```http
GET /api/v1/reports/decisions?days=30
```

### Reviewer Performance

```http
GET /api/v1/reports/reviewer-performance?days=30
```

## Images

### Secure Image Access

Images are accessed via signed URLs that expire after 60 seconds.

```http
GET /api/v1/images/secure/{token}
```

The token is provided in the check item response.

## Audit

### Get Item Audit Trail

```http
GET /api/v1/audit/items/{item_id}
```

### Generate Audit Packet

```http
POST /api/v1/audit/packet
Content-Type: application/json

{
  "check_item_id": "string",
  "include_images": true,
  "include_history": true,
  "format": "pdf"
}
```

## Error Responses

All errors follow this format:

```json
{
  "error": "error_code",
  "message": "Human readable message",
  "details": {}
}
```

Common HTTP Status Codes:
- `400`: Bad Request
- `401`: Unauthorized
- `403`: Forbidden
- `404`: Not Found
- `422`: Validation Error
- `500`: Internal Server Error

## Rate Limiting

The API implements rate limiting:
- 100 requests per minute per user
- 1000 requests per minute per IP

Rate limit headers are included in responses:
- `X-RateLimit-Limit`
- `X-RateLimit-Remaining`
- `X-RateLimit-Reset`
