"""Tiny PDFs for tests, built by hand: one page per string, with a real text layer."""


def escape(text: str) -> str:
    return text.replace('\\', '\\\\').replace('(', '\\(').replace(')', '\\)')


# A LaTeX font's trick for "ł": character 1 is the glyph "suppress" (a stroke over the next l)
TEX_ENCODING = b' /Encoding << /Type /Encoding /Differences [1 /suppress] >>'


def make_pdf(*pages: str, tex_font: bool = False) -> bytes:
    """A valid PDF whose pages show the given text (ASCII; one line per '\\n').

    make_pdf() gives a page with no text at all, like a scanned CV without a text layer.
    tex_font=True draws "\\x01" as the LaTeX "suppress" glyph, the stroke of "ł":
    make_pdf("Wroc\\x01law", tex_font=True) reads as "Wrocław".
    """
    pages = pages or ('',)
    page_ids = [3 + 2 * n for n in range(len(pages))]
    font_id = 3 + 2 * len(pages)
    objects: dict[int, bytes] = {
        1: b'<< /Type /Catalog /Pages 2 0 R >>',
        2: f'<< /Type /Pages /Kids [{" ".join(f"{i} 0 R" for i in page_ids)}] '
        f'/Count {len(pages)} >>'.encode(),
        font_id: b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica'
        + (TEX_ENCODING if tex_font else b'')
        + b' >>',
    }
    for page_id, text in zip(page_ids, pages, strict=True):
        lines = ' T* '.join(f'({escape(line)}) Tj' for line in text.split('\n') if line)
        stream = f'BT /F1 12 Tf 14 TL 72 720 Td {lines} ET'.encode() if lines else b''
        objects[page_id] = (
            f'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents {page_id + 1} 0 R '
            f'/Resources << /Font << /F1 {font_id} 0 R >> >> >>'
        ).encode()
        objects[page_id + 1] = b'<< /Length %d >>\nstream\n' % len(stream) + stream + b'\nendstream'

    out = bytearray(b'%PDF-1.4\n')
    offsets = {}
    for number in sorted(objects):
        offsets[number] = len(out)
        out += b'%d 0 obj\n' % number + objects[number] + b'\nendobj\n'
    xref = len(out)
    size = max(objects) + 1
    out += b'xref\n0 %d\n0000000000 65535 f \n' % size
    for number in range(1, size):
        out += b'%010d 00000 n \n' % offsets[number]
    out += b'trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n' % (size, xref)
    return bytes(out)
