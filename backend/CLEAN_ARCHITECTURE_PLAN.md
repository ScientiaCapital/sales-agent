# Clean Architecture Plan

This document defines the target structure and migration steps.

## Target Structure
app/
- domain/
  - entities/
  - value_objects/
  - repositories/
- application/
  - use_cases/
  - services/
  - interfaces/
- infrastructure/
  - database/
  - external_apis/
  - messaging/
- presentation/
  - api/
  - cli/
  - webhooks/

## Migration Steps
1. Extract entities and value objects from models/services into `domain/`.
2. Define repository interfaces in `domain/repositories`.
3. Move DB-specific implementations to `infrastructure/database`.
4. Refactor services into `application/services` and use-cases into `application/use_cases`.
5. Limit `presentation` layer to FastAPI endpoints and DTO mapping.

## Principles
- Dependency Rule: outer layers depend on inner layers only
- Use interfaces for boundaries (repositories/services)
- Keep domain pure (no frameworks)

## Incremental Plan
- Week 1: Define domain types and repo interfaces; adapt one use case (lead qualification)
- Week 2: Migrate CRM sync and enrichment flows
- Week 3: Migrate agents integrations boundaries
