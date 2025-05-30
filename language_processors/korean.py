import re


def normalize_text(text):
    """Normalizes all types of whitespace characters to regular spaces."""
    return re.sub(r"\s+", " ", text).strip()


def process_text(text):
    try:
        from num2words import num2words
    except ImportError:
        raise ImportError(
            "num2words package is required. Please run 'pip install num2words'"
        )

    text = normalize_text(text)

    # Convert numbers to Korean words (add spaces before and after)
    text = re.sub(r"\d+", lambda m: f" {num2words(int(m.group()), lang='ko')} ", text)

    # Unify consecutive spaces into one
    text = re.sub(r"\s+", " ", text).strip()

    return text


# Korean match
korean_match = re.compile(r"[가-힣]+")


def transliterate(sentence, epi, eng_epi=None):
    sentence = process_text(sentence)
    current_sentence = ""
    current_eng_sentence = ""
    ipa = ""
    for ch in sentence:
        # Check if it's an English character
        if ch.isascii() and (
            ch.isalpha() or ch.isspace()
        ):  # If it's alphabet or space and not Korean (special characters, etc.)
            if (
                current_eng_sentence or ch.isalpha()
            ):  # If English has already started or this is an alphabet (beginning of English). If current_sentence is not empty, it means English has started
                current_eng_sentence += ch
                if current_sentence:
                    ipa += epi.transliterate(current_sentence)
                    current_sentence = ""
            else:  # Otherwise (special character not in the middle of English or space not in the middle of English)
                current_sentence += ch
            continue

        if current_eng_sentence:
            ipa += eng_epi.transliterate(current_eng_sentence)
            current_eng_sentence = ""

        current_sentence += ch

    # Finalize
    if current_eng_sentence:
        ipa += eng_epi.transliterate(current_eng_sentence)
    elif current_sentence:
        ipa += epi.transliterate(current_sentence)

    return ipa
