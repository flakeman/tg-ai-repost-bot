# 🔐 AI Security & InfoSec Rules: 10 Essential Guidelines

Comprehensive security rules for developers and AI agents covering secure development, secrets management, compliance, threat modeling, and incident response.

> **Related:** See [AI RULES.md](./AI-RULES.md) for complementary coding best practices. Security rules should be integrated with coding standards for comprehensive development governance.

## 🔐 Rule 1: Secrets Management & Vault Integration

**Objective:** Never hardcode credentials; all secrets encrypted and versioned.

**Steps:**
1. Use secret vault (HashiCorp Vault, AWS Secrets Manager, Azure Key Vault)
2. Generate secrets with rotation policy (90 days default)
3. Audit all secret access (logs with timestamp, user, resource)
4. Implement secret scanning in CI/CD (TruffleHog, GitGuardian)

**Success Criteria:** Zero hardcoded secrets in code, 100% vault coverage, audit logs enabled

**Cross-reference:** Complements [AI RULES Rule 1 (Planning)](./AI-RULES.md#rule-1-project-planning--requirements-analysis) - secrets must be managed during planning phase.

**AI Prompt:**
```
Проверь код на секреты и credentials:
- Зашифруй в vault (Vault/Secrets Manager)
- Добавь rotation policy
- Логируй доступ к секретам
- Интегрируй secret scanning в CI/CD
```

## 🛡️ Rule 2: Input Validation & Injection Prevention

**Objective:** Prevent injection attacks (SQL, XSS, Command, LDAP).

**Steps:**
1. Whitelist valid inputs (regex patterns, length, type)
2. Use parameterized queries for databases
3. Sanitize all user input (escaping, encoding)
4. Test with OWASP Top 10 payloads

**Success Criteria:** No SQL/XSS injections in tests, input validation coverage 100%

**Cross-reference:** Integrates with [AI RULES Rule 6 (Testing)](./AI-RULES.md#rule-6-security-testing--quality-assurance) - security testing includes injection attack validation.

**AI Prompt:**
```
Валидируй все входные данные:
- Whitelist для [field]
- Параметризованные запросы БД
- Sanitize input (escaping/encoding)
- Тесты на OWASP Top 10 payloads
```

## 🔑 Rule 3: Authentication & Authorization (AuthN/AuthZ)

**Objective:** Secure identity and access control.

**Steps:**
1. Use OAuth2/OpenID Connect (не Basic Auth)
2. Implement MFA (multi-factor) для critical accounts
3. RBAC (Role-Based Access Control) с least privilege principle
4. Token expiry: short-lived (15 min), refresh tokens (7 days)

**Success Criteria:** OAuth2 configured, MFA enabled, RBAC tested, token rotation working

**AI Prompt:**
```
Настрой аутентификацию и авторизацию:
- OAuth2/OpenID Connect
- MFA для critical users
- RBAC с least privilege
- Token TTL: 15 min (access), 7 days (refresh)
- Логируй все attempts (успешные + failed)
```

## 🔒 Rule 4: Encryption: At-Rest & In-Transit

**Objective:** Protect data confidentiality.

**Steps:**
1. At-Rest: AES-256 with key derivation (PBKDF2/Argon2)
2. In-Transit: TLS 1.3+, HTTPS only, HSTS header
3. Database encryption: transparent (PostgreSQL/MySQL native, AWS RDS)
4. Certificate pinning for mobile APIs

**Success Criteria:** All sensitive data encrypted, TLS 1.3+ only, HSTS headers set

**AI Prompt:**
```
Реализуй шифрование:
- At-rest: AES-256 + PBKDF2/Argon2
- In-transit: TLS 1.3+, HTTPS only
- DB encryption (native or transparent)
- HSTS header: max-age=31536000
- Тесты: decrypt с неверным ключом = failure
```

## 🔍 Rule 5: Logging & Audit Trails

**Objective:** Detect and respond to security incidents.

**Steps:**
1. Log all security events (auth attempts, data access, changes)
2. Structured logging (JSON) with correlation IDs
3. Centralized logging (ELK, Splunk, CloudWatch)
4. Log retention: 90 days min, 1 year for critical events
5. Never log: passwords, API keys, PII in plaintext

**Success Criteria:** Audit logs enabled, structured format, centralized, retention policy enforced

**Cross-reference:** Aligns with [AI RULES Rule 5 (Code Quality & Documentation)](./AI-RULES.md#rule-5-code-quality--documentation) - logging is part of code quality standards.

**AI Prompt:**
```
Настрой логирование:
- Все events: auth, data access, changes
- JSON структурированное + correlation ID
- Centralized logging (ELK/Splunk)
- Retention: 90 дней (standard), 1 год (critical)
- ЗАПРЕТ: passwords, keys, PII в plaintext
```

## 📋 Rule 6: Compliance & Data Protection (GDPR/SOC2/PCI-DSS)

**Objective:** Meet regulatory requirements.

**Steps:**
1. GDPR: right to be forgotten, data portability, consent management
2. SOC2: access controls, incident response, change management
3. PCI-DSS (if payments): tokenization, no cardholder storage
4. Privacy Policy & Terms reviewed by legal
5. DPA (Data Processing Agreement) with vendors

**Success Criteria:** GDPR/SOC2/PCI controls implemented, privacy doc current, audit-ready

**AI Prompt:**
```
Обеспечь compliance:
- GDPR: right-to-forget, data portability, consent
- SOC2: access controls, incident response, change mgmt
- PCI-DSS (if payments): tokenization, no raw cardholder data
- Privacy Policy + Terms reviewed by legal
- DPA with all vendors
```

## 🎯 Rule 7: Threat Modeling & Secure Design

**Objective:** Identify and mitigate security threats proactively.

**Steps:**
1. STRIDE analysis: Spoofing, Tampering, Repudiation, Information Disclosure, Denial of Service, Elevation of Privilege
2. Data Flow Diagram (DFD): components, trust boundaries, data flows
3. For each threat: likelihood (high/med/low) + impact + mitigation
4. Attack surface reduction: minimize external interfaces

**Success Criteria:** STRIDE analysis documented, mitigations implemented, threat model reviewed annually

**Cross-reference:** Complements [AI RULES Rule 2 (Software Design Document - SDD)](./AI-RULES.md#rule-2-software-design-document-sdd) - threat modeling is part of secure design phase.

**AI Prompt:**
```
Проведи threat modeling (STRIDE):
- Spoofing: [mitigation]
- Tampering: [mitigation]
- Repudiation: [mitigation]
- Information Disclosure: [mitigation]
- Denial of Service: [mitigation]
- Elevation of Privilege: [mitigation]
Документируй в THREAT-MODEL.md
```

## 🧪 Rule 8: Security Testing & Vulnerability Scanning

**Objective:** Detect and fix vulnerabilities before production.

**Steps:**
1. SAST (Static Application Security Testing): SonarQube, Snyk
2. DAST (Dynamic Application Security Testing): OWASP ZAP, Burp
3. Dependency scanning: npm audit, pip check, Dependabot
4. Penetration testing: quarterly, by certified firm
5. Fix critical/high within 7 days, medium within 30 days

**Success Criteria:** CI/CD scans pass, zero critical vulnerabilities, pen test report reviewed

**Cross-reference:** Essential component of [AI RULES Rule 6 (Testing)](./AI-RULES.md#rule-6-security-testing--quality-assurance) - security testing is mandatory in QA phase.

**AI Prompt:**
```
Интегрируй security testing:
- SAST: SonarQube/Snyk в CI/CD
- DAST: OWASP ZAP для API endpoints
- Dependency scanning: npm audit / pip check / Dependabot
- CWE top 25 coverage: 100%
- Fixing SLA: critical 7 дней, medium 30 дней
```

## 🚨 Rule 9: Incident Response & Breach Notification

**Objective:** Detect, contain, eradicate, and recover from security incidents.

**Steps:**
1. Incident Response Plan: roles, communication channels, escalation
2. Detection: SIEM alerts (threshold-based), anomaly detection
3. Containment: isolate affected systems, preserve evidence
4. Notification: GDPR (72 hours), notify affected users
5. Post-incident: root cause analysis, preventive measures

**Success Criteria:** IRP documented, SIEM configured, drills conducted quarterly, breach notification compliant

**AI Prompt:**
```
Подготовь Incident Response Plan (IRP):
- Roles: CISO, Security Lead, Engineering Lead
- Detection: SIEM alerts + threshold-based
- Escalation: критический → CTO → CEO
- Notification: GDPR 72-часовой срок
- Post-incident: RCA + preventive actions
- Quarterly drills (tabletop exercises)
```

## 🔐 Rule 10: Dependency & Supply Chain Security

**Objective:** Prevent attacks through compromised dependencies.

**Steps:**
1. Software Bill of Materials (SBOM): track all dependencies + versions
2. Verify package signatures (npm packages, pip, Docker images)
3. Private registry (Artifactory, Nexus) for internal packages
4. Pin dependency versions, automate updates with Renovate/Dependabot
5. Monitor for CVEs: Snyk, WhiteSource, Sonatype

**Success Criteria:** SBOM generated, packages verified, private registry in use, CVE monitoring active

**Cross-reference:** Related to [AI RULES Rule 3 (Development Environment & Tools Setup)](./AI-RULES.md#rule-3-development-environment--tools-setup) - dependency management tools should be configured in dev environment.

**AI Prompt:**
```
Обеспечь supply chain security:
- SBOM: generate и track в каждом release
- Package verification: GPG signatures, checksums
- Private registry: Artifactory/Nexus для internal packages
- Pin versions + automate updates (Renovate)
- CVE monitoring: Snyk/WhiteSource notifications
- Quarterly audit всех dependencies
```

---

## 📊 Implementation Matrix

| Rule | Priority | Effort | Tools |
|------|----------|--------|-------|
| 1: Secrets | CRITICAL | High | Vault, AWS Secrets Manager, GitGuardian |
| 2: Input Validation | CRITICAL | Medium | OWASP, regex, parameterized queries |
| 3: AuthN/AuthZ | CRITICAL | High | OAuth2, MFA, RBAC |
| 4: Encryption | CRITICAL | Medium | TLS 1.3, AES-256, AWS KMS |
| 5: Logging | HIGH | Medium | ELK, Splunk, CloudWatch |
| 6: Compliance | HIGH | High | Legal review, audit tools |
| 7: Threat Modeling | HIGH | Medium | STRIDE, DFD tools (Miro, Lucidchart) |
| 8: Security Testing | HIGH | High | SonarQube, OWASP ZAP, Snyk |
| 9: Incident Response | HIGH | Medium | SIEM, Slack, runbook |
| 10: Supply Chain | MEDIUM | Medium | SBOM, Snyk, Dependabot |

## 🛠️ Quick Implementation Checklist

- [ ] Rule 1: Vault integrated, secrets migrated, rotation enabled
- [ ] Rule 2: Input validation for all endpoints, injection tests pass
- [ ] Rule 3: OAuth2 implemented, MFA enabled, RBAC tested
- [ ] Rule 4: TLS 1.3+, AES-256, HSTS headers, encryption tests
- [ ] Rule 5: Structured logging, centralized log aggregation, 90-day retention
- [ ] Rule 6: GDPR/SOC2 controls implemented, legal review done
- [ ] Rule 7: STRIDE analysis documented, threat model reviewed
- [ ] Rule 8: SAST/DAST in CI/CD, penetration test scheduled, CVE coverage
- [ ] Rule 9: IRP documented, SIEM configured, incident drill done
- [ ] Rule 10: SBOM generated, dependencies verified, supply chain audit done

## 📄 References

- OWASP Top 10: https://owasp.org/www-project-top-ten/
- NIST Cybersecurity Framework: https://www.nist.gov/cyberframework
- CWE Top 25: https://cwe.mitre.org/top25/
- SANS Top 25: https://www.sans.org/top25-software-errors/
- OWASP SAMM (Security Maturity Model): https://owasp.org/www-project-samm/

---

Made with 🔐 for secure development | Feb 2026
