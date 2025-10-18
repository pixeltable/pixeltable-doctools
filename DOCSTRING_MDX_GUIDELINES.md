# Docstring MDX Guidelines for Pixeltable

## Problem

Python docstrings are converted to MDX for Mintlify documentation. Valid Python docstrings can contain patterns that generate **invalid MDX**, causing silent parsing failures in deployed docs.

## Common Issues

### 1. Code Fence on Same Line as Closing Parenthesis

**❌ WRONG:**
```python
"""
Example usage:

```python
my_function(
    arg1='value',
    arg2='value'
)```

This pattern worked...
"""
```

**✅ CORRECT:**
```python
"""
Example usage:

```python
my_function(
    arg1='value',
    arg2='value'
)
```

This pattern worked...
"""
```

**Why:** MDX parser expects code fence (` ``` `) on its own line, not attached to code.

### 2. Unclosed HTML Tags

**❌ WRONG:**
```python
"""
Here's an image: <img src="foo.png">
"""
```

**✅ CORRECT:**
```python
"""
Here's an image: <img src="foo.png" />
"""
```

**Why:** MDX requires self-closing tags for HTML elements.

### 3. Double Code Fences

**❌ WRONG:**
```python
"""
Example:
```
```
"""
```

**✅ CORRECT:**
```python
"""
Example:
```
"""
```

## Real-World Example

**Commit:** c9748340b (2025-10-18)
**File:** `pixeltable/catalog/table.py`
**Author:** Aaron Siegel (original invalid pattern from 2024-11-08)
**Issue:** `Table.insert()` docstring had `)``` pattern causing Mintlify parsing error

**Error Message:**
```
Failed to parse page content at path sdk/v0.4.17/table.mdx: Could not parse expression with acorn
```

**Impact:** Method didn't appear in deployed documentation despite being in OPML and source code.

## Recommended Pre-Commit Hook Checks

These patterns have **zero false positives** and catch common issues:

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

    # Check for double fences
    if '```\n```' in docstring or '```\r\n```' in docstring:
        errors.append("Double code fences detected")

    return errors
```

## Action Items

1. **Add pre-commit hook** to Pixeltable repo that validates docstrings
2. **Add CI check** that runs mintlifier + MDX validation on PRs
3. **Fail PRs** with invalid docstrings before merge
4. **Document guidelines** in Pixeltable CONTRIBUTING.md

## Benefits

- **Immediate feedback:** Engineers see errors at commit time, not months later during doc deployment
- **Prevent silent failures:** Docs won't deploy broken without warning
- **No false positives:** Simple pattern matching with high confidence
- **Easy to fix:** Clear error messages point to exact issue

## Testing

To test docstrings locally:
```bash
# Generate docs
cd pixeltable-doctools
mintlifier --no-errors

# Validate MDX
npx remark docs/target/sdk/**/*.mdx --frail
```

## Related Issues

- Notebook conversion issues with unclosed `<img>` tags
- Acorn parser errors from invalid JSX syntax
- Silent deployment failures in mintlify
