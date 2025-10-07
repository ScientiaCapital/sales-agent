# Data Encryption Policy

**Document Version:** 1.0
**Last Updated:** 2025-10-07
**Classification:** Confidential
**SOC 2 Controls:** CC6.1, CC6.7

## Overview

This document outlines the encryption standards and practices implemented in the Sales Agent platform to protect sensitive data at rest and in transit.

## Encryption Standards

### Encryption Algorithms

| Data Type | Algorithm | Key Size | Implementation |
|-----------|-----------|----------|----------------|
| Data at Rest | Fernet (AES-128) | 128-bit | Python cryptography library |
| Passwords | bcrypt | - | pwdlib with cost factor 12 |
| Data in Transit | TLS 1.3 | 256-bit | HTTPS/WSS |
| JWT Tokens | HS256 | 256-bit | PyJWT library |
| Future: Database | AES-256 | 256-bit | PostgreSQL TDE |

## Data at Rest Encryption

### CRM Credentials

All CRM integration credentials are encrypted using Fernet symmetric encryption:

```python
# Implementation in backend/app/services/crm/base.py
class CredentialEncryption:
    def encrypt_credential(self, plaintext: str) -> str:
        """Encrypts sensitive credential data"""

    def decrypt_credential(self, ciphertext: str) -> str:
        """Decrypts credential for use"""
```

**Protected Fields:**
- OAuth access tokens
- OAuth refresh tokens
- API keys
- Client secrets

### Database Encryption

**Current Implementation:**
- Application-level encryption for sensitive fields
- Fernet encryption for credentials
- Bcrypt hashing for passwords

**Planned Enhancements:**
- PostgreSQL Transparent Data Encryption (TDE)
- Encrypted backups
- Key rotation automation

### File Storage

**Sensitive Documents:**
- Encrypted before storage
- AES-256-GCM for file encryption
- Unique key per file
- Key derivation from master key

## Data in Transit Encryption

### HTTPS/TLS Configuration

**Protocol Support:**
- TLS 1.3 (preferred)
- TLS 1.2 (minimum)
- TLS 1.0/1.1 (disabled)

**Cipher Suites:**
```
TLS_AES_256_GCM_SHA384
TLS_CHACHA20_POLY1305_SHA256
TLS_AES_128_GCM_SHA256
ECDHE-RSA-AES256-GCM-SHA384
ECDHE-RSA-AES128-GCM-SHA256
```

**Certificate Management:**
- Valid SSL/TLS certificates required
- Automated renewal via Let's Encrypt
- Certificate pinning for mobile apps
- HSTS header enforcement

### API Communication

All API communications are encrypted:

1. **External APIs:**
   - HTTPS required for all endpoints
   - Certificate validation enforced
   - No fallback to HTTP

2. **Webhooks:**
   - HTTPS endpoints only
   - Signature verification
   - Replay attack prevention

3. **WebSocket Connections:**
   - WSS (WebSocket Secure) only
   - Same TLS configuration as HTTPS

## Key Management

### Master Encryption Key

**Storage:**
- Environment variable: `CRM_ENCRYPTION_KEY`
- Never committed to version control
- Separated from application code
- Backed up securely

**Generation:**
```python
from cryptography.fernet import Fernet
key = Fernet.generate_key()  # Generate new key
```

### JWT Secret Key

**Configuration:**
- Environment variable: `JWT_SECRET_KEY`
- Minimum 256 bits of entropy
- Unique per environment
- Rotated quarterly

### Key Rotation Policy

| Key Type | Rotation Frequency | Process |
|----------|-------------------|---------|
| Master Encryption Key | Annually | Re-encrypt all data |
| JWT Secret | Quarterly | Dual-key transition |
| Database Passwords | Semi-annually | Coordinated update |
| API Keys | Quarterly | Provider-specific |

### Key Rotation Process

1. **Preparation Phase**
   - Generate new key
   - Test in staging environment
   - Backup current encrypted data

2. **Transition Phase**
   - Deploy dual-key support
   - Re-encrypt data gradually
   - Monitor for errors

3. **Completion Phase**
   - Remove old key support
   - Securely destroy old key
   - Update documentation

## Password Security

### Password Hashing

**Algorithm:** bcrypt with pwdlib
**Configuration:**
- Cost factor: 12 (minimum)
- Automatic salt generation
- Timing attack resistant

### Password Requirements

- Minimum 8 characters
- At least one uppercase letter
- At least one lowercase letter
- At least one digit
- No common passwords (checked against list)

### Password Storage

```python
from pwdlib import PasswordHash

password_hash = PasswordHash.recommended()
hashed = password_hash.hash(plain_password)  # Store this
password_hash.verify(plain_password, hashed)  # Verify
```

## Sensitive Data Classification

### Highly Sensitive Data

**Encryption Required:**
- Passwords (hashed)
- API keys
- OAuth tokens
- Credit card data (tokenized)
- Social Security Numbers

### Sensitive Data

**Encryption Recommended:**
- Email addresses
- Phone numbers
- Physical addresses
- Financial data
- Health information

### Internal Data

**Encryption Optional:**
- User preferences
- Application logs
- Analytics data
- Public content

## Compliance Requirements

### GDPR Article 32

- Pseudonymization and encryption implemented
- Confidentiality and integrity ensured
- Regular security testing conducted
- Encryption effectiveness assessed

### PCI DSS (Future)

- Strong cryptography for cardholder data
- Encryption key management procedures
- Annual key rotation
- Split knowledge and dual control

### SOC 2 Type II

- **CC6.1:** Encryption of sensitive data
- **CC6.7:** Restriction of data access
- **CC7.2:** Monitoring of encryption systems

## Implementation Examples

### Encrypting API Keys

```python
def store_api_key(self, provider: str, api_key: str):
    encrypted_key = self.encrypt_credential(api_key)
    credential = CRMCredential(
        provider=provider,
        api_key=encrypted_key
    )
    db.add(credential)
    db.commit()
```

### Decrypting for Use

```python
def get_api_key(self, provider: str) -> str:
    credential = db.query(CRMCredential).filter_by(
        provider=provider
    ).first()
    return self.decrypt_credential(credential.api_key)
```

## Monitoring and Auditing

### Encryption Metrics

- Encryption/decryption operations per hour
- Failed decryption attempts
- Key rotation completion rate
- Certificate expiry warnings

### Audit Events

All encryption operations are logged:
- Key generation
- Encryption/decryption requests
- Key rotation events
- Failed operations
- Certificate updates

## Incident Response

### Compromised Key Response

1. **Immediate Actions**
   - Revoke compromised key
   - Generate new key
   - Deploy emergency update

2. **Assessment**
   - Identify affected data
   - Determine exposure window
   - Assess impact scope

3. **Remediation**
   - Re-encrypt all affected data
   - Notify affected users
   - Update security controls

### Data Breach Protocol

1. Identify encrypted vs. unencrypted data exposed
2. Assess encryption strength
3. Determine if keys were compromised
4. Follow breach notification procedures

## Testing and Validation

### Regular Testing

- Quarterly encryption strength assessment
- Annual penetration testing
- Automated security scanning
- Key rotation drills

### Validation Checks

- Verify all sensitive data encrypted
- Confirm TLS configuration
- Test key rotation procedures
- Validate backup encryption

## Appendix A: Encryption Checklist

- [ ] Environment variables set for keys
- [ ] Fernet encryption configured
- [ ] TLS certificates valid
- [ ] Password hashing implemented
- [ ] Key rotation scheduled
- [ ] Monitoring enabled
- [ ] Audit logging configured

## Appendix B: Emergency Procedures

Steps for emergency key rotation and data re-encryption.

## Appendix C: Tool References

- cryptography library: https://cryptography.io
- pwdlib: https://github.com/liquidprompt/pwdlib
- PyJWT: https://pyjwt.readthedocs.io