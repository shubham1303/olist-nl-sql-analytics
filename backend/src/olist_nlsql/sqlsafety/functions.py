"""Map sqlglot function nodes to the PostgreSQL names used in the catalog allowlist."""

import re

from sqlglot import exp

# Func subclasses that are syntax, not callable functions. sqlglot models boolean
# connectors and EXISTS as Func nodes; CAST is checked separately against the
# catalog's cast_types.
STRUCTURAL_FUNCS: tuple[type[exp.Func], ...] = (
    exp.Case,
    exp.If,
    exp.Cast,
    exp.And,
    exp.Or,
    exp.Exists,
)

# A call renders as NAME(...) or, for keyword functions such as CURRENT_DATE, as NAME.
_CALL = re.compile(r"\s*([A-Za-z_][A-Za-z0-9_]*)\s*(?:\(|$)")


def function_name(node: exp.Func) -> str:
    """The PostgreSQL name of a function call, upper case.

    sqlglot normalises some calls (DATE_PART -> EXTRACT, MEDIAN -> PERCENTILE_CONT), so
    the name is taken from the PostgreSQL rendering of the node: that is what the
    database would actually execute. Operator-style nodes (``a ~ 'x'``, ``data -> 'k'``)
    do not render as a call and get their sqlglot class name, which is never in the
    allowlist, so a column name can never be mistaken for a function name.
    """
    if isinstance(node, exp.Anonymous):
        return node.name.upper()
    match = _CALL.match(node.sql(dialect="postgres"))
    return match.group(1).upper() if match else f"<{type(node).__name__}>"
