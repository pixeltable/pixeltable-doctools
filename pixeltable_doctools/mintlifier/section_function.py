"""Generate documentation sections for functions within module pages."""

import inspect
from typing import Any
from docstring_parser import parse as parse_docstring
from .page_base import PageBase
import textwrap

class FunctionSectionGenerator(PageBase):
    """Generate documentation sections for functions within module pages."""

    default_name: str

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

    def generate_section(self, func: Any, func_name: str, module_path: str, is_udf: bool = None) -> str:
        """Generate function documentation section for inline use.

        Args:
            func: The function object to document
            func_name: Name of the function
            module_path: Full module path (e.g., 'pixeltable.functions.image')
            is_udf: If True, add UDF label; if False, no label; if None, auto-detect (deprecated)

        Returns:
            Markdown string for the function documentation
        """
        full_path = f"{module_path}.{func_name}"

        # Build section content with elegant visual separation
        content = "\n"

        # Use explicit is_udf if provided, otherwise fall back to detection (deprecated)
        if is_udf is None:
            is_udf = self._is_udf(func)

        if is_udf:
            content += f"## `udf` {func_name}()\n\n"
        else:
            content += f"## `{self.default_name}` {func_name}()\n\n"

        # Add signature
        content += self._document_signature(func, func_name)

        # Add description
        doc = inspect.getdoc(func)
        if doc:
            parsed = parse_docstring(doc)
            if parsed.description:
                content += f"{self._escape_mdx(parsed.description)}\n\n"

        # Add parameters
        if doc:
            content += self._document_parameters(func, doc)

        # Add returns
        if doc:
            parsed = parse_docstring(doc)
            if parsed and parsed.returns:
                content += self._document_returns(parsed, func)

        # Add examples using docstring_parser
        if doc:
            parsed = parse_docstring(doc)
            examples_meta = [m for m in parsed.meta if m.args and "examples" in m.args[0].lower()]
            if examples_meta:
                content += self._format_examples_from_meta(examples_meta)

        return content

    def _document_signature(self, func: Any, func_name: str) -> str:
        """Document function signature."""
        content = "```python\n"

        if hasattr(func, "signatures"):
            # Pixeltable UDF
            for i, sig in enumerate(func.signatures, 1):
                if len(func.signatures) > 1:
                    content += f"# Signature {i}:\n"
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

        else:
            # Fall back to standard introspection
            sig = inspect.signature(func)
            params = list(sig.parameters.values())
            if self.default_name == 'method' and params and params[0].name in ('self', 'cls'):
                params = params[1:]
                sig = sig.replace(parameters=params)
            # Format signature with line breaks after commas for readability
            formatted_sig = self._format_signature(str(sig))
            content += f"{func_name}{formatted_sig}\n"

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
        try:
            # For UDFs and decorated functions, inspect.signature may return wrapper signature
            # Try to get the actual signature if available
            actual_func = func
            if hasattr(func, '__wrapped__'):
                actual_func = func.__wrapped__
            elif hasattr(func, 'py_fn'):
                # Pixeltable UDF pattern - get the original Python function
                actual_func = func.py_fn

            # Use inspect.signature to get actual parameter information
            sig = inspect.signature(actual_func)

            # Extract the parameters part from the signature string
            if "(" not in sig_str or ")" not in sig_str:
                return sig_str

            # Find return type annotation
            return_type = ""
            if "->" in sig_str:
                return_type = sig_str[sig_str.rindex("->"):]
                sig_str = sig_str[:sig_str.rindex("->")].strip()

            # Extract parameter section
            params_start = sig_str.index("(")
            params_end = sig_str.rindex(")")
            params_str = sig_str[params_start + 1:params_end].strip()

            if not params_str:
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
                # Skip if this parameter is not in the original signature string
                if param_name not in param_types:
                    continue

                matched_params += 1

                # Insert * separator before first keyword-only parameter
                if param.kind == inspect.Parameter.KEYWORD_ONLY and not seen_keyword_only:
                    param_parts.append("*")
                    seen_keyword_only = True

                # Build parameter string with type annotation
                param_str = param_name
                if param_types[param_name]:
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

        except (ValueError, TypeError, AttributeError):
            # If anything goes wrong, return original signature
            return sig_str

    def _document_parameters(self, func: Any, doc: str) -> str:
        """Document function parameters."""
        parsed = parse_docstring(doc)
        if not parsed or not parsed.params:
            return ""

        content = "**Parameters:**\n\n"

        # Get signature for default values and type annotations
        params_with_defaults = {}
        params_with_types = {}
        try:
            # For polymorphic functions, document ALL parameter variants
            if hasattr(func, "is_polymorphic") and func.is_polymorphic and hasattr(func, "signatures"):
                # Collect all unique parameters from all signatures
                all_params = {}
                for sig in func.signatures:
                    if hasattr(sig, "parameters"):
                        for param_name, param in sig.parameters.items():
                            if param_name not in all_params:
                                # Store first occurrence of each param
                                all_params[param_name] = param
                                if hasattr(param, "col_type"):
                                    params_with_types[param_name] = str(param.col_type)
                                if hasattr(param, "default") and param.default is not None:
                                    params_with_defaults[param_name] = param.default
            # For regular Pixeltable functions, parse the signature string
            elif hasattr(func, "signature") and func.signature:
                # Parse signature string like "(audio: Audio) -> Json"
                sig_str = str(func.signature)
                # Extract parameters from the string
                if "(" in sig_str and ")" in sig_str:
                    params_str = sig_str[sig_str.index("(") + 1 : sig_str.index(")")]
                    if params_str:
                        for param in params_str.split(","):
                            param = param.strip()
                            if ":" in param:
                                name, type_str = param.split(":", 1)
                                params_with_types[name.strip()] = type_str.strip()
            else:
                # Standard introspection
                sig = inspect.signature(func)
                for param_name, param in sig.parameters.items():
                    if param.default != inspect.Parameter.empty:
                        params_with_defaults[param_name] = param.default
                    if param.annotation != inspect.Parameter.empty:
                        params_with_types[param_name] = param.annotation
        except (ValueError, TypeError):
            pass

        for param in parsed.params:
            # Format parameter
            type_str = params_with_types.get(param.arg_name, param.type_name or "Any")
            # Clean up type strings that break MDX
            if type_str:
                import re

                # Convert to string first if it's not already
                type_str = str(type_str)
                # Remove <class '...'> format
                type_str = re.sub(r"<class '([^']+)'>", r"\1", type_str)
            default = params_with_defaults.get(param.arg_name)

            content += f"- **`{param.arg_name}`** "
            if type_str:
                content += f"(`{type_str}`"
                if default is not None:
                    content += f", default: `{default!r}`"
                content += ")"

            # Format description with proper nesting for bullet points
            if param.description:
                escaped = self._escape_mdx(param.description)
                indented = textwrap.indent(escaped, "    ").strip()
                content += f': {indented}'
            content += "\n"

        content += "\n"
        return content

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

    def _extract_doctest_examples(self, text: str) -> list:
        """
        Extract doctest examples from text.

        Groups consecutive >>> blocks as single examples when they're part of the
        same logical operation (e.g., defining a variable then using it).

        Returns a list of dicts with 'description', 'code', and 'output' keys.
        """

        examples = []
        lines = text.split("\n")
        current_example = {"description": "", "code": "", "output": ""}
        in_code = False
        code_lines = []

        i = 0
        while i < len(lines):
            line = lines[i]

            # Check if line starts a doctest
            if line.strip().startswith(">>>"):
                if not in_code:
                    # Starting a new code block
                    in_code = True

                # Remove the >>> prompt and add to code
                code_line = line.strip()[4:]
                code_lines.append(code_line)

            elif line.strip().startswith("..."):
                # Continuation of previous code line
                if in_code:
                    code_line = line.strip()[4:]
                    code_lines.append(code_line)

            elif in_code:
                # We're in a code block and hit a non-code line
                if line.strip() == "":
                    # Empty line - check what comes next
                    if i + 1 < len(lines):
                        next_line = lines[i + 1].strip()
                        if next_line.startswith(">>>"):
                            # Another >>> immediately after - continue same example
                            pass
                        elif next_line == "":
                            # Double blank line - end of example
                            in_code = False
                            if code_lines:
                                current_example["code"] = "\n".join(code_lines)
                                examples.append(current_example)
                                current_example = {"description": "", "code": "", "output": ""}
                                code_lines = []
                        else:
                            # Text after blank line - end of code block
                            in_code = False
                            if code_lines:
                                current_example["code"] = "\n".join(code_lines)
                                examples.append(current_example)
                                current_example = {"description": "", "code": "", "output": ""}
                                code_lines = []
                    else:
                        # End of text
                        in_code = False
                else:
                    # Non-empty, non-code line - this would be output in a real doctest
                    # For now, we'll treat it as end of code block
                    in_code = False
                    if code_lines:
                        current_example["code"] = "\n".join(code_lines)
                        examples.append(current_example)
                        current_example = {"description": "", "code": "", "output": ""}
                        code_lines = []

            # Not in code - this is descriptive text
            elif line.strip():
                # Add to description
                if current_example["description"]:
                    current_example["description"] += " "
                current_example["description"] += line.strip()

            i += 1

        # Don't forget the last example
        if code_lines:
            current_example["code"] = "\n".join(code_lines)
            examples.append(current_example)

        # Filter out empty examples
        examples = [ex for ex in examples if ex["code"] or ex["description"]]

        return examples

    def _format_examples_from_meta(self, examples_meta) -> str:
        """Format examples from parsed meta using improved doctest extraction."""
        if not examples_meta:
            return ""

        content = "**Examples:**\n\n"

        for meta in examples_meta:
            if meta.description:
                # Use docstring_parser's Numpy example parser's approach to extract doctest examples
                examples = self._extract_doctest_examples(meta.description)

                for example in examples:
                    if example["description"]:
                        content += f"{example['description']}\n"

                    if example["code"]:
                        # Format the code using ruff for consistent line breaks
                        content += "```python\n"
                        content += example["code"]
                        content += "\n```\n"

                    if example["output"]:
                        # Optionally show output as a comment or separate block
                        # For now, we'll skip output to keep it clean
                        pass

                    content += "\n"

        return content

    def _extract_and_format_examples(self, doc: str) -> str:
        """Extract and format examples from docstring."""
        # Find the Examples section - use simpler pattern that works!
        import re

        pattern = r"Examples?:(.*?)$"
        match = re.search(pattern, doc, re.DOTALL | re.IGNORECASE)

        if not match:
            return ""

        examples_text = match.group(2).strip()
        if not examples_text:
            return ""

        # Format with glamour but subtle headers!
        content = "**Examples:**\n\n"

        # Clean up the example text
        lines = examples_text.split("\n")
        in_code_block = False
        formatted_lines = []

        for line in lines:
            # Check if this looks like code (starts with >>> or has significant indentation)
            if line.strip().startswith(">>>") or (line and line[0] == " " * 4):
                if not in_code_block:
                    formatted_lines.append("\n```python")
                    in_code_block = True
                # Clean up the >>> prompt if present
                clean_line = line.replace(">>>", "").replace("...", "   ")
                formatted_lines.append(clean_line)
            else:
                if in_code_block:
                    formatted_lines.append("```\n")
                    in_code_block = False
                if line.strip():  # Only add non-empty lines outside code blocks
                    formatted_lines.append(line.strip())

        if in_code_block:
            formatted_lines.append("```")

        content += "\n".join(formatted_lines)
        content += "\n\n"

        return content

    def _document_examples(self, parsed) -> str:
        """Document examples."""
        if not hasattr(parsed, "examples") or not parsed.examples:
            return ""

        content = "**Examples:**\n\n"

        for example in parsed.examples:
            if example.description:
                content += f"{self._escape_mdx(example.description)}\n\n"
            if example.snippet:
                content += f"```python\n{example.snippet}\n```\n\n"

        return content

    def _format_signature(self, sig_str: str) -> str:
        """Format function signature - delegates to base class."""
        return super()._format_signature(sig_str, default_name=self.default_name)
