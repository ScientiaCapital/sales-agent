# Access Control Policy

**Document Version:** 1.0
**Last Updated:** 2025-10-07
**Classification:** Internal
**SOC 2 Controls:** CC6.1, CC6.2

## Overview

This document outlines the access control mechanisms implemented in the Sales Agent platform to ensure secure authentication and authorization of users accessing system resources.

## Authentication System

### JWT-Based Authentication

The platform uses JSON Web Tokens (JWT) for stateless authentication:

- **Algorithm:** HS256 (HMAC with SHA-256)
- **Access Token Expiry:** 15 minutes
- **Refresh Token Expiry:** 7 days
- **Token Rotation:** Refresh tokens are rotated on each use

### Password Policy

All user passwords must meet the following requirements:

- Minimum 8 characters
- At least one uppercase letter
- At least one lowercase letter
- At least one digit
- Hashed using bcrypt with automatic salt generation
- Cost factor: 12 (default for pwdlib)

### Account Security

- **Failed Login Attempts:** Account locked after 5 failed attempts
- **Lock Duration:** 30 minutes
- **Session Management:** JWT version tracking for token revocation
- **Multi-Factor Authentication:** Planned for future release

## Authorization System

### Role-Based Access Control (RBAC)

The system implements a hierarchical RBAC model with the following components:

#### System Roles

1. **Admin Role**
   - Full system access
   - User management capabilities
   - System configuration access
   - Audit log access
   - All business data operations

2. **Manager Role**
   - Read/write access to business data
   - Lead management
   - Campaign creation and management
   - CRM synchronization
   - Report generation

3. **User Role**
   - Read-only access to business data
   - View leads and campaigns
   - View reports
   - Limited CRM access

#### Permission Model

Permissions follow the format: `action:resource`

**Lead Permissions:**
- `read:leads` - View lead information
- `write:leads` - Create and update leads
- `delete:leads` - Delete leads

**Campaign Permissions:**
- `read:campaigns` - View campaigns
- `write:campaigns` - Create and update campaigns
- `delete:campaigns` - Delete campaigns

**CRM Permissions:**
- `read:crm` - View CRM data
- `write:crm` - Sync and update CRM data
- `manage:crm` - Manage CRM connections

**Administrative Permissions:**
- `manage:users` - User account management
- `manage:roles` - Role and permission management
- `view:audit` - Access audit logs
- `manage:system` - System administration

### API Endpoint Protection

All sensitive endpoints are protected using dependency injection:

```python
# Example: Campaign creation requires write permission
@router.post("/campaigns", dependencies=[Depends(has_permission("write:campaigns"))])

# Example: User management requires admin role
@router.get("/users", dependencies=[Depends(has_role("admin"))])
```

## Access Control Matrix

| Resource | Admin | Manager | User | Anonymous |
|----------|-------|---------|------|-----------|
| Leads | CRUD | CRUD | R | - |
| Campaigns | CRUD | CRUD | R | - |
| CRM Data | CRUD | RW | R | - |
| Reports | CRUD | RW | R | - |
| Users | CRUD | - | - | - |
| Audit Logs | R | - | - | - |
| System Config | RW | - | - | - |

Legend: C=Create, R=Read, U=Update, D=Delete, W=Write

## User Provisioning Process

1. **Account Creation**
   - Admin creates new user account
   - Default role assigned (typically "user")
   - Temporary password generated
   - Email verification required

2. **Role Assignment**
   - Admin reviews user requirements
   - Appropriate role(s) assigned
   - Permissions automatically inherited from role

3. **Account Activation**
   - User receives activation email
   - Password reset required on first login
   - Profile completion encouraged

## Access Review Process

### Quarterly Reviews

- All user accounts reviewed quarterly
- Inactive accounts (>90 days) flagged for deactivation
- Role appropriateness verified
- Permission usage analyzed

### Audit Trail

All access control events are logged:
- Login attempts (successful and failed)
- Role changes
- Permission grants/revocations
- Account modifications
- Token refresh events

## Incident Response

### Compromised Account

1. Immediate token revocation
2. Password reset forced
3. Account locked pending investigation
4. Audit log review for unauthorized access
5. User notification

### Suspicious Activity

- Automated detection of anomalous patterns
- Real-time alerts for:
  - Multiple failed login attempts
  - Access from unusual locations
  - Privilege escalation attempts
  - Unusual data access patterns

## Compliance Mappings

### SOC 2 Type II Controls

- **CC6.1:** Logical and physical access controls
- **CC6.2:** Prior authorization for system access
- **CC6.3:** Role-based access control implementation
- **CC6.6:** Access removal upon termination

### GDPR Requirements

- User consent tracking
- Data access logging
- Right to access implementation
- Data portability support

## Technical Implementation

### Database Schema

- `users` table: Core user accounts
- `roles` table: Role definitions
- `permissions` table: Granular permissions
- `user_roles` table: User-role associations
- `role_permissions` table: Role-permission mappings

### Security Headers

All API responses include:
- `X-Request-ID`: Request tracing
- `Strict-Transport-Security`: HTTPS enforcement
- `X-Content-Type-Options`: nosniff
- `X-Frame-Options`: DENY

## Monitoring and Alerting

### Key Metrics

- Failed login attempts per user
- Token refresh rate
- Permission denial rate
- Account lockout frequency

### Alert Thresholds

- 5+ failed logins: Account lock
- 10+ permission denials/hour: Security alert
- Unusual token refresh pattern: Investigation trigger

## Appendix A: API Authentication Flow

```
1. User submits credentials → POST /api/v1/auth/login
2. Server validates credentials
3. Server issues JWT tokens
4. Client includes token in Authorization header
5. Server validates token on each request
6. Token refresh before expiry
```

## Appendix B: Emergency Access Procedures

1. Break-glass account available for emergencies
2. Requires dual authorization
3. All actions logged with enhanced detail
4. Automatic review triggered post-use
5. Account disabled after emergency