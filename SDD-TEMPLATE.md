# System Design Document (SDD) Template

Use this template for every project task to define architecture before coding.

## Project Overview
- **Project Name:** [Name]
- **Version:** [Version]
- **Author:** [Team/Person]
- **Date:** [Date]
- **Status:** [Draft/Review/Approved]

---

## 1. Purpose & Goals
- **Business Goal:** What problem does this solve?
- **Success Criteria:** How do we measure success?
- **Out of Scope:** What's explicitly excluded?

---

## 2. Domain Model
### 2.1 Core Entities & Aggregates
```
Entity: [Name]
  - ID: [Type]
  - Fields: [List]
  - Invariants: [Rules]
```

### 2.2 Bounded Contexts (for microservices)
```
Context: [Name]
  - Entities: [List]
  - Commands: [Actions]
  - Events: [Published events]
  - External Dependencies: [Other contexts]
```

---

## 3. System Architecture
### 3.1 High-Level Design
```
[ASCII diagram or description of layers/components]
- Presentation Layer
- Application/API Layer
- Domain/Business Logic Layer
- Infrastructure/Data Layer
```

### 3.2 Technology Stack
- **Language:** [e.g., Python, Go]
- **Framework:** [e.g., FastAPI, Gin]
- **Database:** [e.g., PostgreSQL, MongoDB]
- **Message Queue:** [e.g., Kafka, RabbitMQ]
- **Deployment:** [e.g., Docker, K8s]

---

## 4. API Specification
### 4.1 REST Endpoints (if applicable)
```
GET    /api/v1/[resource]/{id}     - Get single resource
GET    /api/v1/[resource]          - List resources
POST   /api/v1/[resource]          - Create resource
PUT    /api/v1/[resource]/{id}     - Update resource
DELETE /api/v1/[resource]/{id}     - Delete resource
```

### 4.2 Request/Response Models
```protobuf
message [ResourceRequest] {
  string id = 1;
  string name = 2;
  // ... other fields
}

message [ResourceResponse] {
  string id = 1;
  string name = 2;
  string created_at = 3;
}
```

### 4.3 Error Handling
- **400:** Bad Request (validation errors)
- **401:** Unauthorized
- **403:** Forbidden
- **404:** Not Found
- **500:** Internal Server Error

---

## 5. Data Models & Schemas
### 5.1 Database Schema
```sql
CREATE TABLE [table_name] (
  id UUID PRIMARY KEY,
  name VARCHAR(255) NOT NULL,
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW()
);
```

### 5.2 Data Relationships
- [Entity1] → [Entity2] (One-to-Many, Foreign Key)
- [Entity2] → [Entity3] (Many-to-Many, Junction Table)

---

## 6. Workflows & Interactions
### 6.1 Happy Path Flows
**Flow: [Name]**
1. User initiates action
2. System validates input
3. System processes request
4. System returns result
5. System publishes event (if async)

### 6.2 Error Scenarios
**Scenario: [Error Case]**
- Trigger: [What causes this]
- Recovery: [How to handle]

---

## 7. Non-Functional Requirements
- **Performance:** [e.g., <200ms response time]
- **Scalability:** [e.g., 10k req/sec]
- **Availability:** [e.g., 99.9%]
- **Security:** [e.g., OAuth2, TLS]
- **Logging:** [Structured JSON, OpenTelemetry]
- **Monitoring:** [Prometheus metrics, health checks]

---

## 8. Dependency & Integration Points
- **Internal Calls:** Service A → Service B (HTTP/gRPC)
- **External APIs:** [List with version]
- **Async Events:** Published/Consumed via [Kafka/RabbitMQ]
- **Database:** [Connection pooling, migrations]

---

## 9. Deployment & Infrastructure
- **Docker Image:** [Base image, ports]
- **Kubernetes:** [Deployment manifest, HPA rules]
- **Environment Variables:** [Required configs]
- **Database Migrations:** [Strategy]
- **Rollback Plan:** [How to revert changes]

---

## 10. Testing Strategy
### 10.1 Test Types & Coverage
- **Unit Tests:** [Coverage >80%]
- **Integration Tests:** [Database, external services]
- **E2E Tests:** [User workflows]
- **Load Tests:** [Performance baselines]

### 10.2 Test Scenarios
1. Happy Path: [Scenario description]
2. Edge Case: [Scenario description]
3. Error Handling: [Scenario description]

---

## 11. Security Considerations
- **Authentication:** [Method]
- **Authorization:** [RBAC/ABAC]
- **Input Validation:** [Rules]
- **Data Encryption:** [At-rest, in-transit]
- **Secret Management:** [Vault, env vars]
- **Audit Logging:** [What to log]

---

## 12. Known Constraints & Decisions
- **Decision:** [What & Why]
- **Alternative:** [What was considered]
- **Trade-off:** [Cost vs benefit]
- **Constraint:** [System limitation]

---

## 13. Appendix: References & Examples
- Link to OpenAPI spec: [URL]
- Link to database schema: [URL]
- Example requests/responses: [Code snippets]
- Architecture diagram: [Link]

---

## Sign-Off
- **Reviewed By:** [Names]
- **Approved On:** [Date]
- **Next Review:** [Date]
