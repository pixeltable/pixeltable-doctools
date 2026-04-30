"""Generate documentation sections for functions within module pages."""

import inspect
from docstring_parser import Docstring, DocstringMeta, parse as parse_docstring
from typing import Any, Callable
from typing_extensions import get_overloads

from .utils import entity_label
from .page_base import PageBase

class FunctionSectionGenerator(PageBase):
    """Generate documentation sections for functions within module pages."""

    default_name: str
    entity_type: str

    def __init__(self, default_name: str):
        """Initialize the section generator."""
        # Don't initialize PageBase with output_dir since we're not writing files
        self.default_name = default_name

    def _is_udf(self, func: Any) -> bool:
        """Check if a function has the @udf decorator by examining its source code.

        Args:
            func: The function to check

        Returns:
            True if the function has @udf decorator, False otherwise
        """
        try:
            # Get the wrapped function if it exists (for decorated functions)
            actual_func = func

            # Check for polymorphic functions first (py_fn property has assertion)
            if hasattr(func, 'is_polymorphic') and func.is_polymorphic:
                if hasattr(func, 'py_fns') and func.py_fns:
                    actual_func = func.py_fns[0]
            elif hasattr(func, 'py_fn'):
                actual_func = func.py_fn

            # Get source code
            source = inspect.getsource(actual_func)

            # Check for @udf decorator in the source
            # Look for @udf or @pxt.udf
            lines = source.split('\n')
            for line in lines:
                stripped = line.strip()
                if stripped.startswith('@udf') or stripped.startswith('@pxt.udf'):
                    return True
                # Stop checking once we hit the def line
                if stripped.startswith('def '):
                    break
            return False
        except (OSError, TypeError):
            # If we can't get source (built-in, etc.), assume it's not a UDF
            return False

    def generate_section(self, func: Any, func_name: str, module_path: str, entity_type: str | None = None) -> str:
        """Generate function documentation section for inline use.

        Args:
            func: The function object to document
            func_name: Name of the function
            module_path: Full module path (e.g., 'pixeltable.functions.image')
            is_udf: If True, add UDF label; if False, no label; if None, auto-detect (deprecated)

        Returns:
            Markdown string for the function documentation
        """
        # Build section content with elegant visual separation
        content = "\n"

        # Infer entity type if not provided
        if entity_type is None:
            if self._is_udf(func):  # Deprecated path
                entity_type = "udf"
            else:
                entity_type = self.default_name

        self.entity_type = entity_type

        content += f"## {entity_label(entity_type)} {func_name}()\n\n"

        # Add signature
        content += self._document_signature(func, func_name)

        if hasattr(func, "call_output_schema"):
            # 2.0-style iterator
            doc = inspect.getdoc(func.decorated_callable)
        else:
            doc = inspect.getdoc(func)
        if doc:
            parsed = parse_docstring(doc)
            if parsed.description:
                content += f"{self._escape_mdx(parsed.description)}\n\n"
            content += self._document_parameters(func, doc)
            if parsed and parsed.returns:
                content += self._document_returns(parsed, func)
            examples_meta = [m for m in parsed.meta if m.args and "examples" in m.args[0].lower()]
            if examples_meta:
                content += self._format_examples_from_meta(examples_meta)

        return content

    def _document_signature(self, func: Any, func_name: str) -> str:
        """Document function signature."""
        content = '```python '

        if hasattr(func, "signatures"):
            if len(func.signatures) > 1:
                content += "Signatures\n"
            else:
                content += "Signature\n"
            # Pixeltable UDF
            for i, sig in enumerate(func.signatures, 1):
                if len(func.signatures) > 1:
                    content += f"# Signature {i}:\n"
                content += f"@pxt.{self.entity_type}\n"
                sig_str = str(sig)
                # Inject default parameter values into the signature
                if len(func.signatures) == 1:
                    # TODO: Defaults for polymorphic fns
                    sig_str = self._inject_defaults_into_signature(func, sig_str)
                # Format signature with line breaks after commas for readability
                formatted_sig = self._format_signature(sig_str)
                content += f"{func_name}{formatted_sig}\n"
                if i < len(func.signatures):
                    content += "\n"

        elif hasattr(func, "call_output_schema"):
            # 2.0-style iterator
            content += "Signature\n@pxt.iterator\n"
            sig = func.signature
            sig_str = str(sig)
            sig_str = self._inject_defaults_into_signature(func, sig_str)
            formatted_sig = self._format_signature(sig_str)
            # Don't include return type (which currently is always an unhelpful pxt.Json)
            formatted_sig = formatted_sig.removesuffix(" -> pxt.Json")
            content += f"{func_name}{formatted_sig}\n"

        else:
            # Fall back to standard introspection
            assert isinstance(func, Callable)
            overloads = get_overloads(func)
            if len(overloads) > 1:
                content += "Signatures\n"
            else:
                content += "Signature\n"

            for i, overload_fn in enumerate(overloads or [func], 1):
                if len(overloads) > 1:
                    content += f"# Signature {i}:\n"
                sig = inspect.signature(overload_fn)
                params = list(sig.parameters.values())
                if self.default_name == 'method' and params and params[0].name in ('self', 'cls'):
                    params = params[1:]
                    sig = sig.replace(parameters=params)
                if self.entity_type == 'iterator':
                    # Hack: suppress boilerplate return type for iterators
                    # TODO: When we refactor iterators, this hack can be removed
                    sig = sig.replace(return_annotation=inspect._empty)
                # Format signature with line breaks after commas for readability
                formatted_sig = self._format_signature(str(sig))
                content += f"{func_name}{formatted_sig}\n"
                if i < len(overloads):
                    content += "\n"

        content += "```\n\n"
        return content

    def _inject_defaults_into_signature(self, func: Any, sig_str: str) -> str:
        """Inject default parameter values and keyword-only separator into a signature string.

        Args:
            func: The function object
            sig_str: The signature string (e.g., "(audio: Audio, model: str) -> Json")

        Returns:
            Modified signature string with defaults and * separator
            (e.g., "(audio: Audio, *, model: str = 'whisper-1') -> Json")
        """
        # For UDFs and decorated functions, inspect.signature may return wrapper signature
        # Try to get the actual signature if available
        actual_func = func
        if hasattr(func, '__wrapped__'):
            actual_func = func.__wrapped__
        elif hasattr(func, 'call_output_schema'):
            actual_func = func.decorated_callable
        elif hasattr(func, 'py_fn'):
            # Pixeltable UDF pattern - get the original Python function
            actual_func = func.py_fn

        # Use inspect.signature to get actual parameter information
        sig = inspect.signature(actual_func)

        assert "(" in sig_str and ")" in sig_str

        # Find return type annotation
        return_type = ""
        if "->" in sig_str:
            return_type = sig_str[sig_str.rindex("->"):]
            sig_str = sig_str[:sig_str.rindex("->")].strip()

        # Extract parameter section
        params_start = sig_str.index("(")
        params_end = sig_str.rindex(")")
        params_str = sig_str[params_start + 1:params_end].strip()

        if len(params_str) == 0:
            return sig_str + (" " + return_type if return_type else "")

        # Parse existing parameters from the signature string to preserve type annotations
        # Map parameter name -> type annotation string
        param_types = {}
        for param_str in params_str.split(","):
            param_str = param_str.strip()
            if not param_str or param_str == "*":
                continue

            if ":" in param_str:
                param_name = param_str.split(":")[0].strip()
                param_type = param_str.split(":", 1)[1].strip()
                param_types[param_name] = param_type
            else:
                param_name = param_str.strip()
                param_types[param_name] = None

        # Reconstruct signature using inspect.signature parameter order and kinds
        param_parts = []
        seen_keyword_only = False
        matched_params = 0

        for param_name, param in sig.parameters.items():
            if param_name == '_runtime_ctx':
                continue

            assert (
                param_name in param_types or param.kind in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD)
            ), f'{sig_str}: {param_name} not in {param_types}'

            # Skip if this parameter is not in the original signature string
            matched_params += 1

            # Insert * separator before first keyword-only parameter
            if param.kind == inspect.Parameter.KEYWORD_ONLY and not seen_keyword_only:
                param_parts.append("*")
                seen_keyword_only = True

            # Build parameter string with type annotation
            if param.kind == inspect.Parameter.VAR_POSITIONAL:
                param_str = f"*{param_name}"
            elif param.kind == inspect.Parameter.VAR_KEYWORD:
                param_str = f"**{param_name}"
            else:
                param_str = param_name

            if param_types.get(param_name):
                param_str += f": {param_types[param_name]}"

            # Add default value if present
            if param.default != inspect.Parameter.empty:
                param_str += f" = {param.default!r}"

            param_parts.append(param_str)

        # If we couldn't match any parameters, return original signature
        # This happens when inspect.signature returns decorator wrapper params
        if matched_params == 0:
            return f"({params_str})" + (" " + return_type if return_type else "")

        # Reconstruct the signature
        new_params_str = ", ".join(param_parts)
        result = f"({new_params_str})"
        if return_type:
            result += " " + return_type

        return result

    def _wrap_code_line(self, line: str) -> str:
        """Wrap code lines beautifully at logical break points."""
        # Handle function calls with parameters
        if "(" in line and ")" in line:
            # Find the function name and opening paren
            func_start = line[: line.index("(") + 1]
            params = line[line.index("(") + 1 : line.rindex(")")]
            func_end = line[line.rindex(")") :]

            # Split parameters at commas
            param_parts = []
            depth = 0
            current = []

            for char in params:
                if char in "([{":
                    depth += 1
                elif char in ")]}":
                    depth -= 1
                elif char == "," and depth == 0:
                    param_parts.append("".join(current).strip())
                    current = []
                    continue
                current.append(char)

            if current:
                param_parts.append("".join(current).strip())

            # Reconstruct with wrapping
            if len(param_parts) > 1:
                wrapped = func_start + "\n"
                for i, param in enumerate(param_parts):
                    wrapped += "    " + param
                    if i < len(param_parts) - 1:
                        wrapped += ",\n"
                wrapped += "\n" + func_end
                return wrapped

        return line

    def _run_doctest(self, code: str, module_context: dict = None) -> dict:
        """
        Stub method for running doctest examples and validating their output.

        This would use Python's doctest module to execute the code and verify output.
        For now, this is just a stub for future implementation.

        Args:
            code: The doctest code string (with >>> and ... prompts)
            module_context: Dict of globals/locals to run the code in (e.g., imported modules)

        Returns:
            Dict with:
                - 'passed': bool indicating if the test passed
                - 'output': actual output from running the code
                - 'expected': expected output from the doctest
                - 'error': any error message if the test failed

        Implementation notes:
            1. Parse the doctest string to extract code and expected output
            2. Create a temporary module or namespace
            3. Execute the code using doctest.run_docstring_examples() or similar
            4. Compare actual vs expected output
            5. Return results

        Example usage:
            result = self._run_doctest(
                ">>> 2 + 2\\n4",
                module_context={'numpy': numpy}
            )
            if result['passed']:
                print("Doctest passed!")
        """
        # TODO: Implement actual doctest execution
        # For now, just return a stub response
        return {
            "passed": True,
            "output": "",
            "expected": "",
            "error": None,
            "warning": "Doctest execution not yet implemented",
        }

    def _format_examples_from_meta(self, examples_meta: list[DocstringMeta]) -> str:
        """Format examples from parsed meta using improved doctest extraction."""
        if not examples_meta:
            return ""

        content = "**Examples:**\n\n"

        for meta in examples_meta:
            if meta.description:
                content += self._format_code_blocks(meta.description) + "\n\n"

        return content

    def _format_signature(self, sig_str: str) -> str:
        """Format function signature - delegates to base class."""
        return super()._format_signature(sig_str, default_name=self.default_name)
