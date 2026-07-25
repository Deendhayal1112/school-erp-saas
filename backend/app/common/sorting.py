"""
Generic Sorting Engine for SQLAlchemy Queries.
"""

from typing import Any

from sqlalchemy import Select, asc, desc, inspect


def apply_sorting(
    query: Select,
    model: type[Any],
    sort_param: str | None,
    sortable_fields: list[str],
    default_sort: str | None = "-created_at",
) -> Select:
    """
    Parses sorting arguments and appends order_by clauses to a SQLAlchemy query.

    Arguments:
        query: The SQLAlchemy select statement.
        model: The target SQLAlchemy Model class.
        sort_param: Comma-separated sort keys (e.g., "-created_at,first_name").
        sortable_fields: Whitelist of allowed field names that can be sorted.
        default_sort: Fallback sort string if no sort_param is provided.
    """
    mapper = inspect(model)
    sort_str = sort_param or default_sort
    if not sort_str:
        return query

    order_clauses = []
    # Split comma-separated sort instructions
    instructions = [i.strip() for i in sort_str.split(",") if i.strip()]

    for inst in instructions:
        is_desc = inst.startswith("-")
        field_name = inst[1:] if is_desc else inst

        # Enforce sortable field whitelist
        if field_name not in sortable_fields:
            continue

        # Double check field actually exists on database column definition
        if field_name not in mapper.columns:
            continue

        column = mapper.columns[field_name]
        clause = desc(column) if is_desc else asc(column)
        order_clauses.append(clause)

    if order_clauses:
        query = query.order_by(*order_clauses)

    return query
