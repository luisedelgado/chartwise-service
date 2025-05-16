# 🛡️ ChartWise Incident Response Plan (IRP)

**Last revised:** May 16, 2025  
**Version:** 1.0.1

---

## Purpose

This document outlines how ChartWise identifies, assesses, and responds to potential or actual security incidents that could involve electronic protected health information (ePHI), in compliance with HIPAA’s Security Rule (§164.308(a)(6)).

## Scope

This plan applies to all internal and external systems that process, store, or transmit protected health information (PHI), directly or indirectly.

---

## Business Associate Inventory

### Systems & Vendors That Handle PHI

| System     | Function | BAA Signed |
|------------|----------|------------|
| **AWS** | 1. **FastAPI App (ECS service)**: Receives, processes, encrypts/decrypts PHI. Hosted in a Docker container running on ECS. Neither the decrypted PHI nor the application memory are accessible by ECS.<br><br>Secrets (including encryption keys like `CHARTWISE_PHI_ENCRYPTION_KEY`) are stored using AWS Secrets Manager and injected securely as environment variables. No secrets are committed to the codebase or hard-coded in container images.<br><br>2. **Postgres DB (RDS instance)**: Stores encrypted PHI at rest. | Yes |
| **Pinecone** | Stores embeddings representing PHI, along with encrypted PHI metadata. | Yes |
| **OpenAI** | Summarizes patient sessions and generates insights from PHI. | Yes |
| **Deepgram** | Transcribes audio sessions containing PHI. | Yes |
| **DocuPanda** | Uses OCR to process images containing PHI text. | Yes |

### Supporting Vendors That Do Not Handle PHI

| System     | Function | BAA Signed |
|------------|----------|------------|
| **Resend** | Sends transactional emails. PHI is never included in email bodies. | No |
| **InfluxDB** | Stores app-level metrics (e.g., volume, latency). No PHI captured. | No |

---

## Incident Types

| Incident Type       | Example |
|---------------------|---------|
| Data breach         | Pinecone externally compromised. |
| PHI leakage         | PHI accidentally logged or included in email/web responses. |
| Unauthorized access | Therapist accessing another provider’s patient records. |
| Denial of service   | Intentional disruption of app/server availability. |
| Key compromise      | Environment key `CHARTWISE_PHI_ENCRYPTION_KEY` is exposed. |

---

## Roles & Responsibilities

| Role | Person | Responsibilities |
|------|--------|------------------|
| **Security Lead** | Luis Delgado, ChartWise Cofounder |- Primary responder, coordinates containment, leads postmortems. |
| **Developer(s)** | Luis Delgado (backend), Contractor (frontend) |- Assist in investigation, patching, system validation.<br>Developers do not have direct access to decrypted PHI.<br>- All database access is scoped through RBAC with session-level `app.current_user_id` enforcement. This ensures no user can access another user’s data, whether intentionally or accidentally. |
| **Infra Providers and Third-Party Vendors** | AWS, Pinecone, OpenAI, Deepgram, DocuPanda, InfluxDB | - Support incident reporting and investigation, and infrastructure forensics.<br>- Provide breach notifications in accordance with BAA terms.<br>Supply audit logs or security incident documentation upon request. |

---

## Incident Response Lifecycle

### Detection & Identification

- Encryption/decryption failures automatically fail-safe.
- Audit logs monitored for anomalies (e.g. frequent 403s, odd IPs).
- Contractors operate under RBAC permissions.
- CloudTrail, VPC Flow Logs, and ECS container logs monitored via AWS CloudWatch.
- Alerts triggered on anomaly patterns (e.g., credential use from unexpected geolocation, abnormal DB queries).

### Containment

- Revoke tokens, sessions, or keys.
- Temporarily restrict or lock compromised services.
- Isolate attacker or actor through RBAC/user suspension.

### Eradication & Recovery

- Patch vulnerabilities.
- Rotate keys/secrets (`os.environ`) and regenerate if necessary.
- Restore from backups if corruption/loss occurred.

### Notification

**If PHI was compromised**:

- Notify affected users within 60 days.
- Report to HHS if breach affects 500+ individuals or meets other federal criteria.
- Record incident log internally for 6 years per HIPAA.

**Escalation Criteria**

- The Security Lead determines severity and whether breach notification is necessary.
- Legal counsel is consulted before notifying external regulators or affected users.

### Postmortem

Internal writeup due within 7 days, including:

- Timeline
- Root cause
- Detection
- Resolution
- Recommended changes

Update IRP or SOPs accordingly.

---

## Communication Plan

| Stakeholder         | Communication Method         |
|---------------------|------------------------------|
| Internal Team       | Email or secure messaging    |
| Affected Users      | Email via Resend             |
| Infrastructure Vendors | Support portals & dashboards |
| Regulators (HHS)    | OCR Breach Portal            |

---

## Review & Testing

- Security Lead ensures annual review of this plan.
- Tabletop simulation tests conducted yearly.
- Latest IRP version stored in Git under `compliance/incident-response-plan.md`.

### Tabletop Exercise – Example Run

**Pre-Test Setup**

- Choose scenario: encryption key leak (`CHARTWISE_PHI_ENCRYPTION_KEY`)
- Assign roles:  
  - Security Lead: Luis Delgado  
  - Backend Engineer: Luis Delgado  
  - Frontend Contractor: Observer  
- Distribute IRP copies
- Notify team it's a simulation

**Simulate the Incident**

- Announce mock incident
- Simulate detection (e.g., GitHub secret scan alert)
- Response steps:
  - Contain: revoke key, block old ciphertext
  - Eradicate: rotate key, re-encrypt
  - Recover: test decryption
  - Notify: simulate Resend + HHS contact

**Debrief & Post-Test**

- Timeline, gaps, integrity check
- Simulated breach report filed
- Adjust IRP/tooling if needed
- Schedule next test in 12 months

---

## Breach Report Template

**Summary**
- **Date of Incident**: [Insert]
- **Date Discovered**: [Insert]
- **Reported By**: [Insert Name/Role]
- **Incident Type**: [e.g., Unauthorized Access]
- **Status**: ☐ Open ☐ Contained ☐ Resolved

**Description**
- What happened?  
- How was it detected?  
- Systems involved: [List]

**Impact Assessment**
- Was PHI exposed? ☐ Yes ☐ No  
  - Number of individuals: [#]  
  - PHI types: [e.g., DOB, notes]  
- Was data altered/lost? ☐ Yes ☐ No  
- Was incident contained? ☐ Yes ☐ No

**Actions Taken**
- Containment:  
- Eradication:  
- Recovery:  

**Notifications**
- Users notified? ☐ Yes ☐ No  
  - If yes: [Date/Method]  
- HHS notified? ☐ Yes ☐ No  
- OCR Submission #:  
- Others: [Vendors, Researchers]

**Root Cause**
- Describe what went wrong

**Lessons Learned**
- Fixes applied  
- Long-term improvements

**Sign-Off**
- Name, Role, Date

---

## Data Retention & Backup

### Retention Policy

- PHI retained for at least 6 years
- Data deletion requests honored per HIPAA/contractual terms

### Backup Strategy

- **AWS Postgres (PHI storage):**  
  - Daily, encrypted, retained 7+ days
- **App State:**  
  - Ephemeral Docker images (no PHI)
- **Pinecone, Vendors:**  
  - Backups managed by vendors per BAA

### Secrets Management

- Secrets stored in AWS Secrets Manager with 90-day auto-rotation
- IAM-restricted access, logged via CloudTrail
- Env vars injected at runtime only
- KMS key (`CHARTWISE_PHI_ENCRYPTION_KEY`) used for encryption
  - Auto-rotated every 365 days
  - Strict IAM access controls
  - Decryption works seamlessly post-rotation

### Access & Review

- Only authorized staff can trigger restores
- Backup configuration: reviewed quarterly
- Retention/deletion policies: reviewed annually

---

## Change Log

| Date         | Version | Author        | Description                                                   |
|--------------|---------|---------------|---------------------------------------------------------------|
| Mar 26, 2025 | 1.0.0   | Luis Delgado  | Initial HIPAA-aligned IRP with vendor scope and breach flow.  |
| May 16, 2025 | 1.0.1   | Luis Delgado  | Reflected AWS migration, KMS auto-rotation, detection tooling |


