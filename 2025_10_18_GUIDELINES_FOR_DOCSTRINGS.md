# Guidelines for Writing MDX-Compatible Python Docstrings

**Date**: 2025-10-18
**Author**: Documentation Team
**Purpose**: Prevent Python docstrings from generating invalid MDX that breaks Mintlify deployment

---

## Problem Statement

Python docstrings are extracted by `mintlifier` and converted to MDX for Mintlify documentation. While Python accepts many formatting patterns, **MDX has stricter parsing rules**. Invalid MDX causes:

1. **Silent deployment failures** - Mintlify deploys but pages don't render
2. **Acorn parser errors** - "Could not parse expression with acorn"
3. **Missing documentation** - Methods don't appear in deployed docs
4. **Late discovery** - Issues found months after code is written

---

## Critical Rules

### 1. Code Fence Placement

**❌ WRONG - Code fence on same line as closing delimiter:**
```python
"""
```python
my_function(
    arg1='value',
    arg2='value'
)```

Text continues...
"""
```

**✅ CORRECT - Code fence on its own line:**
```python
"""
```python
my_function(
    arg1='value',
    arg2='value'
)
```

Text continues...
"""
```

**Why**: MDX requires code fences (` ``` `) to be on their own lines, not attached to code.

**Patterns to avoid:**
- `)```  - Closing parenthesis + fence
- `}```  - Closing brace + fence
- `]```  - Closing bracket + fence

---

### 2. Code Fences Must Be Complete

**❌ WRONG - Broken code fence mid-example:**
```python
"""
Example:
```python
tbl.update(
```
[{'id': 1, 'name': 'Alice'}],
if_not_exists='insert')
"""
```

**✅ CORRECT - Complete code block:**
```python
"""
Example:
```python
tbl.update(
    [{'id': 1, 'name': 'Alice'}],
    if_not_exists='insert'
)
```
"""
```

**Why**: Closing a code fence mid-example causes the following code to be parsed as JSX/JavaScript, which triggers acorn parser errors.

---

### 3. Backtick Pairing

**❌ WRONG - Mismatched or escaped backticks:**
```python
"""
Store error info in `tbl.col.errormsg` tbl.col.errortype\` fields.
"""
```

**✅ CORRECT - Properly paired backticks:**
```python
"""
Store error info in `tbl.col.errormsg` and `tbl.col.errortype` fields.
"""
```

**Why**: Each backtick must have a matching pair. Escaped backticks `` \` `` are invalid in MDX.

---

### 4. HTML Tags Must Be Self-Closing

**❌ WRONG - Unclosed HTML tag:**
```python
"""
Here's an image: <img src="diagram.png">
"""
```

**✅ CORRECT - Self-closing tag:**
```python
"""
Here's an image: <img src="diagram.png" />
"""
```

**Why**: MDX requires all HTML elements to be properly closed or self-closing.

---

### 5. Markdown Links (Not Escaped Brackets)

**❌ WRONG - Escaped square brackets:**
```python
"""
Uses \[CLIP embedding\]\[pixeltable.functions.huggingface.clip\] for indexing.
"""
```

**✅ CORRECT - Proper markdown link:**
```python
"""
Uses [CLIP embedding][pixeltable.functions.huggingface.clip] for indexing.
"""
```

**Why**: Escaped brackets `\[` cause MDX parser errors. Use proper markdown link syntax.

---

### 6. Python REPL Syntax

**❌ WRONG - Broken REPL prompts:**
```python
"""
Example:

> > > from module import func
... result = func()
"""
```

**✅ CORRECT - Proper REPL syntax:**
```python
"""
Example:

```python
>>> from module import func
... result = func()
```
"""
```

**Why**: REPL examples should be in code blocks with proper `>>>` and `...` continuation marks.

---

## Real-World Examples

### Example 1: insert() Method (Fixed 2025-10-18)

**Problem**: Code fences attached to closing parentheses caused acorn parser error.

**Before**:
```python
"""
```python
insert(
    source: TableSourceDataType,
    **kwargs: Any,
)```
"""
```

**After**:
```python
"""
```python
insert(
    source: TableSourceDataType,
    **kwargs: Any,
)
```
"""
```

**Impact**: `Table.insert()` was missing from deployed docs for v0.4.17.

---

### Example 2: add_computed_column() (Fixed 2025-10-18)

**Problem**: Mismatched backticks in parameter description.

**Before**:
```python
"""
Args:
    on_error: ...
        - 'ignore': ... stored in `tbl.col.errormsg` tbl.col.errortype\` fields.
"""
```

**After**:
```python
"""
Args:
    on_error: ...
        - 'ignore': ... stored in `tbl.col.errormsg` and `tbl.col.errortype` fields.
"""
```

**Impact**: Prevented `add_computed_column()` from appearing in docs.

---

### Example 3: batch_update() (Fixed 2025-10-18)

**Problem**: Code fence closed mid-function call.

**Before**:
```python
"""
```python
tbl.update(
```
[{'id': 1, 'name': 'Alice'}],
if_not_exists='insert')
"""
```

**After**:
```python
"""
```python
tbl.update(
    [{'id': 1, 'name': 'Alice'}],
    if_not_exists='insert'
)
```
"""
```

**Impact**: Acorn parser error on line 321 of generated table.mdx.

---

### Example 4: add_embedding_index() (Fixed 2025-10-18)

**Problem**: Escaped brackets and broken REPL syntax.

**Before**:
```python
"""
Uses \[CLIP embedding\]\[pixeltable.functions.huggingface.clip\]:

> > > from pixeltable.functions.huggingface import clip
... embedding_fn = clip.using(model_id='openai/clip-vit-base-patch32')
"""
```

**After**:
```python
"""
Uses [CLIP embedding][pixeltable.functions.huggingface.clip]:

```python
>>> from pixeltable.functions.huggingface import clip
... embedding_fn = clip.using(model_id='openai/clip-vit-base-patch32')
```
"""
```

**Impact**: Multiple acorn parsing errors prevented page rendering.

---

## Validation

### Pre-Commit Hook (Recommended)

Simple pattern matching with **zero false positives**:

```python
def check_docstring(docstring: str) -> list[str]:
    """Check docstring for MDX-incompatible patterns."""
    errors = []

    # Check for )``` pattern (code fence on closing paren)
    if ')```' in docstring:
        errors.append("Code fence on same line as closing paren: )```")

    # Check for }``` pattern
    if '}```' in docstring:
        errors.append("Code fence on same line as closing brace: }```")

    # Check for ]``` pattern
    if ']```' in docstring:
        errors.append("Code fence on same line as closing bracket: ]```")

    # Check for escaped backticks
    if r'\`' in docstring:
        errors.append("Escaped backtick found: \\`")

    # Check for double fences
    if '```\n```' in docstring or '```\r\n```' in docstring:
        errors.append("Double code fences detected")

    return errors
```

### Local Testing

```bash
# Generate docs from current code
cd pixeltable-doctools
mintlifier --no-errors

# Validate MDX (requires Node.js)
npx remark docs/target/sdk/**/*.mdx --frail

# Check for specific patterns
grep -r ')```' pixeltable/catalog/
```

---

## Best Practices

### 1. Use Code Blocks for All Examples

Always wrap Python code examples in proper code blocks:

```python
"""
Example:

```python
result = my_function(arg1, arg2)
```
"""
```

### 2. Keep Code Blocks Self-Contained

Don't split function calls across code blocks:

```python
# ❌ WRONG
"""
```python
my_function(
```
arg1, arg2)
"""

# ✅ CORRECT
"""
```python
my_function(arg1, arg2)
```
"""
```

### 3. Test Before Release

Run mintlifier locally before tagging releases to catch MDX errors early.

### 4. Use Inline Code for Short References

Use single backticks for inline code mentions:

```python
"""
The `column_name` parameter specifies which column to update.
"""
```

### 5. Link to Other Documentation

Use markdown link syntax for cross-references:

```python
"""
See [`Table.add_column()`][pixeltable.Table.add_column] for details.
"""
```

---

## Error Messages

### Common Mintlify Errors

**"Could not parse expression with acorn"**
- Cause: Code or data structures outside code blocks
- Fix: Wrap all code in proper ` ```python ... ``` ` blocks

**"Unexpected closing tag"**
- Cause: Unclosed HTML elements
- Fix: Use self-closing tags: `<img />` not `<img>`

**"Could not parse import/exports with acorn"**
- Cause: Import statements outside code blocks
- Fix: Wrap imports in code blocks

---

## Prevention Strategy

1. **Pre-commit hooks** - Validate docstrings before commit
2. **CI checks** - Run mintlifier + MDX validation on PRs
3. **Release checklist** - Validate docs before tagging versions
4. **Documentation** - Link to these guidelines in CONTRIBUTING.md
5. **Code reviews** - Check docstrings during review

---

## References

- **Acorn Parser**: https://github.com/acornjs/acorn
- **MDX Spec**: https://mdxjs.com/docs/troubleshooting-mdx/
- **Mintlify Docs**: https://mintlify.com/docs
- **Post-Mortem**: See `POSTMORTEM_TABLE_MDX_PARSING_FAILURE.md`
- **Original Guidelines**: See `DOCSTRING_MDX_GUIDELINES.md`

---

## Summary Checklist

When writing docstrings with code examples:

- [ ] Code fences (` ``` `) are on their own lines
- [ ] No `)```  or `}```  or `]```  patterns
- [ ] All backticks are properly paired
- [ ] HTML tags are self-closing (`<img />`)
- [ ] Markdown links use `[text][ref]`, not `\[text\]`
- [ ] REPL examples are in code blocks with `>>>` and `...`
- [ ] Code blocks are complete and self-contained
- [ ] Run local validation: `mintlifier --no-errors`

**Remember**: Valid Python docstrings can generate invalid MDX. Always validate!
