import math

def escape_md_cell(value: str) -> str:
    return f"`{value.replace('`', '')}`" if "|" in value or "\n" in value else value


def format_result_as_markdown(result: list[dict]) -> str:
    if not result:
        return "No results found"

    headers = list(result[0].keys())
    headers = ["#"] + headers  # Add row number header

    lines = ["| " + " | ".join(headers) + " |", "| " + " | ".join(["---"] * len(headers)) + " |"]

    for idx, row in enumerate(result, start=1):
        row_values = [str(idx)] + [escape_md_cell(str(value)) for value in row.values()]
        lines.append("| " + " | ".join(row_values) + " |")

    return "\n".join(lines)


def split_result(data: list[dict], max_chunk_size: int = 5000) -> list[list[dict]]:
    """
    Splits data into evenly sized chunks where each chunk has <= max_entries.
    """
    total = len(data)
    if total <= max_chunk_size:
        return [data]

    for num_chunks in range(2, total + 1):
        chunk_size = math.ceil(total / num_chunks)
        if chunk_size <= max_chunk_size:
            break

    return [data[i * chunk_size:(i + 1) * chunk_size] for i in range(num_chunks)]
