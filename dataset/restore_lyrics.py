import json
import os
import re
import string as std_string  # Import string module
import logging # Import logging module
import MeCab # Change back to MeCab

# --- Constants ---
LANG_LIST = ["US", "ES", "FR", "KR", "JP"]

# --- Logger Setup ---
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO) # Set base level for the logger

# Console Handler (outputs INFO and above to console)
ch = logging.StreamHandler()
ch.setLevel(logging.INFO)
formatter_console = logging.Formatter('%(levelname)s: %(message)s')
ch.setFormatter(formatter_console)
logger.addHandler(ch)

# File Handler (outputs ERROR and above to error.log)
log_file_path = "restore_lyrics_error.log"
try:
    fh = logging.FileHandler(log_file_path, mode='w') 
    fh.setLevel(logging.WARNING)
    formatter_file = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    fh.setFormatter(formatter_file)
    logger.addHandler(fh)
except Exception as e:
    # Use the already configured console handler to log this error if file handler setup fails
    # This assumes the console handler (ch) was added to logger successfully before this point.
    # If logger.addHandler(ch) itself could fail, more robust error handling for logger setup would be needed.
    logger.error(f"Failed to configure file logger at '{log_file_path}': {e}")
# --- End Logger Setup ---

# --- Lyrics Cache ---
CACHED_ORIGINAL_LYRICS = {} # Cache for original lyrics content
LANG_CODE_TO_PATH_COMPONENT = { # Mapping for language codes to directory names
    "US_og": "US"
}
# --- End Lyrics Cache ---

def is_special_char_only(word_str):
    """Checks if a word consists only of non-alphanumeric characters."""
    if not word_str:
        return False
    return re.match(r'^[^\w\s]+$', word_str) is not None


def get_comparable_form(word_str, is_corresponding_clue_special_only):
    """
    Normalizes a word for comparison based on whether its corresponding clue word is special-char-only.
    If the clue is special-char-only, an exact match is needed for the word.
    Otherwise, trailing punctuation is stripped from the word for comparison.
    """
    if is_corresponding_clue_special_only:
        return word_str  # Exact match needed
    else:
        # replace punctuation with empty string with regex, globally
        temp_word = word_str
        temp_word = re.sub(r'[^\w\s]', '', temp_word)
        temp_word = temp_word.lower()
        return temp_word


def check_acronym_strict(acronym_clue_str, candidate_words_list, normalized_candidate_segment_words):
    """
    Checks if the acronym can be formed by a contiguous sub-segment of candidate_words_list.
    Each character in the acronym must correspond to the starting letter of a word
    in this contiguous sub-segment.

    Args:
        acronym_clue_str (str): The acronym to check.
        candidate_words_list (list): A list of words to check against the acronym.

    Returns:
        bool: True if the acronym can be formed by a contiguous sub-segment of the candidate words, False otherwise.
    """
    if not acronym_clue_str:
        return True  # Empty acronym always matches

    acronym_chars = list(acronym_clue_str)

    if not candidate_words_list or len(candidate_words_list) != len(acronym_chars):
        return False  # Not enough words in candidate to form the acronym

    for i in range(len(candidate_words_list)):
        # Potential contiguous sub-segment starts at candidate_words_list[i]
        # and has length len(acronym_chars)
        word_to_check = candidate_words_list[i].lower()
        normalized_word_to_check = normalized_candidate_segment_words[i].lower()
        acronym_char_to_check = acronym_chars[i].lower()
        # Perform case-sensitive startswith for acronym character
        if not word_to_check.startswith(acronym_char_to_check) and not normalized_word_to_check.startswith(acronym_char_to_check):
            return False

    return True


def merge_jp_chars(chars: str) -> list[str]:
    """Groups Japanese characters by 3."""
    grouped = []
    for i in range(0, len(chars), 3):
        group = chars[i:i+3]
        if group:
            grouped.append(group)
    return grouped

def get_original_lyrics_content(song_key: str, lang_code: str, lyrics_dataset_base_dir: str) -> dict | None:
    """
    Loads and preprocesses original lyrics for a given song and language.
    Caches the results.

    Returns:
        A dictionary like {'type': 'words', 'content': list_of_words} for English-like,
        {'type': 'jp_raw_tokens', 'content': list_of_raw_tokens} for Japanese,
        or None if an error occurs.
    """
    cache_key = (song_key, lang_code)
    if cache_key in CACHED_ORIGINAL_LYRICS:
        return CACHED_ORIGINAL_LYRICS[cache_key]

    lang_path_component = LANG_CODE_TO_PATH_COMPONENT.get(lang_code, lang_code)
    lyrics_filepath = os.path.join(lyrics_dataset_base_dir, song_key, lang_path_component, "lyrics.txt")

    if not os.path.exists(lyrics_filepath):
        logger.error(f"Original lyrics file not found for song '{song_key}', lang '{lang_code}' at '{lyrics_filepath}'.")
        return None

    try:
        with open(lyrics_filepath, "r", encoding="utf-8") as f:
            full_lyrics_text = f.read()
            # Remove zero-width spaces and other invisible Unicode characters
            full_lyrics_text = re.sub(r'[\u200b\u200c\u200d\ufeff\u3000]', ' ', full_lyrics_text)
            # Convert Japanese full-width characters to half-width
            full_lyrics_text = full_lyrics_text.replace("（", "(")
            full_lyrics_text = full_lyrics_text.replace("）", ")")
            full_lyrics_text = full_lyrics_text.replace("！", "!")
            full_lyrics_text = full_lyrics_text.replace("？", "?")
            full_lyrics_text = full_lyrics_text.replace("．", ".")
            full_lyrics_text = full_lyrics_text.replace("，", ",")
            full_lyrics_text = full_lyrics_text.replace("：", ":")
            full_lyrics_text = full_lyrics_text.replace("；", ";")
            full_lyrics_text = full_lyrics_text.replace("「", '"')
            full_lyrics_text = full_lyrics_text.replace("」", '"')
            full_lyrics_text = full_lyrics_text.replace("『", '"')
            full_lyrics_text = full_lyrics_text.replace("』", '"')
            full_lyrics_text = full_lyrics_text.replace("〜", "~")
            full_lyrics_text = full_lyrics_text.replace("－", "-")
            # "..." -> "... " (add space after . or ,)
            full_lyrics_text = full_lyrics_text.replace("\n", " ")

        if lang_code == "JP":
            # Remove all spaces and whitespace characters for Japanese
            full_lyrics_text = re.sub(r'\s+', '', full_lyrics_text)
            full_lyrics_text = re.sub(r'[\u200b\u200c\u200d\ufeff\u3000]', '', full_lyrics_text)
            
            content_data = {
                'type': 'jp_chars', 
                'content': full_lyrics_text,  # Store as string of characters
            }
        else: # English-like languages (US_og, ES, FR, KR, etc.)
            full_lyrics_text = re.sub(r'(\.|\,|:)', lambda m: m.group() + ' ', full_lyrics_text)
            full_lyrics_text = full_lyrics_text.replace(")", " ")
            full_lyrics_text = full_lyrics_text.replace("(", " ")
            raw_words = full_lyrics_text.split()
            # Normalize only specific apostrophe ' to ' , keep ' as is.
            normalized_words = [word.replace("'", "'") for word in raw_words]
            
            # Merge special-character-only words with preceding words
            merged_words = []
            for word in normalized_words:
                if is_special_char_only(word) and merged_words:
                    # Merge with the previous word
                    merged_words[-1] = merged_words[-1] + word
                else:
                    merged_words.append(word)
            
            content_data = {'type': 'words', 'content': merged_words}
        
        CACHED_ORIGINAL_LYRICS[cache_key] = content_data
        return content_data
    except Exception as e:
        logger.error(f"Could not read or process original lyrics for song '{song_key}', lang '{lang_code}' at '{lyrics_filepath}'. Error: {e}")
        return None


def find_eng_like_segment_strict( # Renamed from find_us_og_segment_strict
    clues, all_lyrics_words, search_from_word_index # all_lyrics_words_normalized -> all_lyrics_words
):
    """
    Finds a segment in all_lyrics_words based on strict acronym matching
    and punctuation handling for first/last words. (For English-like languages)

    Args:
        clues (tuple): (acronym_clue_str, first_word_clue_str, last_word_clue_str)
        all_lyrics_words (list): List of words from original lyrics.txt.
        search_from_word_index (int): Index to start searching from in all_lyrics_words.

    Returns:
        tuple: (matched_phrase_str, last_word_index_of_match) if found,
               (None, -1) otherwise.
    """
    acronym_clue, first_word_clue, last_word_clue = clues
    
    # Normalize apostrophes in clues to match lyric content normalization
    first_word_clue = first_word_clue.replace("'", "'")
    last_word_clue = last_word_clue.replace("'", "'")
    acronym_clue = acronym_clue.replace("'", "'") # Though less likely for acronyms


    is_first_clue_special_only = is_special_char_only(first_word_clue)
    comparable_first_clue = get_comparable_form(
        first_word_clue, is_first_clue_special_only
    )

    is_last_clue_special_only = is_special_char_only(last_word_clue)
    comparable_last_clue = get_comparable_form(
        last_word_clue, is_last_clue_special_only
    )

    for i in range(search_from_word_index, len(all_lyrics_words)):
        current_lyrics_word_for_first_match = all_lyrics_words[i]
        comparable_lyrics_word_i = get_comparable_form(
            current_lyrics_word_for_first_match, is_first_clue_special_only
        )
        
        if comparable_lyrics_word_i == comparable_first_clue:
            # Potential start of a segment
            for j in range(i, len(all_lyrics_words)):
                current_lyrics_word_for_last_match = all_lyrics_words[j]
                comparable_lyrics_word_j = get_comparable_form(
                    current_lyrics_word_for_last_match, is_last_clue_special_only
                )
                
                if comparable_lyrics_word_j == comparable_last_clue:
                    if j < i: # last word cannot be before first word
                        continue
                    
                    # Candidate segment uses original words from lyrics
                    candidate_segment_words = all_lyrics_words[i : j + 1]
                    
                    # Prepare normalized candidate segment words for check_acronym_strict
                    normalized_candidate_segment_words_for_acronym_check = [
                        get_comparable_form(word, False) for word in candidate_segment_words
                    ]

                    if check_acronym_strict(acronym_clue, candidate_segment_words, normalized_candidate_segment_words_for_acronym_check):
                        return " ".join(candidate_segment_words), j

    return None, -1  # No segment found matching all criteria


def find_jp_segment_strict(clues, all_chars, search_from_char_index):
    """
    Finds a Japanese segment by iterating through characters, grouping them by 3 for comparison.
    
    Args:
        clues (tuple): (acronym_clue_str, first_group_clue, last_group_clue)
        all_chars (str): All characters from the entire song (spaces removed).
        search_from_char_index (int): Index to start searching from in all_chars.

    Returns:
        tuple: (matched_phrase_str, last_char_idx_of_match_in_song) if found,
               (None, -1) otherwise.
    """
    acronym_clue, first_group_clue, last_group_clue = clues
    n_chars = len(all_chars)

    if n_chars == 0:
        return None, -1

    # Try to find the first group starting from search_from_char_index
    for i in range(search_from_char_index, n_chars):
        # Check if we can form a group of up to 3 characters starting at position i
        for first_group_len in [1, 2, 3]:
            if i + first_group_len > n_chars:
                continue
                
            candidate_first_group = all_chars[i:i + first_group_len]
            
            # Check if this candidate matches the first_group_clue
            if candidate_first_group == first_group_clue:
                # Found potential start of segment
                
                # Special case: if first and last groups are the same (single group segment)
                if first_group_clue == last_group_clue:
                    # Check if acronym matches (should be first character of the group)
                    if candidate_first_group and candidate_first_group[0] == acronym_clue:
                        return candidate_first_group, i + first_group_len - 1
                
                # Search for the last group starting after the first group
                search_start_for_last = i + first_group_len
                
                # Try to find matching last group
                for j in range(search_start_for_last, n_chars):
                    for last_group_len in [1, 2, 3]:
                        if j + last_group_len > n_chars:
                            continue
                            
                        candidate_last_group = all_chars[j:j + last_group_len]
                        
                        if candidate_last_group == last_group_clue:
                            # Found potential end of segment
                            segment_chars = all_chars[i:j + last_group_len]
                            
                            # Group the segment characters by 3 and check acronym
                            grouped_chars = merge_jp_chars(segment_chars)
                            
                            if grouped_chars:
                                formed_acronym = "".join(g[0] for g in grouped_chars if g)
                                
                                if formed_acronym == acronym_clue:
                                    return segment_chars, j + last_group_len - 1
    
    return None, -1

def find_kr_segment_with_partial_matching(clues, all_lyrics_words, search_from_word_index, remaining_word_part=""):
    """
    Finds a Korean segment with partial word matching support.
    If a clue matches only the beginning of a word, the remaining part is used for the next clue.
    
    Args:
        clues (tuple): (acronym_clue_str, first_word_clue_str, last_word_clue_str)
        all_lyrics_words (list): List of words from original lyrics.txt.
        search_from_word_index (int): Index to start searching from in all_lyrics_words.
        remaining_word_part (str): Remaining part of a word from previous partial match.
    
    Returns:
        tuple: (matched_phrase_str, last_word_index_of_match, remaining_part) if found,
               (None, -1, "") otherwise.
    """
    acronym_clue, first_word_clue, last_word_clue = clues
    
    is_first_clue_special_only = is_special_char_only(first_word_clue)
    comparable_first_clue = get_comparable_form(
        first_word_clue, is_first_clue_special_only
    )

    is_last_clue_special_only = is_special_char_only(last_word_clue)
    comparable_last_clue = get_comparable_form(
        last_word_clue, is_last_clue_special_only
    )
    
    # If we have a remaining part, start by checking if it matches the first clue
    if remaining_word_part:

        # search_from_word_index = search_from_word_index # It already matches this word, so start from the next word

        is_remaining_word_special_only = is_special_char_only(remaining_word_part)
        remaining_normalized = get_comparable_form(
            remaining_word_part, is_remaining_word_special_only
        )
        
        # Check if remaining part matches first clue exactly
        if remaining_normalized == comparable_first_clue:
            # Use the remaining part as the first word and continue search
            segment_words = [first_word_clue]
            segment_start_idx = search_from_word_index - 1 
            
            # Special case: if first and last clues are the same
            if comparable_first_clue == comparable_last_clue:
                if len(acronym_clue) == 1 and first_word_clue and first_word_clue[0].lower() == acronym_clue.lower():
                    return first_word_clue, search_from_word_index - 1, ""
            
            # Search for last word starting from current index
            for j in range(search_from_word_index, len(all_lyrics_words)):
                current_last_word = all_lyrics_words[j]
                is_last_word_special_only = is_special_char_only(current_last_word)
                current_last_word_normalized = get_comparable_form(
                    current_last_word, is_last_word_special_only
                )
                
                last_match_type = None
                last_match_remaining = ""
                
                if current_last_word_normalized == comparable_last_clue:
                    last_match_type = "exact"
                elif current_last_word_normalized.startswith(comparable_last_clue):
                    last_match_type = "partial"
                    last_match_remaining = current_last_word[len(last_word_clue):]
                
                if last_match_type:
                    # Build candidate segment
                    candidate_words = segment_words + all_lyrics_words[search_from_word_index:j]
                    if last_match_type == "exact":
                        candidate_words.append(current_last_word)
                    else:  # partial
                        candidate_words.append(last_word_clue)
                    
                    # Check acronym
                    if candidate_words:
                        formed_acronym = "".join(word[0].lower() for word in candidate_words if word)
                        if formed_acronym == acronym_clue.lower():
                            # Construct actual phrase
                            actual_phrase_words = [first_word_clue] + all_lyrics_words[search_from_word_index:j]
                            if last_match_type == "exact":
                                actual_phrase_words.append(current_last_word)
                            else:
                                actual_phrase_words.append(last_word_clue)
                            
                            return " ".join(actual_phrase_words), j, last_match_remaining
    
    # first clue == last clue and partial match
    if comparable_first_clue == comparable_last_clue:
        current_word = all_lyrics_words[search_from_word_index]
        is_current_word_special_only = is_special_char_only(current_word)
        current_word_normalized = get_comparable_form(
            current_word, is_current_word_special_only
        )

        # if partial match, return the current word and the remaining part
        if current_word_normalized.startswith(comparable_first_clue):
            return current_word, search_from_word_index, current_word[len(last_word_clue):]



    # Normal search without remaining part
    for i in range(search_from_word_index, len(all_lyrics_words)):
        current_word_to_check = all_lyrics_words[i]
        is_current_word_special_only = is_special_char_only(current_word_to_check)
        current_word_normalized = get_comparable_form(
            current_word_to_check, is_current_word_special_only
        )
        
        candidate_words = []
        actual_phrase_words = []

        if current_word_normalized == comparable_first_clue:
            # Special case: if first and last clues are the same and we had exact match
            if comparable_first_clue == comparable_last_clue:
                if len(acronym_clue) == 1 and current_word_to_check and current_word_normalized.lower()[0] == acronym_clue.lower():
                    return current_word_to_check, i, ""
            
            # Search for last word match
            candidate_words.append(current_word_normalized)
            actual_phrase_words.append(current_word_to_check)
            search_start_for_last = i + 1
            
            # Search in subsequent words
            for j in range(search_start_for_last, len(all_lyrics_words)):
                current_last_word = all_lyrics_words[j]
                is_current_last_word_special_only = is_special_char_only(current_last_word)
                current_last_word_normalized = get_comparable_form(
                    current_last_word, is_current_last_word_special_only
                )

                candidate_words.append(current_last_word_normalized)
                actual_phrase_words.append(current_last_word)
                
                last_match_type = None
                last_match_remaining = ""
                
                if current_last_word_normalized == comparable_last_clue:
                    last_match_type = "exact"
                elif current_last_word_normalized.startswith(comparable_last_clue):
                    last_match_type = "partial"
                    last_match_remaining = current_last_word[len(last_word_clue):]
                
                if last_match_type:
                    # Check acronym
                    formed_acronym = "".join(word[0].lower() for word in candidate_words if word)
                    if formed_acronym == acronym_clue.lower():
                        return " ".join(actual_phrase_words), j, last_match_remaining
    
    return None, -1, ""

def main():
    processed_lyrics_filepath = "mavl_dataset.json"
    lyrics_dataset_base_dir = "mavl_datasets"
    output_filepath = "mavl_dataset_restored.json"

    all_restored_data = {}

    try:
        with open(processed_lyrics_filepath, "r", encoding="utf-8") as f:
            processed_data = json.load(f)
    except FileNotFoundError:
        logger.error(f"Error: Input file '{processed_lyrics_filepath}' not found.")
        return
    except json.JSONDecodeError:
        logger.error(f"Error: Could not decode JSON from '{processed_lyrics_filepath}'.")
        return
    except Exception as e:
        logger.error(
            f"An unexpected error occurred while reading '{processed_lyrics_filepath}': {e}"
        )
        return

    # Handle both old dict format and new array format
    if isinstance(processed_data, list):
        # New array format - convert to dict for processing
        processed_dict = {}
        for song_item in processed_data:
            if "song_title" in song_item:
                song_key = song_item["song_title"]
                # Create song_data dict with all fields except song_title
                song_data = {k: v for k, v in song_item.items() if k != "song_title"}
                processed_dict[song_key] = song_data
        processed_data = processed_dict
    elif not isinstance(processed_data, dict):
        logger.error(f"Unexpected data format. Expected list or dict.")
        return

    for song_key, song_data in processed_data.items():
        logger.info(f"Processing song: {song_key}")
        
        restored_song_data = {
            "lyrics": [],
            # Preserve other top-level song data if necessary
            "youtube_url": song_data.get("youtube_url", {}),
            "lyrics_url": song_data.get("lyrics_url", {}),
            "video": song_data.get("video", {})
        }
        
        # --- Per-language tracking for restoration ---
        # For English-like languages that are word-based
        last_matched_word_indices = {} # lang_code -> last_matched_word_idx
        # For Japanese, store the last matched RAW token index
        last_matched_jp_raw_token_indices = {} # lang_code -> last_raw_token_idx
        # For Korean, store remaining word parts from partial matches
        kr_remaining_word_parts = {} # lang_code -> remaining_word_part
        # --- End per-language tracking ---

        original_line_groups = song_data.get("lyrics", [])
        if not isinstance(original_line_groups, list):
            logger.warning(
                f"Warning: 'lyrics' field for song '{song_key}' is not a list. Skipping this song."
            )
            continue

        for group_idx, original_line_group in enumerate(original_line_groups):
            if not isinstance(original_line_group, list):
                logger.warning(f"Warning: Line group {group_idx} for song '{song_key}' is not a list. Skipping this group.")
                continue
            restored_line_group = []
            for seg_idx, original_segment_data in enumerate(original_line_group):
                if not isinstance(original_segment_data, dict):
                    logger.warning(f"Warning: Segment {seg_idx} in group {group_idx} for song '{song_key}' is not a dict. Skipping this segment.")
                    continue
                restored_segment_output = {}
                for lang_code, lang_entry_data in original_segment_data.items():
                    if not isinstance(lang_entry_data, dict):
                        logger.warning(f"Warning: Language entry for '{lang_code}' in segment {seg_idx}, group {group_idx}, song '{song_key}' is not a dict. Skipping this language.")
                        continue

                    current_lang_output_entry = {
                        "syllable_count": lang_entry_data.get("syllable_count"),
                        "line_number": lang_entry_data.get("line_number"),
                    }
                    for key in ["character_count", "start", "end", "video", "ipa"]:
                        if key in lang_entry_data:
                            current_lang_output_entry[key] = lang_entry_data[key]
                    
                    processed_text_field = lang_entry_data.get("text") # This is a list of lists of strings
                    if not processed_text_field or not isinstance(processed_text_field, list) or not processed_text_field[0]:
                        logger.warning(f"Warning: 'text' field is missing, empty, or not a list of lists for {lang_code} in song '{song_key}', group {group_idx}, segment {seg_idx}. Skipping this language.")
                        continue

                    # Ensure clues_parts is a list, as expected by processing_lyrics.py output structure
                    clue_parts_outer_list = processed_text_field[0] # This should be the list containing clue strings
                    if not isinstance(clue_parts_outer_list, list):
                        logger.warning(f"Warning: Inner part of 'text' field (clues) is not a list for {lang_code} in song '{song_key}', group {group_idx}, segment {seg_idx}. Clues raw: {processed_text_field}. Skipping this language.")
                        continue
                    
                    clue_parts = clue_parts_outer_list

                    original_lyrics_data = get_original_lyrics_content(song_key, lang_code, lyrics_dataset_base_dir)
                    if not original_lyrics_data:
                        logger.warning(f"Warning: Could not load original lyrics for {lang_code}, song '{song_key}'. Skipping this language.")
                        continue

                    # --- Language-specific clue extraction and restoration ---
                    found_phrase_str = None
                    
                    if lang_code == "JP":
                        if original_lyrics_data['type'] != 'jp_chars': # Expecting characters now
                            logger.warning(f"Warning: Original JP lyrics for song '{song_key}' not loaded as jp_chars. Skipping this language.")
                            continue
                        
                        acronym_clue, first_group_clue, last_group_clue = "", "", ""
                        if len(clue_parts) == 3 and all(isinstance(cp, str) for cp in clue_parts):
                            acronym_clue, first_group_clue, last_group_clue = clue_parts
                        else:
                            logger.warning(f"Warning: Invalid clue structure for JP in song '{song_key}'. Expected [acronym, first_group, last_group]. Got: {clue_parts}. Skipping this language.")
                            continue
                        
                        clues_jp = (acronym_clue, first_group_clue, last_group_clue)
                        search_start_char_idx = last_matched_jp_raw_token_indices.get(lang_code, -1) + 1
                        
                        all_song_chars = original_lyrics_data['content']

                        found_phrase_str, matched_last_char_idx = find_jp_segment_strict(
                            clues_jp, 
                            all_song_chars,
                            search_start_char_idx
                        )
                        if found_phrase_str is not None:
                            last_matched_jp_raw_token_indices[lang_code] = matched_last_char_idx
                        else:
                            # Extract the attempted segment for logging (raw characters)
                            attempted_char_snippet_jp = ""
                            if all_song_chars:
                                start_idx_jp = search_start_char_idx
                                acronym_len_jp = len(acronym_clue) if acronym_clue else 0
                                desired_snippet_len_jp = acronym_len_jp * 3
                                end_idx_jp = start_idx_jp + desired_snippet_len_jp
                                # Ensure end_idx_jp does not exceed the bounds of the string
                                end_idx_jp = min(end_idx_jp, len(all_song_chars))
                                if start_idx_jp < len(all_song_chars) and desired_snippet_len_jp > 0: # ensure start_idx_jp is valid and snippet_len >0
                                    attempted_char_snippet_jp = all_song_chars[start_idx_jp:end_idx_jp]
                            
                            lyrics_url_jp = song_data.get("lyrics_url", {}).get(lang_code, "N/A") # Corrected to use song_data
                            logger.warning(f"Warning: {lyrics_url_jp} - Could not find matching JP segment for song '{song_key}', clues: {clues_jp}, start char_idx: {search_start_char_idx}. Attempted characters: {attempted_char_snippet_jp}. Total characters: {len(all_song_chars)}. Skipping this language.")
                            continue
                    elif lang_code == "KR":
                        if original_lyrics_data['type'] != 'words':
                            logger.warning(f"Warning: Original {lang_code} lyrics for song '{song_key}' not loaded as words. Skipping this language.")
                            continue

                        acronym_clue, first_word_clue, last_word_clue = "", "", ""
                        valid_clues_extracted = False
                        if len(clue_parts) == 3 and all(isinstance(cp, str) for cp in clue_parts):
                            acronym_clue, first_word_clue, last_word_clue = clue_parts
                            valid_clues_extracted = True
                        elif len(clue_parts) == 2 and all(isinstance(cp, str) for cp in clue_parts) and clue_parts[1]:
                            acronym_clue = clue_parts[0]
                            first_word_clue = last_word_clue = clue_parts[1]
                            valid_clues_extracted = True
                        elif len(clue_parts) == 1 and isinstance(clue_parts[0], str) and clue_parts[0]:
                            single_clue_word = clue_parts[0]
                            acronym_clue = single_clue_word[0] if single_clue_word else ""
                            first_word_clue = last_word_clue = single_clue_word
                            valid_clues_extracted = True
                        
                        if not valid_clues_extracted:
                            logger.warning(f"Warning: Invalid clue structure for {lang_code} in song '{song_key}'. Clues: {clue_parts}. Skipping this language.")
                            continue
                        
                        clues = (acronym_clue, first_word_clue, last_word_clue)
                        search_start_word_idx = last_matched_word_indices.get(lang_code, -1) + 1
                        current_remaining_part = kr_remaining_word_parts.get(lang_code, "")
                        
                        found_phrase_str, matched_end_idx, remaining_word_part = find_kr_segment_with_partial_matching(
                            clues, original_lyrics_data['content'], search_start_word_idx, current_remaining_part
                        )
                        if found_phrase_str is not None:
                            last_matched_word_indices[lang_code] = matched_end_idx
                            kr_remaining_word_parts[lang_code] = remaining_word_part
                        else:
                            song_lyrics_url = song_data.get("lyrics_url", {}).get(lang_code, "N/A")
                            # Extract the attempted segment for logging
                            attempted_segment_snippet = []
                            if original_lyrics_data and 'content' in original_lyrics_data and isinstance(original_lyrics_data['content'], list):
                                start_idx = search_start_word_idx
                                acronym_len = len(acronym_clue) if acronym_clue else 0
                                end_idx = start_idx + acronym_len
                                # Ensure end_idx does not exceed the bounds of the list
                                end_idx = min(end_idx, len(original_lyrics_data['content']))
                                if start_idx < len(original_lyrics_data['content']) and acronym_len > 0 : # ensure start_idx is valid and acronym_len > 0
                                    attempted_segment_snippet = original_lyrics_data['content'][start_idx:end_idx]
                            
                            logger.warning(f"Warning: Could not find matching {lang_code} segment for song '{song_key}', URL: {song_lyrics_url}, clues: {clues}, (original processed: {processed_text_field}), start word idx: {search_start_word_idx}. Attempted segment: {attempted_segment_snippet}. Total words: {len(original_lyrics_data['content'])}. Skipping this language.")
                            continue
                    else: # English-like languages (US_og, ES, FR, etc.)
                        if original_lyrics_data['type'] != 'words':
                            logger.warning(f"Warning: Original {lang_code} lyrics for song '{song_key}' not loaded as words. Skipping this language.")
                            continue

                        acronym_clue, first_word_clue, last_word_clue = "", "", ""
                        valid_clues_extracted = False
                        if len(clue_parts) == 3 and all(isinstance(cp, str) for cp in clue_parts):
                            acronym_clue, first_word_clue, last_word_clue = clue_parts
                            valid_clues_extracted = True
                        elif len(clue_parts) == 2 and all(isinstance(cp, str) for cp in clue_parts) and clue_parts[1]:
                            acronym_clue = clue_parts[0]
                            first_word_clue = last_word_clue = clue_parts[1]
                            valid_clues_extracted = True
                        elif len(clue_parts) == 1 and isinstance(clue_parts[0], str) and clue_parts[0]:
                            single_clue_word = clue_parts[0]
                            acronym_clue = single_clue_word[0] if single_clue_word else ""
                            first_word_clue = last_word_clue = single_clue_word
                            valid_clues_extracted = True
                        
                        if not valid_clues_extracted:
                            logger.warning(f"Warning: Invalid clue structure for {lang_code} in song '{song_key}'. Clues: {clue_parts}. Skipping this language.")
                            continue
                        
                        clues = (acronym_clue, first_word_clue, last_word_clue)
                        search_start_word_idx = last_matched_word_indices.get(lang_code, -1) + 1
                        
                        found_phrase_str, matched_end_idx = find_eng_like_segment_strict(
                            clues, original_lyrics_data['content'], search_start_word_idx
                        )
                        if found_phrase_str is not None:
                            last_matched_word_indices[lang_code] = matched_end_idx
                        else:
                            song_lyrics_url = song_data.get("lyrics_url", {}).get(lang_code, "N/A")
                            # Extract the attempted segment for logging
                            attempted_segment_snippet = []
                            if original_lyrics_data and 'content' in original_lyrics_data and isinstance(original_lyrics_data['content'], list):
                                start_idx = search_start_word_idx
                                acronym_len = len(acronym_clue) if acronym_clue else 0
                                end_idx = start_idx + acronym_len
                                # Ensure end_idx does not exceed the bounds of the list
                                end_idx = min(end_idx, len(original_lyrics_data['content']))
                                if start_idx < len(original_lyrics_data['content']) and acronym_len > 0 : # ensure start_idx is valid and acronym_len > 0
                                    attempted_segment_snippet = original_lyrics_data['content'][start_idx:end_idx]
                            
                            logger.warning(f"Warning: Could not find matching {lang_code} segment for song '{song_key}', URL: {song_lyrics_url}, clues: {clues}, (original processed: {processed_text_field}), start word idx: {search_start_word_idx}. Attempted segment: {attempted_segment_snippet}. Total words: {len(original_lyrics_data['content'])}. Skipping this language.")
                            continue
                    # --- End Language-specific clue extraction and restoration ---

                    if found_phrase_str is not None:
                        current_lang_output_entry["text"] = found_phrase_str
                    else:
                        # This case should ideally be caught by continues above, but as a safeguard:
                        logger.warning(f"Warning: found_phrase_str is None but not caught for {lang_code}, song '{song_key}'. Skipping this language.")
                        continue
                        
                    restored_segment_output[lang_code] = current_lang_output_entry
                
                # Only add segment if it has at least one language
                if restored_segment_output:
                    restored_line_group.append(restored_segment_output)
            
            # Only add line group if it has at least one segment
            if restored_line_group:
                restored_song_data["lyrics"].append(restored_line_group)
        
        # Always add song data, even if some languages/segments failed
        all_restored_data[song_key] = restored_song_data

    try:
        with open(output_filepath, "w", encoding="utf-8") as f_out:
            json.dump(all_restored_data, f_out, ensure_ascii=False, indent=2)
        logger.info(f"Successfully wrote restored lyrics to '{output_filepath}'. Processed {len(all_restored_data)} songs.")
    except IOError:
        logger.error(f"Error: Could not write to output file '{output_filepath}'.")
    except Exception as e:
        logger.error(f"An unexpected error occurred during file writing: {e}")


if __name__ == "__main__":
    try:
        main()
    except ValueError as ve:
        logger.critical(f"Script terminated due to a ValueError: {ve}")
    except Exception as e:
        logger.critical(f"Script terminated due to an unexpected error: {e}")
