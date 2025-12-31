# Development Guidelines & Best Practices

## Core Principles

### General Coding Style

- **KISS (Keep It Simple, Stupid)**: Prefer simple, straightforward solutions over complex ones
- **YAGNI (You Aren't Gonna Need It)**: Don't build features until they're actually needed
- **DRY (Don't Repeat Yourself)**: Extract common logic into reusable functions/components
- **SRP (Single Responsibility Principle)**: Each function, class, or module should have one clear purpose
- **Separation of Concerns**: Keep business logic, data access, and presentation layers distinct
- **Type Safety**: Always use proper type annotations and avoid `any` types

### Code Organization

- **Folder-based structure**: Organize code by feature/domain, not by technical layer
- **Avoid over-engineering**: Start simple, iterate based on actual needs
- **Context awareness**: Always review existing code patterns before implementing new features

---

## Backend Guidelines (FastAPI)

### Architecture Patterns

#### Repository Pattern

- Use repositories to abstract data access logic
- Keep business logic separate from database operations
- Example structure:
  ```
  app/
    repositories/
      user_repository.py
      game_repository.py
    services/
      user_service.py
      game_service.py
    models/
      user.py
      game.py
    schemas/
      user_schema.py
      game_schema.py
  ```

#### Models (SQLAlchemy)

- Define database models using SQLAlchemy ORM
- Use proper relationships and constraints
- Keep models focused on data structure only

#### Schemas (Pydantic)

- Use Pydantic schemas for request/response validation
- Separate schemas for:
  - Request validation (input)
  - Response serialization (output)
  - Internal operations (if needed)
- Leverage Pydantic's validation features

### FastAPI Conventions

- Use dependency injection for shared resources (DB sessions, services)
- Leverage FastAPI's automatic OpenAPI documentation
- Use proper HTTP status codes
- Implement proper request/response models
- Use async/await for I/O operations

### Error Handling

**MUST:**

- Avoid nested try-catch blocks
- Use specific error types, not generic exceptions
- Return proper HTTP status codes (400, 401, 403, 404, 422, 500, etc.)
- Provide meaningful error messages to the frontend
- Include error codes for frontend handling

**Error Response Format:**

```python
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid input provided",
    "details": {
      "field": "email",
      "reason": "Invalid email format"
    }
  }
}
```

**Early Escape Pattern:**

- Check for nulls, invalid inputs, and edge cases at the beginning of functions
- Return early instead of nesting if-else blocks
- Example:

  ```python
  def process_user(user_id: int) -> User:
      if not user_id:
          raise ValueError("User ID is required")

      user = get_user(user_id)
      if not user:
          raise NotFoundError(f"User {user_id} not found")

      if not user.is_active:
          raise InactiveUserError(f"User {user_id} is inactive")

      # Main logic here
      return process(user)
  ```

### Logging

**MUST:**

- Create an environment-based logging utility
- Use appropriate log levels (DEBUG, INFO, WARNING, ERROR, CRITICAL)
- Include context in log messages (user_id, request_id, etc.)
- Log errors with stack traces
- Configure logging based on environment (development, staging, production)

**Example Structure:**

```python
# lib/logging.py
import logging
import os
from logging.handlers import RotatingFileHandler

def setup_logging():
    log_level = os.getenv("LOG_LEVEL", "INFO")
    logging.basicConfig(
        level=getattr(logging, log_level),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            RotatingFileHandler('app.log', maxBytes=10485760, backupCount=5),
            logging.StreamHandler()
        ]
    )
    return logging.getLogger(__name__)
```

### Database Migrations

**MUST:**

- Use Alembic for all database migrations
- Generate migrations using `alembic --autogenerate`
- Never create migration files manually
- Review generated migrations before applying
- Test migrations on development/staging before production

**Migration Workflow:**

```bash
# 1. Make model changes
# 2. Generate migration
alembic revision --autogenerate -m "description of changes"

# 3. Review generated migration file
# 4. Apply migration
alembic upgrade head
```

### API Design

- Use RESTful conventions for endpoints
- Implement proper pagination for list endpoints
- Use query parameters for filtering and sorting
- Return consistent response formats
- Document APIs using FastAPI's automatic docs

---

## Frontend Guidelines

### SOLID Principles

- **Single Responsibility**: Each component should do one thing well
- **Open/Closed**: Components should be open for extension, closed for modification
- **Liskov Substitution**: Components should be substitutable with their base types
- **Interface Segregation**: Don't force components to depend on interfaces they don't use
- **Dependency Inversion**: Depend on abstractions, not concrete implementations

### Folder Structure

```
components/
  shared/              # Shared components across routes
    Button/
      Button.tsx
      Button.test.tsx
    Modal/
      Modal.tsx

  {{route}}/           # Route-specific components
    index.tsx          # Main UI/logic for the route
    page.tsx           # Minimal, used for data-fetching
    types.ts           # Route-specific types
    constants.ts       # Route-specific constants
    utils.ts           # Route-specific utilities
    sub-feature/       # Sub-folders for complex features
      Component.tsx
      hooks.ts

hooks/                 # Global custom hooks
  useAuth.ts
  useGameState.ts

types.ts               # Global types
constants.ts           # Global constants
utils.ts               # Global utilities
```

### Component Organization

**Route Structure:**

- Each route has its own folder in `/components/{{route}}`
- `page.tsx`: Minimal component, primarily for data-fetching
- `index.tsx`: Main UI/logic component for the route
- Route-specific files (`types.ts`, `constants.ts`, `utils.ts`) in the route folder root
- Only include things relevant to that specific route

**Shared Resources:**

- Global `types.ts`, `constants.ts`, `utils.ts` outside components folder
- Shared components in `/components/shared`
- Reusable hooks in `/hooks` folder

### Component Guidelines

**Rendering:**

- Server-rendered components by default
- Use client components (`'use client'`) only when needed (interactivity, browser APIs, state)

**Size Limits:**

- **Target**: Components should stay below 200 lines of code
- **Acceptable**: Can be larger for complex components (up to 600 LoC max)
- **Extract**: Complex logic to hooks, reducers, or proper state management

**State Management:**

- Avoid using `useEffect` if better managed with proper state management
- Extract complex state to custom hooks (in `/hooks` folder)
- Use reducers for complex state transitions
- Consider proper state management libraries for global state

### Type Safety

**MUST:**

- Type-safety is mandatory
- Avoid using `any` type
- Use proper TypeScript types and interfaces
- Leverage type inference where appropriate
- Use generic types for reusable components

**Example:**

```typescript
// ❌ Bad
function processData(data: any) {
  return data.value;
}

// ✅ Good
interface Data {
  value: string;
  id: number;
}

function processData(data: Data): string {
  return data.value;
}
```

### Code Quality

- Keep components focused and single-purpose
- Extract complex logic to hooks or utilities
- Use meaningful variable and function names
- Implement proper error boundaries
- Handle loading and error states gracefully

---

## General Best Practices

### Before Starting a New Task

1. **Review existing code**: Understand patterns, conventions, and architecture
2. **Check for similar implementations**: Reuse existing patterns when possible
3. **Identify dependencies**: Understand what needs to be modified or created
4. **Plan the approach**: Consider the simplest solution first

### Code Review Checklist

- [ ] Follows established patterns and conventions
- [ ] Proper error handling implemented
- [ ] Type safety maintained
- [ ] No over-engineering
- [ ] Proper separation of concerns
- [ ] Logging added where appropriate
- [ ] Tests written (if applicable)
- [ ] Documentation updated (if needed)

### Performance Considerations

- Optimize database queries (avoid N+1 problems)
- Use proper indexing
- Implement caching where appropriate
- Lazy load components when possible
- Minimize bundle size

---

## Pinecone (Vector Database)

⚠️ **MANDATORY: If you need to help with Pinecone, vector databases, embeddings, semantic search, RAG, or recommendations, you MUST read `.agents/PINECONE.md` first** to determine:

- What questions to ask the user
- How to select the programming language
- Which guide files to consult for implementation details

IGNORE this and below for now:
Do not proceed with Pinecone-related tasks without consulting the appropriate guide files. Use `.agents/PINECONE.md` as your entry point and follow its "Choosing the Right Guide" section to navigate to the appropriate resources.

### Pinecone Instructions Catalog

@./.agents/PINECONE.md
@./.agents/PINECONE-cli.md
@./.agents/PINECONE-python.md
@./.agents/PINECONE-typescript.md
@./.agents/PINECONE-go.md
@./.agents/PINECONE-java.md
@./.agents/PINECONE-quickstart.md
@./.agents/PINECONE-troubleshooting.md
