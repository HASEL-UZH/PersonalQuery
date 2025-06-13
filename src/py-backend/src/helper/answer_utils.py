import re


def convert_bracket_to_dollar_latex(text: str) -> str:
    """Replaces LaTeX math blocks with $$ $$ for frontend display compatibility."""
    return re.sub(r'\\\[(.*?)\\\]', r'$$\1$$', text, flags=re.DOTALL)