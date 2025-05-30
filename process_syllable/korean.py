from typing import List
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from process_syllable.english import split_syllables as eng_split
from language_processors.korean import process_text as ko_processor

def split_syllables(text: str) -> tuple[List[str], int]:
    # Preprocess text using ko_processor
    text = ko_processor(text)

    syllables = []
    count = 0
    current_eng_word = ""
    prev_ch = ""

    for ch in text:
        # Check if it's an English character
        if ch.isascii() and (ch.isalpha() or ch.isspace()):
            if current_eng_word or ch.isalpha():
                current_eng_word += ch
            continue

        # Process if there was an English word
        if current_eng_word:
            eng_words = current_eng_word.strip().split()
            for word in eng_words:
                if word:
                    eng_syllables, eng_count = split_syllables_english(word)
                    syllables.extend(eng_syllables)
                    count += eng_count
            current_eng_word = ""

        # Check if it's between '가'(U+AC00) and '힣'(U+D7A3)
        if "가" <= ch <= "힣":
            if prev_ch:
                syllables.append(f"{prev_ch}{ch}")
                prev_ch = ""
            else:
                syllables.append(ch)
            count += 1
        else:
            if syllables:
                syllables[-1] = syllables[-1] + ch
            else:
                prev_ch += ch

    # Process the last English word
    if current_eng_word:
        eng_words = current_eng_word.strip().split()
        for word in eng_words:
            if word:
                eng_syllables, eng_count = split_syllables_english(word)
                syllables.extend(eng_syllables)
                count += eng_count

    return syllables, count


def split_syllables_english(word: str) -> tuple[List[str], int]:
    """Splits English words into syllables and returns the count."""
    return eng_split(word)

