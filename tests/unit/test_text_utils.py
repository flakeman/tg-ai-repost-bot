from src.presentation.text_utils import split_telegram_message


def test_split_telegram_message_short():
    text = "Short message under limit"
    chunks = split_telegram_message(text, max_length=100)
    assert chunks == [text]


def test_split_telegram_message_empty():
    assert split_telegram_message("", max_length=100) == [""]


def test_split_telegram_message_paragraphs():
    p1 = "Paragraph 1 " * 10
    p2 = "Paragraph 2 " * 10
    full = f"{p1}\n\n{p2}"
    chunks = split_telegram_message(full, max_length=len(p1) + 10)
    assert len(chunks) == 2
    assert chunks[0] == p1.strip()
    assert chunks[1] == p2.strip()


def test_split_telegram_message_hard_cut():
    long_unbroken = "A" * 150
    chunks = split_telegram_message(long_unbroken, max_length=50)
    assert len(chunks) == 3
    assert all(len(c) <= 50 for c in chunks)
    assert "".join(chunks) == long_unbroken
