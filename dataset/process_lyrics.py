import argparse
import os
from typing import Dict, List, Union
import json
import jieba
import MeCab
import re


LANG_LIST = ["US", "ES", "FR", "KR", "JP"]

def clean_special_characters(word: str) -> str:
    """
    Remove special characters from the beginning and end of a word.
    If the word consists only of special characters, keep it as is.
    
    Args:
        word: Input word
        
    Returns:
        Cleaned word
    """
    if not word:
        return word
    
    # Check if the word consists only of special characters
    if re.match(r'^[^\w\s]+$', word):
        return word
    
    # Remove special characters from beginning and end
    cleaned = re.sub(r'^[^\w]+|[^\w]+$', '', word)
    return cleaned if cleaned else word


def transform_lyrics_english(text: str) -> List[List[str]]:
    """
    # Transform English lyrics according to copyright regulations
    "Remember me though I have to say goodbye" -> ["RmtIhtsg", "Remember", "goodbye"]

    Args:
        text: Original lyrics text

    Returns:
        Transformed lyrics representation
    """
    result = []
    lines = text.strip().split("\n")

    for line in lines:
        # "..." -> "... " (add space after . or ,)
        line = re.sub(r'(\.|\,|:)+', lambda m: m.group() + ' ', line)
        line = line.strip()
        if not line:
            continue

        words = [clean_special_characters(w) for w in line.split()]
        
        # Process words to attach special character-only words to previous word
        processed_words = []
        for word in words:
            if not word:  # Skip empty strings
                continue
            
            # Check if word consists only of special characters
            if re.match(r'^[^\w\s]+$', word):
                # If there's a previous word, attach to it
                if processed_words:
                    processed_words[-1] += word
                # If no previous word, skip this special character word
            else:
                processed_words.append(word)
        
        if not processed_words:
            continue

        if len(processed_words) == 1:
            # If there is only one word, save only the first letter and the word itself
            first_letter = processed_words[0][0] if processed_words[0] else ""
            result.append([first_letter, processed_words[0]])
        else:
            # Extract the first letter of each word
            first_letters = "".join(w[0] for w in processed_words if w)

            # First word and last word
            first_word = processed_words[0]
            last_word = processed_words[-1]

            result.append([first_letters, first_word, last_word])

    return result

def transform_lyrics_japanese(text: str) -> List[List[str]]:
    """
    # Transform Japanese lyrics according to copyright regulations
    # Process by grouping every 3 characters after removing all spaces

    Args:
        text: Original lyrics text

    Returns:
        Transformed lyrics representation
    """
    result = []
    lines = text.strip().split("\n")

    for line in lines:
        # Normalize punctuation
        line = line.replace("（", "(")
        line = line.replace("）", ")")
        line = line.replace("！", "!")
        line = line.replace("？", "?")
        line = line.replace("．", ".")
        line = line.replace("，", ",")
        line = line.replace("：", ":")
        line = line.replace("；", ";")
        line = line.replace("「", '"')
        line = line.replace("」", '"')
        line = line.replace("『", '"')
        line = line.replace("』", '"')
        line = line.replace("〜", "~")
        line = line.replace("－", "-")
        
        # Remove all spaces and whitespace characters
        line = re.sub(r'\s+', '', line)
        line = re.sub(r'[\u200b\u200c\u200d\ufeff\u3000]', '', line)
        
        if not line:
            continue

        # Group characters by 3
        grouped_chars = []
        for i in range(0, len(line), 3):
            group = line[i:i+3]
            if group:
                grouped_chars.append(group)

        if not grouped_chars:
            continue

        # First characters of each group and the first/last group
        first_chars = "".join(g[0] for g in grouped_chars if g and len(g) > 0)
        first_group = grouped_chars[0]
        last_group = grouped_chars[-1]

        result.append([first_chars, first_group, last_group])

    return result


def transform_lyrics(text: str, language: str) -> List[List[str]]:
    """
    # Transform lyrics according to copyright regulations

    Args:
        text: Original lyrics text
        language: Language code

    Returns:
        Transformed lyrics representation
    """
    if language == "CN":
        raise ValueError("Chinese lyrics are not supported")
    elif language == "JP":
        return transform_lyrics_japanese(text)
    else: # Default to English transformation for US_og, ES, FR, KR, and any other unspecified languages
        return transform_lyrics_english(text)


def process_lyrics(lyrics: Union[List, Dict]) -> Dict:
    # Handle both old dict format and new array format
    if isinstance(lyrics, list):
        # New array format - convert to dict for processing
        lyrics_dict = {}
        for song_item in lyrics:
            if "song_title" in song_item:
                song_key = song_item["song_title"]
                # Create song_data dict with all fields except song_title
                song_data = {k: v for k, v in song_item.items() if k != "song_title"}
                lyrics_dict[song_key] = song_data
        lyrics = lyrics_dict
    elif not isinstance(lyrics, dict):
        raise ValueError("Unexpected data format. Expected list or dict.")

    result_json = {}
    for song_key, song_data in lyrics.items():
        print(f"Title: {song_key}")
        result_json[song_key] = {
            "lyrics": [],
            "youtube_url": {},
            "lyrics_url": {},
            "video": {},
        }

        # Copy only US, ES, FR, KR, JP for YouTube URL, lyrics URL and video
        if "youtube_url" in song_data:
            for lang in LANG_LIST:
                if lang in song_data["youtube_url"]:
                    result_json[song_key]["youtube_url"][lang] = song_data["youtube_url"][lang]
        if "lyrics_url" in song_data:
            for lang in LANG_LIST:
                if lang in song_data["lyrics_url"]:
                    result_json[song_key]["lyrics_url"][lang] = song_data["lyrics_url"][lang]
        if "video" in song_data:
            for lang in LANG_LIST:
                if lang in song_data["video"]:
                    result_json[song_key]["video"][lang] = song_data["video"][lang]

        # Process lyrics
        processed_lyrics = []

        for verse in song_data.get("lyrics", []):
            processed_verse = []

            for line_data in verse:
                processed_line = {}
                for lang, lang_data in line_data.items():
                    # Transform text field for copyright protection
                    if lang not in LANG_LIST:
                        continue
                    if "text" in lang_data:
                        text = lang_data["text"]
                        transformed = transform_lyrics(text, lang)
                        start_time = lang_data.get("start", -1)
                        end_time = lang_data.get("end", -1)
                        processed_line[lang] = {
                            "text": transformed,
                            "line_number": lang_data["line_number"],
                            "syllable_count": lang_data["syllable_count"],
                        }
                        if start_time != -1 and end_time != -1:
                            processed_line[lang]["start"] = start_time
                            processed_line[lang]["end"] = end_time

                processed_verse.append(processed_line)

            processed_lyrics.append(processed_verse)

        result_json[song_key]["lyrics"] = processed_lyrics

    return result_json


def main(lyrics_path: str, output_path: str):
    # read the file
    with open(lyrics_path, "r", encoding="utf-8") as f:
        lyrics = json.load(f)

    # process the lyrics
    processed_lyrics = process_lyrics(lyrics)

    # write the processed lyrics to the output file
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(processed_lyrics, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--lyrics_path", type=str, default="mavl_dataset.json")
    parser.add_argument("--output_path", type=str, default="copyright_protected_lyrics.json")
    args = parser.parse_args()

    main(args.lyrics_path, args.output_path)
