from src.presentation.text_utils import (
    split_telegram_message,
    convert_markdown_to_telegram_html,
    strip_html_tags,
    render_progress_bar,
    format_progress_message,
)


def test_convert_markdown_to_telegram_html_escapes_raw_angles():
    raw = "В двух кейсах — УПД с количеством <0,005 и онлайн-платежи — патч `EF_00.cfe`: **точно**."
    converted = convert_markdown_to_telegram_html(raw)
    assert "&lt;0,005" in converted
    assert "<code>EF_00.cfe</code>" in converted
    assert "<b>точно</b>" in converted
    assert "<0,005" not in converted


def test_convert_markdown_to_telegram_html_preserves_valid_tags():
    raw = "Текст с <b>жирным</b> и <a href='https://t.me'>ссылкой</a> и формулой x < 5."
    converted = convert_markdown_to_telegram_html(raw)
    assert "<b>жирным</b>" in converted
    assert "href=" in converted
    assert "x &lt; 5" in converted


def test_strip_html_tags():
    html_text = "<b>Заголовок</b> &lt;0,005&gt; <a href='http://x.com'>ссылка</a>"
    plain = strip_html_tags(html_text)
    assert plain == "Заголовок <0,005> ссылка"


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


def test_render_progress_bar():
    assert render_progress_bar(0) == "[░░░░░░░░░░] 0%"
    assert render_progress_bar(20) == "[▓▓░░░░░░░░] 20%"
    assert render_progress_bar(50) == "[▓▓▓▓▓░░░░░] 50%"
    assert render_progress_bar(80) == "[▓▓▓▓▓▓▓▓░░] 80%"
    assert render_progress_bar(100) == "[▓▓▓▓▓▓▓▓▓▓] 100%"
    # Clamping
    assert render_progress_bar(-15) == "[░░░░░░░░░░] 0%"
    assert render_progress_bar(150) == "[▓▓▓▓▓▓▓▓▓▓] 100%"


def test_format_progress_message():
    msg = format_progress_message(50, "Адаптация текста")
    assert "<code>[▓▓▓▓▓░░░░░] 50%</code>" in msg
    assert "Адаптация текста" in msg

    msg_with_details = format_progress_message(75, "Генерация арта", details="Промпт <test> & more")
    assert "<code>[▓▓▓▓▓▓▓▓░░] 75%</code>" in msg_with_details
    assert "Промпт &lt;test&gt; &amp; more" in msg_with_details

