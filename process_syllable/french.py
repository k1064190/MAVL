# syllabify-fr
import re
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from language_processors.french import process_text as fr_processor


def _char_at(s: str, i: int) -> str:
    """Returns an empty string if it's out of bounds, same as JavaScript's charAt"""
    if 0 <= i < len(s):
        return s[i]
    return ""


def _substring(s: str, start: int, end: int) -> str:
    """
    Similar to JavaScript's substring, automatically handles out-of-bounds ranges
    through slicing (Python doesn't raise an IndexError).
    """
    return s[start:end]


def split_syllables(s: str) -> tuple[list[str], int]:

    # Preprocess text using fr_processor
    s = fr_processor(s)

    # Word separation logic
    words = re.findall(r"[a-zA-ZÀ-ÿ]+(?:'[a-zA-ZÀ-ÿ]+)?", s)

    count = 0
    syllables = []
    for w in words:
        sylls, cnt = syllabify(w)
        syllables.extend(sylls)
        count += cnt
    return syllables, count


def syllabify(s: str) -> tuple[list[str], int]:
    """
    French syllabic splitter by Bilgé Kimyonok
    Converted original (TypeScript) code to Python.
    The TypeScript logic has been transferred as faithfully as possible to perform the same function.

    :param s: Word to analyze
    :return: List divided into syllables, actual number of syllables cut
    """
    # Specific exception handling
    if s.lower() == "pays":
        return ["pa", "ys"], 2

    # If there are no alphabetic characters
    if not s.strip() or not any(ch.isalpha() for ch in s):
        return [], 0

    consonnes = [
        "b",
        "B",
        "c",
        "C",
        "ç",
        "Ç",
        "d",
        "D",
        "f",
        "F",
        "g",
        "G",
        "h",
        "H",
        "j",
        "J",
        "k",
        "K",
        "l",
        "L",
        "m",
        "M",
        "n",
        "N",
        "ñ",
        "Ñ",
        "p",
        "P",
        "q",
        "Q",
        "r",
        "R",
        "s",
        "S",
        "t",
        "T",
        "v",
        "V",
        "w",
        "W",
        "x",
        "X",
        "y",
        "Y",
        "z",
        "Z",
        "-",
    ]

    voyellesFortes = [
        "a",
        "A",
        "á",
        "Á",
        "à",
        "À",
        "â",
        "Â",
        "e",
        "E",
        "é",
        "É",
        "è",
        "È",
        "ê",
        "Ê",
        "í",
        "Í",
        "o",
        "ó",
        "O",
        "Ó",
        "ô",
        "Ô",
        "ú",
        "Ú",
    ]

    voyellesFaibles = [
        "i",
        "I",
        "u",
        "U",
        "ü",
        "Ü",
        "ï",
        "Ï",
        "î",
        "Î",
        "û",
        "Û",
    ]

    e_list = ["e"]

    # 'y', 'Y' are also treated as vowels
    voyelles = voyellesFortes + voyellesFaibles + ["y", "Y"]

    nb = 0
    coupure = 0
    max_extra = 0  # Variable name 'max' changed as it can overlap with built-in function
    j = 0
    n = len(s) - 1
    i = 0
    syllabes = []

    while i <= n:
        coupure = 0  # 0 means do not cut
        c_i = _char_at(s, i)
        c_i1 = _char_at(s, i + 1)
        c_i_1 = _char_at(s, i - 1)

        if c_i in consonnes:
            # Current character is a consonant
            if c_i1 in voyelles:
                # If "y" is used as a consonant, diaeresis can be added
                if c_i.lower() == "y":
                    max_extra += 1
                if c_i_1 in voyelles:
                    coupure = 1
            else:
                # ( s, S ) + ( n, N ) + consonant => coupure = 2
                if (
                    (c_i.lower() == "s")
                    and (c_i_1.lower() == "n")
                    and (c_i1 in consonnes)
                ):
                    coupure = 2
                # consonant + consonant & previous letter is a vowel => specific logic
                elif (c_i1 in consonnes) and (c_i_1 in voyelles):
                    c_i1_lower = c_i1.lower()
                    if c_i1_lower in ["r", "l", "h"]:
                        # r, l, h require additional separation
                        # r, R
                        if c_i1_lower == "r":
                            if c_i.lower() in [
                                "b",
                                "c",
                                "d",
                                "f",
                                "g",
                                "k",
                                "p",
                                "r",
                                "t",
                                "v",
                            ]:
                                coupure = 1
                            else:
                                coupure = 2
                        # l, L
                        elif c_i1_lower == "l":
                            if c_i.lower() in [
                                "b",
                                "c",
                                "d",
                                "f",
                                "g",
                                "k",
                                "l",
                                "p",
                                "t",
                                "v",
                            ]:
                                coupure = 1
                            else:
                                coupure = 2
                        # h, H
                        else:  # 'h'
                            if c_i.lower() in ["c", "s", "p"]:
                                coupure = 1
                            else:
                                coupure = 2
                    else:
                        # If t, p and s appear consecutively (e.g., "verts" / "corps") -> coupure=0
                        c_i2 = _char_at(s, i + 2).lower()
                        if (c_i1_lower in ["t", "p"]) and (c_i2 == "s"):
                            coupure = 0
                        else:
                            coupure = 2
        elif c_i in voyellesFortes:
            # Strong vowel
            c_i_1_2 = _substring(s.lower(), i - 2, i)
            c_i_12 = _substring(s.lower(), i - 1, i + 2)
            c_i_11 = _substring(s.lower(), i - 1, i + 1)
            c_i_14 = _substring(s.lower(), i + 1, i + 4)

            # If previous letter is a strong vowel and not a specific exception case -> coupure=1
            if (
                c_i_1.lower() in voyellesFortes
                and c_i_1_2 != "ge"
                and c_i_12 != "eau"
                and c_i_11 != "oe"
                and (
                    "ée" not in c_i_12 or ("ées" not in c_i_14 and "éent" not in c_i_14)
                )
            ):
                coupure = 1
        elif c_i in voyellesFaibles:
            # Weak vowel + diaeresis judgment
            c_i_1_1 = _substring(s.lower(), i - 1, i + 1)
            if c_i_1_1 not in ["qu", "gu"]:
                # "qu", "gu" are processed together
                c_i1_lower = _char_at(s, i + 1).lower()
                c_i_12 = _substring(s.lower(), i + 1, i + 4)
                c_i_02 = _substring(s.lower(), i, i + 2)

                # Diaeresis (obligatory): if two consonants precede
                c_i_2 = _char_at(s, i - 2)
                c_i_3 = _char_at(s, i - 3)
                if (
                    c_i1_lower in voyelles
                    and c_i_2 in consonnes
                    and c_i_3 in consonnes
                    and c_i_02 != "ui"
                ):
                    # Add if vowel follows y
                    if c_i1_lower == "y":
                        max_extra += 1
                    coupure = 2
                else:
                    # Diaeresis (optional)
                    if c_i1_lower in voyelles and (
                        ("ent" not in c_i_12 and "es" not in c_i_12) or c_i_02 != "ui"
                    ):
                        max_extra += 1

        # Decide whether to actually cut
        if coupure == 1:
            # Make the part up to the current position a syllable
            voy = s[j:i]
            syllabes.append(voy)
            j = i
        elif coupure == 2:
            # Cut right after the current position
            i += 1
            voy = s[j:i]
            syllabes.append(voy)
            j = i

        i += 1

    nb = len(syllabes)
    # End processing
    if j == n and nb > 0 and _char_at(s, n) in consonnes:
        # If the last letter is a consonant, append it to the previous syllable.
        syllabes[nb - 1] += _char_at(s, n)
    else:
        # If the last letter is an 'e' type and there are other syllables, append it to the previous syllable
        if (
            nb > 0 and _char_at(s, n).lower() in e_list and j != 0
        ):  # Process only if j is not 0 (not the first letter)
            voy = s[j : n + 1]
            syllabes[nb - 1] += voy
        else:
            # Add the remaining string as the final syllable
            voy = s[j : n + 1]
            syllabes.append(voy)
            nb += 1

    return syllabes, nb

