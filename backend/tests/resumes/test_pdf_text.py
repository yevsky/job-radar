import pytest

from app.services.resume import MAX_PDF_PAGES, ResumeFileError, pdf_text
from tests.resumes.pdf import make_pdf


def test_reads_the_text_of_every_page() -> None:
    text = pdf_text(make_pdf('Python developer\n2 years', 'Skills: FastAPI (and Docker)'))
    assert text == 'Python developer\n2 years\n\nSkills: FastAPI (and Docker)'


def test_empty_pages_are_skipped() -> None:
    assert pdf_text(make_pdf('First', '', 'Third')) == 'First\n\nThird'


@pytest.mark.parametrize(
    ('content', 'message'),
    [
        (b'Hello, I am a text file', 'not a PDF'),
        (b'', 'not a PDF'),
        (b'%PDF-1.4 and then garbage', 'could not be read'),
        (make_pdf()[:200], 'could not be read'),  # cut off in the middle
        (make_pdf(), 'no text'),  # like a scanned CV
        (make_pdf(*['page'] * (MAX_PDF_PAGES + 1)), 'more than'),
    ],
    ids=['text', 'empty', 'garbage', 'cut', 'no-text', 'too-many-pages'],
)
def test_unreadable_files_raise_a_clear_error(content: bytes, message: str) -> None:
    with pytest.raises(ResumeFileError, match=message):
        pdf_text(content)


@pytest.mark.parametrize(
    ('drawn', 'expected'),
    [
        ('Wroc\x01law, Poland', 'Wrocław, Poland'),
        ('\x01Lukasz Ma\x01lecki', 'Łukasz Małecki'),
    ],
)
def test_latex_letter_l_with_stroke_is_read(drawn: str, expected: str) -> None:
    """LaTeX CVs draw "ł" as a "suppress" stroke plus "l"; pypdf gives 'Wroc/suppresslaw'."""
    assert pdf_text(make_pdf(drawn, tex_font=True)) == expected
