"""
Generic Filtering Engine for SQLAlchemy Queries.
"""

from typing import Any

from sqlalchemy import Select, and_, inspect

# Define operator mappings for string suffixes
OPERATOR_MAP = {
    "exact": lambda col, val: col == val,
    "not": lambda col, val: col != val,
    "contains": lambda col, val: col.ilike(f"%{val}%"),
    "icontains": lambda col, val: col.ilike(f"%{val}%"),
    "startswith": lambda col, val: col.ilike(f"{val}%"),
    "istartswith": lambda col, val: col.ilike(f"{val}%"),
    "endswith": lambda col, val: col.ilike(f"%{val}"),
    "iendswith": lambda col, val: col.ilike(f"%{val}"),
    "gt": lambda col, val: col > val,
    "gte": lambda col, val: col >= val,
    "lt": lambda col, val: col < val,
    "lte": lambda col, val: col <= val,
    "in": lambda col, val: (
        col.in_(val) if isinstance(val, (list, tuple, set)) else col.in_([val])
    ),
    "notin": lambda col, val: (
        ~col.in_(val) if isinstance(val, (list, tuple, set)) else ~col.in_([val])
    ),
    "isnull": lambda col, val: col.is_(None) if val else col.isnot(None),
}


def apply_filters(
    query: Select,
    model: type[Any],
    filters: dict[str, Any],
) -> Select:
    """
    Parses a dictionary of filter values and dynamically appends where clauses.
    Example filters format:
        {
            "email__exact": "test@demo.com",
            "first_name__contains": "John",
            "created_at__gte": "2026-01-01T00:00:00",
            "status__in": ["active", "pending"]
        }
    """
    if not filters:
        return query

    # Get model inspection helper to check if fields exist on model
    mapper = inspect(model)
    clauses = []

    for key, value in filters.items():
        if value is None or value == "":
            continue

        # Split key into field name and operator suffix
        parts = key.split("__")
        field_name = parts[0]
        operator_name = parts[1] if len(parts) > 1 else "exact"

        # Ensure field exists on target model
        if field_name not in mapper.columns:
            # Skip invalid columns silently (prevent errors on extra query args)
            continue

        column = mapper.columns[field_name]
        op_func = OPERATOR_MAP.get(operator_name)

        if op_func:
            clauses.append(op_func(column, value))

    if clauses:
        query = query.where(and_(*clauses))

    return query
