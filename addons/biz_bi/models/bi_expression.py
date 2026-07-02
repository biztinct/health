# -*- coding: utf-8 -*-
"""Safe calculated-field expression compiler.

Surface syntax is a Python expression (parsed with the stdlib ``ast`` module —
no hand-written grammar) where ``[Field Name]`` brackets reference dataset
fields. The compiler transpiles the tree to SQL built exclusively from:

* field references resolved through a caller-supplied callback (which only
  returns SQL for validated ``bi.field`` records),
* literals injected as query parameters (never inlined),
* a whitelist of function templates below.

No attribute access, no subscripts, no comprehensions, no lambdas, no
subqueries, no free SQL — anything outside the whitelist raises
``ExpressionError`` naming the offending token.
"""
import ast
import re

from odoo.tools import SQL

FIELD_REF_RE = re.compile(r'\[([^\[\]]+)\]')
PLACEHOLDER = '__bifld_%d__'
PLACEHOLDER_RE = re.compile(r'^__bifld_(\d+)__$')


class ExpressionError(ValueError):
    pass


def _substitute_field_refs(text):
    """Replace [Field Name] refs (outside string literals) with placeholder
    identifiers so the result is parseable Python. Returns (python_src, refs)
    where refs[i] is the field name for placeholder i."""
    out = []
    refs = []
    i = 0
    n = len(text)
    quote = None
    while i < n:
        ch = text[i]
        if quote:
            out.append(ch)
            if ch == quote and text[i - 1] != '\\':
                quote = None
            i += 1
        elif ch in ('"', "'"):
            quote = ch
            out.append(ch)
            i += 1
        elif ch == '[':
            match = FIELD_REF_RE.match(text, i)
            if not match:
                raise ExpressionError(
                    "Unclosed or empty field reference near position %d" % i)
            refs.append(match.group(1).strip())
            out.append(PLACEHOLDER % (len(refs) - 1))
            i = match.end()
        else:
            out.append(ch)
            i += 1
    if quote:
        raise ExpressionError("Unterminated string literal")
    return ''.join(out), refs


# ---------------------------------------------------------------------------
# Function whitelist. Each entry: (min_args, max_args, builder(args)->SQL,
# is_aggregate). Builders receive already-compiled SQL arguments.
# ---------------------------------------------------------------------------

def _fn_template(template):
    return lambda args: SQL(template, *args)


_DATE_UNITS = ('year', 'quarter', 'month', 'week', 'day', 'hour', 'minute')


def _fn_date_diff(args, raw_args):
    unit = _require_unit(raw_args[0])
    return SQL(
        "EXTRACT(EPOCH FROM (%s::timestamp - %s::timestamp)) / %s",
        args[2], args[1],
        {'year': 31557600, 'quarter': 7889400, 'month': 2629800,
         'week': 604800, 'day': 86400, 'hour': 3600, 'minute': 60}[unit])


def _fn_date_add(args, raw_args):
    unit = _require_unit(raw_args[2])
    # unit validated against _DATE_UNITS, safe to inline the keyword
    return SQL("(%s::timestamp + (%s * interval '1 " + unit + "'))",
               args[0], args[1])


def _fn_date_part(part):
    return lambda args: SQL("EXTRACT(" + part + " FROM %s)::integer", args[0])


def _require_unit(node):
    if not isinstance(node, ast.Constant) or node.value not in _DATE_UNITS:
        raise ExpressionError(
            "Date unit must be a literal, one of: %s" % ', '.join(_DATE_UNITS))
    return node.value


FUNCTIONS = {
    # name: (min_args, max_args, builder, is_aggregate, wants_raw_args)
    'iff': (3, 3, _fn_template("CASE WHEN %s THEN %s ELSE %s END"), False, False),
    'coalesce': (2, 6, lambda args: SQL("COALESCE(%s)" % ", ".join(["%s"] * len(args)), *args), False, False),
    'abs': (1, 1, _fn_template("ABS(%s)"), False, False),
    'round': (2, 2, _fn_template("ROUND((%s)::numeric, (%s)::integer)"), False, False),
    'floor': (1, 1, _fn_template("FLOOR(%s)"), False, False),
    'ceil': (1, 1, _fn_template("CEIL(%s)"), False, False),
    'concat': (2, 8, lambda args: SQL("CONCAT(%s)" % ", ".join(["(%s)::text"] * len(args)), *args), False, False),
    'upper': (1, 1, _fn_template("UPPER((%s)::text)"), False, False),
    'lower': (1, 1, _fn_template("LOWER((%s)::text)"), False, False),
    'trim': (1, 1, _fn_template("TRIM((%s)::text)"), False, False),
    'left': (2, 2, _fn_template("LEFT((%s)::text, (%s)::integer)"), False, False),
    'right': (2, 2, _fn_template("RIGHT((%s)::text, (%s)::integer)"), False, False),
    'length': (1, 1, _fn_template("LENGTH((%s)::text)"), False, False),
    'year': (1, 1, _fn_date_part('YEAR'), False, False),
    'quarter': (1, 1, _fn_date_part('QUARTER'), False, False),
    'month': (1, 1, _fn_date_part('MONTH'), False, False),
    'week': (1, 1, _fn_date_part('WEEK'), False, False),
    'day': (1, 1, _fn_date_part('DAY'), False, False),
    'date_diff': (3, 3, _fn_date_diff, False, True),
    'date_add': (3, 3, _fn_date_add, False, True),
    'today': (0, 0, lambda args: SQL("CURRENT_DATE"), False, False),
    'now': (0, 0, lambda args: SQL("NOW() AT TIME ZONE 'UTC'"), False, False),
    'age_years': (1, 1, _fn_template(
        "EXTRACT(YEAR FROM AGE(CURRENT_DATE, %s::date))::integer"), False, False),
    # aggregate context
    'sum': (1, 1, _fn_template("SUM(%s)"), True, False),
    'avg': (1, 1, _fn_template("AVG(%s)"), True, False),
    'min': (1, 1, _fn_template("MIN(%s)"), True, False),
    'max': (1, 1, _fn_template("MAX(%s)"), True, False),
    'count': (1, 1, _fn_template("COUNT(%s)"), True, False),
    'count_distinct': (1, 1, _fn_template("COUNT(DISTINCT %s)"), True, False),
    'ratio': (2, 2, _fn_template(
        "(SUM(%s)::numeric / NULLIF(SUM(%s)::numeric, 0))"), True, False),
}

_BIN_OPS = {
    ast.Add: "(%s + %s)",
    ast.Sub: "(%s - %s)",
    ast.Mult: "(%s * %s)",
}
_CMP_OPS = {
    ast.Eq: "(%s = %s)",
    ast.NotEq: "(%s <> %s)",
    ast.Gt: "(%s > %s)",
    ast.GtE: "(%s >= %s)",
    ast.Lt: "(%s < %s)",
    ast.LtE: "(%s <= %s)",
}


class ExpressionCompiler:
    """Compile one expression. ``resolve_field(name) -> SQL`` must raise
    ExpressionError for unknown fields; ``allow_aggregates`` gates the
    aggregate function subset (measures yes, row-level dimensions no)."""

    def __init__(self, resolve_field, allow_aggregates=False):
        self.resolve_field = resolve_field
        self.allow_aggregates = allow_aggregates
        self.uses_aggregates = False

    def compile(self, text):
        if not text or not text.strip():
            raise ExpressionError("Expression is empty")
        python_src, refs = _substitute_field_refs(text)
        self._refs = refs
        try:
            tree = ast.parse(python_src, mode='eval')
        except SyntaxError as exc:
            raise ExpressionError("Syntax error: %s" % exc.msg)
        return self._compile_node(tree.body)

    # -- node dispatch --------------------------------------------------

    def _compile_node(self, node):
        if isinstance(node, ast.Constant):
            return self._compile_constant(node)
        if isinstance(node, ast.Name):
            return self._compile_name(node)
        if isinstance(node, ast.BinOp):
            return self._compile_binop(node)
        if isinstance(node, ast.BoolOp):
            return self._compile_boolop(node)
        if isinstance(node, ast.UnaryOp):
            return self._compile_unaryop(node)
        if isinstance(node, ast.Compare):
            return self._compile_compare(node)
        if isinstance(node, ast.Call):
            return self._compile_call(node)
        if isinstance(node, ast.IfExp):
            return SQL("CASE WHEN %s THEN %s ELSE %s END",
                       self._compile_node(node.test),
                       self._compile_node(node.body),
                       self._compile_node(node.orelse))
        raise ExpressionError(
            "Unsupported syntax: %s" % type(node).__name__)

    def _compile_constant(self, node):
        value = node.value
        if value is None:
            return SQL("NULL")
        if isinstance(value, bool):
            return SQL("TRUE") if value else SQL("FALSE")
        if isinstance(value, (int, float, str)):
            return SQL("%s", value)
        raise ExpressionError("Unsupported literal: %r" % (value,))

    def _compile_name(self, node):
        match = PLACEHOLDER_RE.match(node.id)
        if match:
            return self.resolve_field(self._refs[int(match.group(1))])
        if node.id in ('True', 'False', 'None'):  # py<3.8 style, defensive
            return self._compile_constant(ast.Constant(eval(node.id)))
        raise ExpressionError(
            "Unknown identifier '%s' — field references use [brackets]"
            % node.id)

    def _compile_binop(self, node):
        left = self._compile_node(node.left)
        right = self._compile_node(node.right)
        if isinstance(node.op, ast.Div):
            return SQL("((%s)::numeric / NULLIF((%s)::numeric, 0))",
                       left, right)
        template = _BIN_OPS.get(type(node.op))
        if not template:
            raise ExpressionError(
                "Unsupported operator: %s" % type(node.op).__name__)
        return SQL(template, left, right)

    def _compile_boolop(self, node):
        joiner = " AND " if isinstance(node.op, ast.And) else " OR "
        parts = [self._compile_node(v) for v in node.values]
        return SQL("(" + joiner.join(["%s"] * len(parts)) + ")", *parts)

    def _compile_unaryop(self, node):
        operand = self._compile_node(node.operand)
        if isinstance(node.op, ast.Not):
            return SQL("(NOT %s)", operand)
        if isinstance(node.op, ast.USub):
            return SQL("(- %s)", operand)
        raise ExpressionError(
            "Unsupported operator: %s" % type(node.op).__name__)

    def _compile_compare(self, node):
        if len(node.ops) != 1:
            raise ExpressionError("Chained comparisons are not supported")
        template = _CMP_OPS.get(type(node.ops[0]))
        if not template:
            raise ExpressionError(
                "Unsupported comparison: %s" % type(node.ops[0]).__name__)
        return SQL(template,
                   self._compile_node(node.left),
                   self._compile_node(node.comparators[0]))

    def _compile_call(self, node):
        if not isinstance(node.func, ast.Name):
            raise ExpressionError("Only whitelisted function calls are allowed")
        if node.keywords:
            raise ExpressionError("Keyword arguments are not supported")
        fname = node.func.id.lower()
        spec = FUNCTIONS.get(fname)
        if not spec:
            raise ExpressionError(
                "Unknown function '%s'. Allowed: %s"
                % (fname, ', '.join(sorted(FUNCTIONS))))
        min_args, max_args, builder, is_aggregate, wants_raw = spec
        if is_aggregate:
            if not self.allow_aggregates:
                raise ExpressionError(
                    "Aggregate function '%s' is only allowed in measure "
                    "expressions" % fname)
            self.uses_aggregates = True
        if not (min_args <= len(node.args) <= max_args):
            raise ExpressionError(
                "Function '%s' expects %s argument(s)"
                % (fname, min_args if min_args == max_args
                   else "%d..%d" % (min_args, max_args)))
        args = [self._compile_node(arg) for arg in node.args]
        if wants_raw:
            return builder(args, node.args)
        return builder(args)


def validate_expression(text, known_fields, allow_aggregates=False):
    """Save-time validation: compile against a dummy resolver.
    ``known_fields`` maps ref name -> True for every referencable field.
    Returns the set of referenced field names."""
    used = set()

    def resolver(name):
        if name not in known_fields:
            raise ExpressionError("Unknown field reference [%s]" % name)
        used.add(name)
        return SQL("NULL")

    compiler = ExpressionCompiler(resolver, allow_aggregates=allow_aggregates)
    compiler.compile(text)
    return used
