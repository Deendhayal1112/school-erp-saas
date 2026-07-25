# Authentication, Authorization & Security Architecture

This document describes the design, flows, and security guidelines of the enterprise-grade Authentication and Authorization modules.

---

## 1. Modular Monolith Architecture

The security module follows Clean Architecture and SOLID design principles, decoupled into four distinct layers:

```
[REST API Layer] (FastAPI Controllers & Routes)
      ↓
[Service Layer] (Business Logic & Workflow Coordinators)
      ↓
[Repository Layer] (SQLAlchemy Database Access Objects)
      ↓
[Model Layer] (Database Entities & Declarative Base)
```

- **Zero DB Logic in Routers**: Every route relies strictly on Service injection.
- **Repository Pattern**: Prevents N+1 database querying issues via joined loading.
- **Dependency Injection**: Enforced across all constructor calls.

---

## 2. Authentication Flow

The system supports username/email authentication with brute-force protection:

1. **Lockout Evaluation**: Checks if the user account is locked (`locked_until`).
2. **Credential Validation**: Verifies hashes using bcrypt.
3. **Failed Tracking**: Increments `failed_login_count` on failure. Reaching 5 attempts triggers a 15-minute temporary lockout.
4. **Token Generation**: Generates short-lived Access Tokens (30m) and long-lived Refresh Tokens (7d).

---

## 3. Stateless Session Revocation (JWT Flow)

To ensure token security without requiring database whitelists:
- Every JWT contains an issued-at (`iat`) claim.
- Changing or resetting a password updates the user's `password_changed_at` timestamp in the database.
- The middleware and authentication dependencies reject any access or refresh token issued before `password_changed_at`.

---

## 4. Graph-Based Role-Based Access Control (RBAC)

Enforces hierarchy-aware permissions matching the tenant structure:
- **Hierarchical Roles**: `SUPER_ADMIN` outranks all roles.
- **Permission Resolution**: Evaluates user role permissions.
- **Performance Caching**: Employs double-layered (Redis + local memory fallback) caching for permission lookups.

---

## 5. Security & OWASP ASVS Compliance

- **Entropy Checks**: Uses Shannon Entropy validation on passwords.
- **Reuse Block**: Saves the last 5 passwords to prevent immediate reuse.
- **SQL Injection**: Complete parameterization via SQLAlchemy ORM.
- **XSS & CSRF**: Rigid security headers (CSP, HSTS, X-Content-Type-Options).
- **Enumeration Defense**: Silent failure response matching for reset and activation queries.
