# Public API Decorators for Pixeltable

**Date**: 2025-10-18
**Status**: Proposed
**Author**: Documentation Team
**Purpose**: Unified decorator system for marking public API and enabling automatic FastAPI endpoint generation

---

## Problem Statement

Currently, the public API is defined in `docs/public_api.opml` as an XML file, which:

- ❌ Requires manual maintenance (easy to forget to update)
- ❌ Separated from the actual code (can get out of sync)
- ❌ No type validation or IDE support
- ❌ Can't be used for automatic endpoint generation
- ❌ Doesn't integrate with documentation generation

---

## Proposed Solution

Create a `@public_api` decorator that:

1. **Marks public API** - Explicitly declares what's public vs internal
2. **Enables FastAPI generation** - Automatically creates REST endpoints
3. **Validates types** - Uses Pydantic for input/output validation
4. **Generates documentation** - Integrates with existing doc pipeline
5. **IDE support** - Clear markers for what's public

---

## Architecture

### 1. Core Decorator

```python
# pixeltable/decorators.py

from typing import TypeVar, Callable, Any, Optional
from functools import wraps
from pydantic import BaseModel, create_model
import inspect

T = TypeVar('T')

# Registry of all public API functions
_PUBLIC_API_REGISTRY: dict[str, dict[str, Any]] = {}

def public_api(
    category: str = "core",
    endpoint: bool = True,
    http_method: str = "POST",
    path: Optional[str] = None,
    response_model: Optional[type[BaseModel]] = None,
):
    """
    Decorator to mark functions/methods/classes as public API.

    Args:
        category: API category (core, io, functions, etc.)
        endpoint: Whether to expose as FastAPI endpoint
        http_method: HTTP method for endpoint (GET, POST, etc.)
        path: Custom endpoint path (default: /api/{module}/{function})
        response_model: Pydantic model for response validation

    Example:
        ```python
        @public_api(category="tables", endpoint=True)
        def create_table(
            path: str,
            schema: dict[str, ColumnType],
        ) -> Table:
            '''Create a new table.'''
            ...
        ```
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        # Get function metadata
        module = func.__module__
        qualname = func.__qualname__
        signature = inspect.signature(func)

        # Auto-generate Pydantic models from type hints
        input_model = _create_input_model(func, signature)
        output_model = response_model or _create_output_model(func, signature)

        # Register in public API
        api_path = path or f"/api/{module.split('.')[-1]}/{func.__name__}"
        _PUBLIC_API_REGISTRY[qualname] = {
            "function": func,
            "category": category,
            "module": module,
            "endpoint": endpoint,
            "http_method": http_method,
            "path": api_path,
            "input_model": input_model,
            "output_model": output_model,
            "signature": signature,
            "docstring": func.__doc__,
        }

        @wraps(func)
        def wrapper(*args, **kwargs) -> T:
            # Optional: Add validation, logging, telemetry here
            return func(*args, **kwargs)

        # Attach metadata to function for introspection
        wrapper.__public_api__ = True
        wrapper.__api_metadata__ = _PUBLIC_API_REGISTRY[qualname]

        return wrapper

    return decorator


def _create_input_model(func: Callable, sig: inspect.Signature) -> type[BaseModel]:
    """Auto-generate Pydantic input model from function signature."""
    fields = {}
    for param_name, param in sig.parameters.items():
        if param_name == 'self':
            continue

        # Get type annotation
        annotation = param.annotation if param.annotation != inspect.Parameter.empty else Any

        # Get default value
        default = param.default if param.default != inspect.Parameter.empty else ...

        fields[param_name] = (annotation, default)

    # Create Pydantic model
    model_name = f"{func.__name__.title()}Input"
    return create_model(model_name, **fields)


def _create_output_model(func: Callable, sig: inspect.Signature) -> type[BaseModel]:
    """Auto-generate Pydantic output model from return type annotation."""
    return_type = sig.return_annotation if sig.return_annotation != inspect.Signature.empty else Any

    model_name = f"{func.__name__.title()}Output"
    return create_model(model_name, result=(return_type, ...))
```

### 2. Usage Examples

#### Example 1: Table Operations

```python
# pixeltable/catalog/table.py

from pixeltable.decorators import public_api
from pixeltable.types import ColumnType
from typing import Optional

class Table:

    @public_api(category="tables", endpoint=True)
    def add_column(
        self,
        *,
        if_exists: Literal['error', 'ignore', 'replace'] = 'error',
        **kwargs: ColumnType
    ) -> UpdateStatus:
        """
        Adds an ordinary (non-computed) column to the table.

        Args:
            if_exists: Behavior if column exists
            kwargs: Column name and type

        Returns:
            Information about the execution status
        """
        ...

    @public_api(category="tables", endpoint=True)
    def insert(
        self,
        source: Optional[TableDataSource] = None,
        /,
        *,
        on_error: Literal['abort', 'ignore'] = 'abort',
        **kwargs: Any
    ) -> UpdateStatus:
        """
        Inserts rows into this table.

        Args:
            source: Data source to import from
            on_error: Error handling behavior
            kwargs: Column values for single row insert

        Returns:
            Update status information
        """
        ...
```

#### Example 2: Top-level Functions

```python
# pixeltable/__init__.py

from pixeltable.decorators import public_api

@public_api(category="core", endpoint=True, http_method="POST")
def create_table(
    path: str,
    schema: Optional[dict[str, ColumnType]] = None,
    *,
    primary_key: Optional[str | list[str]] = None,
    if_exists: Literal['error', 'replace'] = 'error',
) -> Table:
    """
    Create a new table.

    Args:
        path: Table path
        schema: Column definitions
        primary_key: Primary key column(s)
        if_exists: Behavior if table exists

    Returns:
        The created table
    """
    ...

@public_api(category="core", endpoint=True, http_method="GET")
def get_table(path: str) -> Table:
    """
    Get a handle to an existing table.

    Args:
        path: Table path

    Returns:
        The table handle
    """
    ...

@public_api(category="core", endpoint=True, http_method="GET")
def list_tables(dir_path: str = "", recursive: bool = True) -> list[str]:
    """
    List tables in a directory.

    Args:
        dir_path: Directory path
        recursive: Whether to list recursively

    Returns:
        List of table paths
    """
    ...
```

#### Example 3: UDFs (User Defined Functions)

```python
# pixeltable/functions/huggingface.py

from pixeltable.decorators import public_api
from pixeltable.func import Function

@public_api(category="functions.huggingface", endpoint=False)
class clip(Function):
    """
    CLIP embedding function.

    Supports both text and image inputs.
    """

    @classmethod
    def using(cls, model_id: str = 'openai/clip-vit-base-patch32') -> 'clip':
        """
        Create a CLIP embedding function with specified model.

        Args:
            model_id: HuggingFace model ID

        Returns:
            Configured CLIP function
        """
        ...
```

---

## FastAPI Integration

### Auto-generate FastAPI Endpoints

```python
# pixeltable/server/api.py

from fastapi import FastAPI, HTTPException
from pixeltable.decorators import _PUBLIC_API_REGISTRY
from pydantic import BaseModel

app = FastAPI(title="Pixeltable API", version="0.4.17")

def register_endpoints():
    """Automatically register all @public_api decorated functions as endpoints."""

    for qualname, metadata in _PUBLIC_API_REGISTRY.items():
        if not metadata["endpoint"]:
            continue

        func = metadata["function"]
        path = metadata["path"]
        method = metadata["http_method"]
        input_model = metadata["input_model"]
        output_model = metadata["output_model"]

        # Create endpoint handler
        async def endpoint_handler(request: input_model) -> output_model:
            try:
                # Call the actual function
                result = func(**request.dict())
                return output_model(result=result)
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))

        # Register with FastAPI
        if method == "GET":
            app.get(path, response_model=output_model)(endpoint_handler)
        elif method == "POST":
            app.post(path, response_model=output_model)(endpoint_handler)
        elif method == "PUT":
            app.put(path, response_model=output_model)(endpoint_handler)
        elif method == "DELETE":
            app.delete(path, response_model=output_model)(endpoint_handler)

# Auto-register on import
register_endpoints()
```

### Example API Usage

```bash
# Create a table
curl -X POST http://localhost:8000/api/pixeltable/create_table \
  -H "Content-Type: application/json" \
  -d '{
    "path": "my_table",
    "schema": {
      "id": "Int",
      "name": "String"
    },
    "primary_key": "id"
  }'

# Get table
curl -X GET http://localhost:8000/api/pixeltable/get_table?path=my_table

# List tables
curl -X GET http://localhost:8000/api/pixeltable/list_tables?dir_path=/&recursive=true

# Insert data
curl -X POST http://localhost:8000/api/table/insert \
  -H "Content-Type: application/json" \
  -d '{
    "table_path": "my_table",
    "source": [
      {"id": 1, "name": "Alice"},
      {"id": 2, "name": "Bob"}
    ]
  }'
```

---

## Documentation Integration

### Auto-generate API Documentation

The decorator can feed into existing doc generation:

```python
# doctools/mintlifier/mintlifier.py

from pixeltable.decorators import _PUBLIC_API_REGISTRY

def generate_api_docs():
    """Generate API documentation from @public_api registry."""

    # Group by category
    api_by_category = {}
    for qualname, metadata in _PUBLIC_API_REGISTRY.items():
        category = metadata["category"]
        if category not in api_by_category:
            api_by_category[category] = []
        api_by_category[category].append(metadata)

    # Generate markdown for each category
    for category, apis in api_by_category.items():
        generate_category_docs(category, apis)

def generate_category_docs(category: str, apis: list[dict]):
    """Generate docs for a category."""

    mdx_content = f"# {category.title()} API\n\n"

    for api in apis:
        func = api["function"]
        sig = api["signature"]

        mdx_content += f"## `{func.__name__}()`\n\n"
        mdx_content += f"{api['docstring']}\n\n"

        # Add signature
        mdx_content += "**Signature:**\n\n"
        mdx_content += f"```python\n{func.__name__}{sig}\n```\n\n"

        # Add endpoint info if available
        if api["endpoint"]:
            mdx_content += "**REST Endpoint:**\n\n"
            mdx_content += f"- Method: `{api['http_method']}`\n"
            mdx_content += f"- Path: `{api['path']}`\n\n"

        # Add Pydantic models
        mdx_content += "**Request Model:**\n\n"
        mdx_content += f"```json\n{api['input_model'].schema_json(indent=2)}\n```\n\n"

    # Write to file
    with open(f"docs/api/{category}.mdx", "w") as f:
        f.write(mdx_content)
```

### Replace `public_api.opml`

Instead of maintaining XML:

```xml
<!-- OLD: docs/public_api.opml -->
<opml>
  <outline text="pixeltable">
    <outline text="create_table"/>
    <outline text="get_table"/>
    ...
  </outline>
</opml>
```

We get it from the decorator registry:

```python
# NEW: Auto-generated from @public_api decorators

def get_public_api() -> dict:
    """Get public API structure from decorator registry."""
    return {
        "core": ["create_table", "get_table", "list_tables", ...],
        "tables": ["Table.add_column", "Table.insert", ...],
        "functions.huggingface": ["clip", ...],
        ...
    }
```

---

## Benefits

### 1. Single Source of Truth

```python
@public_api(category="tables")
def add_column(self, **kwargs) -> UpdateStatus:
    """Add a column."""
    ...
```

This single decorator:
- ✅ Marks it as public API
- ✅ Generates documentation
- ✅ Creates REST endpoint
- ✅ Validates types with Pydantic
- ✅ Updates API registry

### 2. Type Safety

```python
# Input validation happens automatically
@public_api()
def create_table(
    path: str,  # Required, must be string
    schema: Optional[dict[str, ColumnType]] = None,  # Optional
) -> Table:  # Return type validated
    ...
```

### 3. Automatic OpenAPI/Swagger Docs

FastAPI automatically generates:
- OpenAPI schema
- Swagger UI at `/docs`
- ReDoc at `/redoc`
- JSON schema for all models

### 4. Easier Maintenance

```python
# Add new public function? Just decorate it!
@public_api(category="io")
def export_to_parquet(table: Table, path: str) -> None:
    """Export table to Parquet file."""
    ...

# That's it! Docs, endpoint, and registry updated automatically.
```

---

## Migration Plan

### Phase 1: Add Decorator Infrastructure (Week 1)

1. Create `pixeltable/decorators.py`
2. Implement `@public_api` decorator
3. Add Pydantic model generation
4. Create API registry

### Phase 2: Decorate Core API (Week 2)

1. Add `@public_api` to top-level functions (`create_table`, `get_table`, etc.)
2. Add to `Table` methods (`add_column`, `insert`, etc.)
3. Add to UDF classes (`clip`, `yolox`, etc.)

### Phase 3: FastAPI Integration (Week 3)

1. Create `pixeltable/server/api.py`
2. Auto-register endpoints
3. Add authentication/authorization
4. Deploy test server

### Phase 4: Documentation Integration (Week 4)

1. Update mintlifier to read from registry
2. Generate API docs automatically
3. Deprecate `public_api.opml`
4. Update CONTRIBUTING.md

---

## Example: Complete Migration

### Before

```python
# pixeltable/__init__.py
def create_table(path: str, schema: Optional[dict] = None) -> Table:
    """Create a new table."""
    ...

# docs/public_api.opml
<outline text="create_table"/>

# Endpoint: Doesn't exist, need to manually create
```

### After

```python
# pixeltable/__init__.py
@public_api(category="core", endpoint=True)
def create_table(path: str, schema: Optional[dict[str, ColumnType]] = None) -> Table:
    """Create a new table."""
    ...

# Automatic:
# - API docs generated
# - REST endpoint at POST /api/pixeltable/create_table
# - Input/output validation via Pydantic
# - OpenAPI schema
# - No manual OPML editing needed
```

---

## Advanced Features

### 1. Versioning

```python
@public_api(category="tables", version="v2", endpoint=True)
def add_column_v2(self, **kwargs) -> UpdateStatus:
    """New version of add_column with breaking changes."""
    ...

# Creates endpoint at: POST /api/v2/table/add_column
```

### 2. Deprecation Warnings

```python
@public_api(category="tables", deprecated="0.5.0", replacement="add_columns")
def add_column(self, **kwargs) -> UpdateStatus:
    """Add a column. DEPRECATED: Use add_columns instead."""
    warnings.warn("add_column is deprecated, use add_columns", DeprecationWarning)
    ...
```

### 3. Rate Limiting

```python
@public_api(category="io", endpoint=True, rate_limit="100/hour")
def export_to_s3(table: Table, bucket: str) -> None:
    """Export table to S3."""
    ...
```

### 4. Authentication Required

```python
@public_api(category="admin", endpoint=True, auth_required=True)
def delete_all_tables() -> None:
    """Delete all tables. Requires admin authentication."""
    ...
```

---

## Open Questions

1. **How to handle method decorators?** (e.g., `Table.add_column`)
   - **Option A**: Decorate methods directly (simple)
   - **Option B**: Use metaclass to auto-register (more magic)

2. **Should ALL functions be endpoints?** Or just specific ones?
   - **Recommendation**: Use `endpoint=True/False` flag

3. **How to handle complex types?** (e.g., `Table`, `DataFrame`)
   - **Option A**: Serialize to JSON representation
   - **Option B**: Use references/IDs for server-side objects

4. **Authentication strategy?** API keys, OAuth, JWT?
   - **Recommendation**: Start simple (API keys), add OAuth later

---

## References

- **FastAPI**: https://fastapi.tiangolo.com/
- **Pydantic**: https://docs.pydantic.dev/
- **OpenAPI**: https://swagger.io/specification/
- **Current public_api.opml**: `/Users/lux/repos/pixeltable/docs/public_api.opml`

---

## Estimated Effort

- **Phase 1** (Infrastructure): 2-3 days
- **Phase 2** (Decoration): 3-4 days
- **Phase 3** (FastAPI): 2-3 days
- **Phase 4** (Docs): 1-2 days

**Total**: 2-3 weeks for complete implementation

---

## Success Metrics

After implementation:

- ✅ **Zero manual OPML editing** - Everything from decorators
- ✅ **100% type coverage** - All public API has Pydantic models
- ✅ **REST API available** - All functions accessible via HTTP
- ✅ **OpenAPI docs** - Automatic Swagger UI
- ✅ **Fewer docs bugs** - Type validation catches errors early

---

## Notes from 2025-10-18 Session

- Inspired by FastAPI's decorator pattern
- Would integrate well with existing mintlifier pipeline
- Could replace manual `public_api.opml` maintenance
- Enables future server/cloud deployment
- Makes it easy to build integrations (JavaScript client, CLI, etc.)

**Key insight**: Decorators are a single source of truth for API surface, docs, and endpoints!

---

## Next Steps

This document covers the **core `@public_api` decorator system**. For advanced techniques including:
- Ray integration for distributed computing
- Semantic interface auto-generation from HuggingFace configs
- Parallel column processing across CPU cores/GPUs
- Ontology-based type reasoning
- Interaction logging for full provenance tracking

See **`2025_10_18_ADVANCED_DECORATOR_TECHNIQUES.md`**

