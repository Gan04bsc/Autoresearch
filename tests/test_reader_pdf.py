from litagent.reader import clean_extracted_text


def test_clean_extracted_text_replaces_invalid_surrogates() -> None:
    text = clean_extracted_text("valid \ud835 text")

    assert text == "valid ? text"
    text.encode("utf-8")
