# Audit Logging Policy

**Document Version:** 1.0
**Last Updated:** 2025-10-07
**Classification:** Internal
**SOC 2 Controls:** CC6.6, CC7.1

## Overview

This document defines the audit logging and monitoring policies for the Sales Agent platform. Comprehensive audit logging ensures accountability, enables incident investigation, and maintains compliance with regulatory requirements.

## Audit Logging Architecture

### Components

1. **Audit Middleware**
   - Captures all API requests automatically
   - Non-blocking background task processing
   - Request ID generation for tracing

2. **Security Event Model**
   - Structured event storage in PostgreSQL
   - JSON metadata for flexible context
   - Indexed for efficient querying

3. **Log Aggregation**
   - Database-backed audit trail
   - Future: Integration with SIEM systems
   - Real-time alerting capabilities

## Event Types Logged

### Authentication Events
- `login_success` - Successful authentication
- `login_failed` - Failed authentication attempts
- `logout` - User logout
- `token_refresh` - JWT token refresh
- `token_revoked` - Token revocation

### Authorization Events
- `access_granted` - Successful resource access
- `access_denied` - Permission denial
- `permission_changed` - Permission modifications
- `role_assigned` - Role assignments
- `role_removed` - Role removals

### Data Operations
- `data_created` - Resource creation
- `data_read` - Resource access
- `data_updated` - Resource modification
- `data_deleted` - Resource deletion
- `data_exported` - Bulk data export

### CRM Integration Events
- `crm_sync` - CRM synchronization
- `crm_auth` - CRM authentication
- `credential_encrypted` - Credential encryption
- `credential_decrypted` - Credential decryption

### GDPR Compliance Events
- `consent_granted` - User consent given
- `consent_revoked` - User consent withdrawn
- `data_export_requested` - GDPR data export
- `data_deletion_requested` - GDPR data deletion

### System Events
- `config_changed` - Configuration changes
- `api_error` - API errors
- `security_alert` - Security incidents

## Data Captured

### For Every Request

```json
{
  "request_id": "uuid-v4",
  "timestamp": "2025-10-07T10:00:00Z",
  "user_id": 123,
  "ip_address": "192.168.1.1",
  "user_agent": "Mozilla/5.0...",
  "request_method": "POST",
  "request_path": "/api/v1/leads",
  "status_code": 201,
  "latency_ms": 45,
  "event_type": "data_created",
  "resource": "lead:456",
  "action": "create"
}
```

### Additional Context

- Request parameters (sanitized)
- Response size
- Error messages (if applicable)
- Business context metadata

## Retention Policy

### Standard Retention

| Event Type | Retention Period | Rationale |
|------------|-----------------|-----------|
| Authentication | 2 years | Security analysis |
| Authorization | 2 years | Access review |
| Data Operations | 1 year | Business audit |
| CRM Events | 1 year | Integration tracking |
| GDPR Events | 7 years | Legal requirement |
| System Events | 6 months | Operational analysis |

### Archive Strategy

1. **Hot Storage** (0-3 months)
   - Active PostgreSQL database
   - Full query capabilities
   - Real-time access

2. **Warm Storage** (3-12 months)
   - Archived tables in PostgreSQL
   - Reduced indexes
   - On-demand access

3. **Cold Storage** (12+ months)
   - Compressed JSON exports
   - Object storage (S3/GCS)
   - Compliance access only

## Security Measures

### Protection of Audit Logs

1. **Tamper Protection**
   - Append-only design
   - No UPDATE operations permitted
   - DELETE restricted to retention policy

2. **Access Control**
   - Read access limited to admin role
   - Write access via system only
   - No direct database modifications

3. **Encryption**
   - At-rest encryption via PostgreSQL
   - In-transit via TLS 1.3
   - Sensitive data redaction

### Data Sanitization

- Passwords never logged
- API keys redacted
- PII minimized
- Credit card data excluded

## Monitoring and Alerting

### Real-Time Alerts

| Condition | Threshold | Action |
|-----------|-----------|--------|
| Failed logins | 5 per user/hour | Account lock |
| Permission denials | 10 per user/hour | Security review |
| Data deletions | 100 per hour | Manual review |
| Configuration changes | Any | Admin notification |
| GDPR requests | Any | Compliance team notification |

### Dashboard Metrics

1. **Security Overview**
   - Failed authentication rate
   - Active sessions count
   - Permission denial trends
   - Suspicious activity score

2. **Compliance Metrics**
   - GDPR request processing time
   - Consent tracking coverage
   - Data retention compliance
   - Audit log integrity

## Query Examples

### Failed Login Investigation

```sql
SELECT
    timestamp,
    ip_address,
    metadata->>'username' as username
FROM security_events
WHERE
    event_type = 'login_failed'
    AND timestamp > NOW() - INTERVAL '24 hours'
ORDER BY timestamp DESC;
```

### User Activity Audit

```sql
SELECT
    event_type,
    resource,
    action,
    timestamp
FROM security_events
WHERE
    user_id = :user_id
    AND timestamp BETWEEN :start_date AND :end_date
ORDER BY timestamp DESC;
```

### Permission Denial Analysis

```sql
SELECT
    user_id,
    resource,
    COUNT(*) as denial_count
FROM security_events
WHERE
    event_type = 'access_denied'
    AND timestamp > NOW() - INTERVAL '7 days'
GROUP BY user_id, resource
HAVING COUNT(*) > 5;
```

## Compliance Reporting

### SOC 2 Type II Requirements

- **CC6.6:** Logical access security events logged
- **CC7.1:** System monitoring implemented
- **CC7.2:** Security incidents detected and reported
- **CC7.3:** Anomalies evaluated and resolved

### GDPR Article 32 Requirements

- Processing activity records maintained
- Security breach detection capability
- Data access tracking implemented
- Consent management audited

## Incident Response Integration

### Log Analysis Workflow

1. **Detection Phase**
   - Automated alert triggered
   - Initial log review
   - Scope assessment

2. **Investigation Phase**
   - Request ID tracing
   - User activity timeline
   - Impact analysis

3. **Response Phase**
   - Containment actions logged
   - Remediation steps documented
   - Lessons learned captured

### Evidence Preservation

- Logs exported for investigation
- Chain of custody maintained
- Cryptographic checksums generated
- Legal hold capabilities

## Performance Considerations

### Optimization Strategies

1. **Asynchronous Logging**
   - Background task processing
   - Non-blocking middleware
   - Queue-based writing

2. **Database Optimization**
   - Partitioned tables by month
   - Selective indexing
   - Automatic vacuum schedule

3. **Query Performance**
   - Materialized views for dashboards
   - Pre-aggregated metrics
   - Caching layer for reports

## Integration Points

### Future Integrations

1. **SIEM Integration**
   - Splunk connector
   - ELK stack support
   - Datadog APM

2. **Compliance Tools**
   - GRC platform integration
   - Automated compliance reporting
   - Risk scoring systems

## Appendix A: Event Type Reference

Complete enumeration of all security event types and their triggers.

## Appendix B: Retention Automation

Scripts and procedures for automated log rotation and archival.

## Appendix C: Recovery Procedures

Steps to restore audit logs from backups in case of data loss.