SEPARATORS = ["\n\n", ". ", " "]


def _recursive_split(text: str, separators: list[str], max_chars: int) -> list[str]:
    if len(text) <= max_chars:
        return [text]

    if not separators:
        return [text[i : i + max_chars] for i in range(0, len(text), max_chars)]

    separator, *rest = separators
    raw_pieces = [p for p in text.split(separator) if p.strip()]

    # str.split() consumes the separator itself — reattach the period for
    # sentence splits so meaning/readability isn't silently destroyed
    if separator == ". " and len(raw_pieces) > 1:
        pieces = [p + "." for p in raw_pieces[:-1]] + [raw_pieces[-1]]
    else:
        pieces = raw_pieces

    chunks = []
    for piece in pieces:
        if len(piece) <= max_chars:
            chunks.append(piece)
        else:
            chunks.extend(_recursive_split(piece, rest, max_chars))
    return chunks


def _merge_small_pieces(pieces: list[str], min_chars: int, max_chars: int) -> list[str]:
    merged = []
    buffer = ""

    for piece in pieces:
        candidate = f"{buffer} {piece}".strip() if buffer else piece
        if len(candidate) <= max_chars:
            buffer = candidate
        else:
            if buffer:
                merged.append(buffer)
            buffer = piece

    if buffer:
        merged.append(buffer)

    # fold an undersized trailing chunk into its predecessor rather than
    # leaving a near-empty fragment as its own retrieval unit
    if len(merged) > 1 and len(merged[-1]) < min_chars:
        last = merged.pop()
        merged[-1] = f"{merged[-1]} {last}"

    return merged


def _sentence_boundary_overlap(previous_chunk: str, overlap_chars: int) -> str:
    """Last complete sentence(s) of previous_chunk, never a mid-word fragment."""
    sentences = [s.strip() for s in previous_chunk.split(". ") if s.strip()]
    selected: list[str] = []
    total = 0
    for sentence in reversed(sentences):
        selected.insert(0, sentence)
        total += len(sentence)
        if total >= overlap_chars:
            break
    return ". ".join(selected)


def _add_overlap(chunks: list[str], overlap_chars: int) -> list[str]:
    result = []
    for i, chunk in enumerate(chunks):
        if i == 0:
            result.append(chunk)
        else:
            prefix = _sentence_boundary_overlap(chunks[i - 1], overlap_chars)
            result.append(f"{prefix} {chunk}" if prefix else chunk)
    return result


def chunk_text(
    text: str,
    min_chars: int = 150,
    max_chars: int = 500,
    overlap_chars: int = 50,
) -> list[str]:
    raw_pieces = _recursive_split(text, SEPARATORS, max_chars)
    merged = _merge_small_pieces(raw_pieces, min_chars, max_chars)
    return _add_overlap(merged, overlap_chars)
