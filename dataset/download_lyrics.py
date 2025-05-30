import os
import json
import logging
import time
import argparse
from typing import Dict, Optional, Tuple, List
from urllib import request
from urllib.parse import quote, unquote, urlparse, urlunparse
import idna
import numpy as np
from bs4 import BeautifulSoup
from tqdm import tqdm
import re
import sys
import io

def smart_encode_url(url):
    """
    Splits URL into components, decodes them first (unquote), 
    then properly encodes them (quote, Punycode) and combines them.
    This prevents double encoding of already encoded URLs.
    """
    try:
        parsed_url = urlparse(url)

        # 1. Netloc (hostname) processing: IDNA (Punycode)
        # Although requests handles most cases automatically, we can do it explicitly
        encoded_netloc = parsed_url.netloc
        if parsed_url.hostname:
            try:
                hostname_bytes = parsed_url.hostname.encode('idna')
                encoded_hostname = hostname_bytes.decode('ascii')
                
                if parsed_url.port:
                    encoded_netloc = f"{encoded_hostname}:{parsed_url.port}"
                else:
                    encoded_netloc = encoded_hostname
            except idna.IDNAError:
                # Use original netloc if Punycode encoding fails (let requests handle it)
                pass

        # 2. Path (path) processing: decode first (unquote) then encode
        # Use unquote instead of unquote_plus as unquote_plus decodes '+' to space
        unquoted_path = unquote(parsed_url.path)
        encoded_path = quote(unquoted_path, safe='/')

        # 3. Parameters processing: decode first then encode
        unquoted_params = unquote(parsed_url.params)
        encoded_params = quote(unquoted_params, safe='') 

        # 4. Query (query string) processing: decode first then encode
        unquoted_query = unquote(parsed_url.query)
        encoded_query = quote(unquoted_query, safe='=&')

        # 5. Fragment processing: decode first then encode
        unquoted_fragment = unquote(parsed_url.fragment)
        encoded_fragment = quote(unquoted_fragment, safe='')

        # Reconstruct URL with encoded components
        encoded_url = urlunparse((
            parsed_url.scheme,
            encoded_netloc,
            encoded_path,
            encoded_params,
            encoded_query,
            encoded_fragment
        ))
        
        return encoded_url

    except Exception as e:
        print(f"Error processing URL '{url}': {e}")
        return None


# Reset stdout to UTF-8
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout)
    ],
    encoding='utf-8'
)
logger = logging.getLogger(__name__)

# Global variables for request throttling per host
_last_req_times_per_host: Dict[str, float] = {}

# Configuration for site-specific throttling
# min_interval: minimum seconds to wait after the *completion* of the previous request
#               before starting a new one for the same host.
# sleep_params: (mean, std_dev, min_cap, max_cap) for the sleep duration if a wait is needed.
SITE_THROTTLE_CONFIG = {
    "lyricstranslate.com": {
        "min_interval": 8.0,  # Minimum 8 seconds interval for lyricstranslate.com
        "sleep_mean": 5.0,  # If throttling, sleep around 5s for lyricstranslate.com
        "sleep_std": 1.0,
        "sleep_min": 3.0,
        "sleep_max": 7.0,
    },
    "default": {
        "min_interval": 2.0,  # Default minimum 2 seconds interval
        "sleep_mean": 1.5,
        "sleep_std": 0.5,
        "sleep_min": 1.0,
        "sleep_max": 2.0,
    },
}


def throttle_request(url, timeout=10, **kwargs):
    """
    Sends a request to a URL with site-specific throttling.
    Encodes non-ASCII characters in the URL.
    """
    global _last_req_times_per_host
    global SITE_THROTTLE_CONFIG

    parsed_url = urlparse(url)
    hostname = parsed_url.hostname if parsed_url.hostname else "default"

    config = SITE_THROTTLE_CONFIG.get(hostname, SITE_THROTTLE_CONFIG["default"])
    last_req_time_for_host = _last_req_times_per_host.get(hostname, 0)

    current_time = time.time()
    if current_time - last_req_time_for_host < config["min_interval"]:
        sleep_duration = np.random.normal(config["sleep_mean"], config["sleep_std"])
        sleep_duration = max(
            config["sleep_min"], min(config["sleep_max"], sleep_duration)
        )
        logger.debug(
            f"Throttling for {hostname}: sleeping for {sleep_duration:.2f}s. "
            f"Interval: {current_time - last_req_time_for_host:.2f}s < {config['min_interval']}s"
        )
        time.sleep(sleep_duration)

    # URL encoding
    # encoded_url = request.quote(url, safe=":/?=&@")
    encoded_url = url

    max_retries = 3
    retry_delay = 10  # seconds

    for attempt in range(max_retries + 1):  # Initial attempt + number of retries
        current_attempt_finish_time = 0.0  # Initialize variable
        try:
            resp = request.urlopen(
                request.Request(
                    encoded_url,
                    headers={
                        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36",
                        "Accept-Charset": "utf-8"
                    },
                ),
                timeout=timeout,
            )
            current_attempt_finish_time = time.time()
            status_code = resp.getcode()

            if status_code == 200:
                _last_req_times_per_host[hostname] = current_attempt_finish_time
                return resp
            elif status_code == 202 or status_code == 403:
                _last_req_times_per_host[hostname] = (
                    current_attempt_finish_time  # Update host last request time
                )
                if attempt < max_retries:
                    logger.info(
                        f"HTTP 202 (Accepted) or 403 (Forbidden) for {url}. Retrying in {retry_delay}s "
                        f"(Attempt {attempt + 2}/{max_retries + 1})"  # attempt is 0-indexed
                    )
                    time.sleep(retry_delay)
                    continue  # Go to the next attempt
                else:
                    # Max retries for 202 reached
                    msg = f"Request to {url} returned status 202 or 403 after all {max_retries + 1} attempts."
                    logger.warning(msg)
                    raise request.HTTPError(
                        url, status_code, msg, resp.headers, resp.fp
                    )
            else:
                # Any other non-200, non-202 status code
                _last_req_times_per_host[hostname] = current_attempt_finish_time
                msg = f"Request to {url} returned status {status_code} on attempt {attempt + 1}."
                logger.warning(msg)
                raise request.HTTPError(url, status_code, msg, resp.headers, resp.fp)

        except request.HTTPError as e:
            # This catches HTTPError raised by urlopen (e.g. 403, 404)
            # or by our own logic above (final 202, other non-200s).
            # Ensure last request time is updated if not already done before raising.
            # The logic above updates it before raising, so this is mostly for urlopen-originated HTTPError.
            if (
                _last_req_times_per_host.get(hostname) != current_attempt_finish_time
            ):  # Check if already set for this attempt
                _last_req_times_per_host[hostname] = time.time()  # Fallback update
            logger.warning(
                f"HTTPError for {url} on attempt {attempt + 1}: {e.code} {e.reason if hasattr(e, 'reason') else 'Unknown Reason'}"
            )
            if attempt < max_retries:
                logger.info(
                    f"Retrying {url} in {retry_delay}s (Attempt {attempt + 2}/{max_retries + 1})"
                )
                time.sleep(retry_delay)
                continue  # Go to the next attempt
            else:
                raise  # Re-raise to be caught by the calling function's error handler
        except Exception as e:
            # Catch other network errors like URLError, socket.timeout, etc.
            _last_req_times_per_host[hostname] = time.time()  # Mark this failed attempt
            logger.error(
                f"Request to {url} failed on attempt {attempt + 1} with generic error: {e}"
            )
            # For simplicity, we don't retry these other errors in this implementation.
            # We raise it to be handled by the calling function.
            raise

    # Fallback: Should not be reached if the loop logic is correct (always returns or raises).
    # This implies an issue like max_retries_on_202 being negative.
    # However, this code path should be logically unreachable with positive retries.
    # For safety, ensure an error is raised.
    final_error_msg = (
        f"Failed to get a valid response for {url} after all attempts and retries."
    )
    logger.error(final_error_msg)
    # Ensure _last_req_times_per_host is updated before this final desperate raise
    _last_req_times_per_host[hostname] = time.time()
    raise Exception(final_error_msg)


def get_lyrics_from_genius_url(song_url: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Scrapes lyrics from a Genius song URL and returns them.
    Returns (None, error_message) on scraping failure or if no lyrics are found.
    Returns (lyrics, None) on success.
    """
    try:
        page_resp = throttle_request(song_url, timeout=5)
        page_content = page_resp.read().decode("utf-8")
        soup = BeautifulSoup(page_content, "html.parser", from_encoding="utf-8")

        lyric_containers = soup.select('div[data-lyrics-container="true"]')
        if not lyric_containers:
            lyric_containers = soup.select('div[class*="Lyrics__Container-sc-1ynbvzw"]')

        if not lyric_containers:
            msg = f"[{song_url}] No lyric containers found (data-lyrics-container or Lyrics__Container-sc-1ynbvzw)."
            if logger:
                logger.error(msg)
            return None, msg

        lyrics_lines = []
        for container in lyric_containers:
            excluded_divs = container.find_all(
                "div", attrs={"data-exclude-from-selection": "true"}
            )
            for div in excluded_divs:
                div.decompose()

            tables = container.find_all("table")
            for table in tables:
                table.decompose()

            # # decompose all tags after first table tag including table itself
            # first_table = container.find("table")
            # if first_table:
            #     current_tag = first_table
            #     while current_tag:
            #         next_tag = current_tag.find_next_sibling()
            #         current_tag.decompose()
            #         current_tag = next_tag
            #     # The loop above handles decomposing the first_table itself as well.

            for tag in container.find_all(["span", "a", "i"], recursive=True):
                tag.unwrap()

            for br in container.find_all("br"):
                br.replace_with("\n")
            text = container.get_text()
            lyrics_lines.append(text)

        lyrics = "\n".join(lyrics_lines)
        if not lyrics.strip():
            msg = f"[{song_url}] NO LYRICS - Lyrics are empty after processing."
            if logger:
                logger.error(msg)
            return None, msg

        return lyrics, None
    except Exception as e:
        msg = (
            f"[{song_url}] Failed to scrape lyrics from Genius: {type(e).__name__}: {e}"
        )
        if logger:
            logger.error(msg)
        return None, msg
    
def get_lyrics_from_disney_fandom_url(song_url: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Scrapes lyrics from a Disney Fandom song URL and returns them.
    Returns (None, error_message) on scraping failure or if no lyrics are found.
    Returns (lyrics, None) on success.
    """
    try:
        # song_url = quote(song_url, safe=":/")
        song_url = smart_encode_url(song_url)
        page_resp = throttle_request(song_url, timeout=5)
        page_content = page_resp.read().decode("utf-8")
        soup = BeautifulSoup(page_content, "html.parser")

        lyric_containers = soup.select('div[class*="wds-tab__content"]')

        if not lyric_containers:
            msg = f"[{song_url}] No lyric containers found.."
            if logger:
                logger.error(msg)
            return None, msg
        
        if len(lyric_containers) != 3:
            msg = f"[{song_url}] lyrics containers should have 3 lyrics for the open road."
            if logger:
                logger.error(msg)
            return None, msg
        lyric_containers = [lyric_containers[1]] # Only Espanol

        lyrics_lines = []
        for container in lyric_containers:

            for tag in container.find_all(["span", "a", "i"], recursive=True):
                tag.unwrap()

            for br in container.find_all("br"):
                br.replace_with("")
            text = container.get_text()
            lyrics_lines.append(text)

        lyrics = "\n".join(lyrics_lines)
        if not lyrics.strip():
            msg = f"[{song_url}] NO LYRICS - Lyrics are empty after processing."
            if logger:
                logger.error(msg)
            return None, msg

        return lyrics, None
    except Exception as e:
        msg = (
            f"[{song_url}] Failed to scrape lyrics from Genius: {type(e).__name__}: {e}"
        )
        if logger:
            logger.error(msg)
        return None, msg
    
def get_lyrics_from_kkbox_url(song_url: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Scrapes lyrics from a KKBox song URL and returns them.
    Returns (None, error_message) on scraping failure or if no lyrics are found.
    Returns (lyrics, None) on success.
    """
    try:
        page_resp = throttle_request(song_url, timeout=5)
        page_content = page_resp.read().decode("utf-8")
        soup = BeautifulSoup(page_content, "html.parser")

        lyric_containers = soup.select('div[class*="lyrics"]')

        if not lyric_containers:
            msg = f"[{song_url}] No lyric containers found."
            if logger:
                logger.error(msg)
            return None, msg

        lyrics_lines = []
        for container in lyric_containers:
            container = container.find_all("p")

            if len(container) == 1:
                container = container[0]
            else:
                container = container[1]

            # for tag in container.find_all(["span", "a", "i"], recursive=True):
            #     tag.unwrap()

            # for br in container.find_all("br"):
            #     br.replace_with("\n")
            text = container.get_text().strip()
            lyrics_lines.append(text)

        lyrics = "\n".join(lyrics_lines)
        if not lyrics.strip():
            msg = f"[{song_url}] NO LYRICS - Lyrics are empty after processing."
            if logger:
                logger.error(msg)
            return None, msg

        return lyrics, None
    except Exception as e:
        msg = (
            f"[{song_url}] Failed to scrape lyrics from Genius: {type(e).__name__}: {e}"
        )
        if logger:
            logger.error(msg)
        return None, msg


def get_lyrics_from_phineas_url(song_url: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Scrape lyrics from phineasandferb.fandom.com wiki.
    Parse p tags inside mw-parser-output class.
    Return (lyrics, None) on success, (None, error_message) on failure.
    """
    try:
        # song_url = quote(song_url, safe=":/")
        song_url = smart_encode_url(song_url)
        page_resp = throttle_request(song_url, timeout=10)
        page_content = page_resp.read().decode("utf-8")
        soup = BeautifulSoup(page_content, "html.parser")

        div_tag = soup.find("div", class_="mw-parser-output")
        if not div_tag:
            msg = f"[{song_url}] No mw-parser-output found."
            if logger:
                logger.error(msg)
            return None, msg

        p_tags = div_tag.find_all("p")
        lyrics_lines = [p_tag.text.strip() for p_tag in p_tags if p_tag.text.strip()]
        lyrics = "\n".join(lyrics_lines)

        if not lyrics:
            msg = f"[{song_url}] NO LYRICS - Lyrics are empty after processing."
            if logger:
                logger.error(msg)
            return None, msg

        return lyrics, None
    except Exception as e:
        msg = f"[{song_url}] Failed to scrape lyrics from Phineas and Ferb Wiki: {type(e).__name__}: {e}"
        if logger:
            logger.error(msg)
        return None, msg


def get_lyrics_from_mlp_url(song_url: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Scrape lyrics from MLP Wiki.
    Return (lyrics, None) on success, (None, error_message) on failure.
    """
    try:
        page_resp = throttle_request(song_url, timeout=5)
        page_content = page_resp.read().decode("utf-8")
        soup = BeautifulSoup(page_content, "html.parser")

        lyrics_heading = soup.find(id="Lyrics")
        if not lyrics_heading:
            msg = f"[{song_url}] 'Lyrics' section ID not found."
            # It might not be an error if the page structure is different, but good to note.
            # logger.info(msg) # Or debug
            return None, msg

        heading_tag = lyrics_heading.find_parent("h2")
        if not heading_tag:
            msg = f"[{song_url}] Parent h2 tag for 'Lyrics' section not found."
            # logger.info(msg)
            return None, msg

        lyrics_lines = []
        for sibling in heading_tag.next_siblings:
            if sibling.name == "h2":
                break
            if sibling.name == "dl":
                dd_tags = sibling.find_all("dd", recursive=False)
                for dd_tag in dd_tags:
                    dd = dd_tag.get_text().split("\n")
                    lyrics_lines.extend(dd)
                lyrics_lines.append("")

        lyrics = "\n".join(lyrics_lines).strip()
        if not lyrics:
            msg = f"[{song_url}] NO LYRICS - Lyrics are empty after processing MLP structure."
            if logger:
                logger.warning(
                    msg
                )  # Use warning as it might indicate missing content vs error
            return None, msg

        return lyrics, None
    except Exception as e:
        msg = f"[{song_url}] Failed to scrape lyrics from MLP Wiki: {type(e).__name__}: {e}"
        if logger:
            logger.error(msg)
        return None, msg


def get_lyrics_from_lyricstranslate_url(
    song_url: str,
) -> Tuple[Optional[str], Optional[str]]:
    """
    Scrape lyrics from lyricstranslate.com.
    Parse #song-body internal structure.
    Return (lyrics, None) on success, (None, error_message) on failure.
    """
    if logger:
        logger.info(f"Attempting to scrape LyricsTranslate URL: {song_url}")
    try:
        # song_url = quote(song_url, safe=":/")
        parsed_song_url = smart_encode_url(song_url)
        if logger:
            logger.debug(f"[{parsed_song_url}] Requesting URL via throttle_request.")
        page_resp = throttle_request(parsed_song_url, timeout=10)
        if logger and page_resp:
            logger.debug(
                f"[{parsed_song_url}] Request successful, status code: {page_resp.getcode()}"
            )

        if logger:
            logger.debug(f"[{parsed_song_url}] Reading and decoding page content.")
        page_content = page_resp.read().decode("utf-8")
        if logger:
            logger.debug(f"[{parsed_song_url}] Page content read and decoded successfully.")

        if logger:
            logger.debug(f"[{parsed_song_url}] Parsing HTML content with BeautifulSoup.")
        soup = BeautifulSoup(page_content, "html.parser", from_encoding="utf-8")
        if logger:
            logger.debug(f"[{parsed_song_url}] HTML content parsed successfully.")

        if logger:
            logger.debug(f"[{parsed_song_url}] Searching for 'div#song-body'.")
        song_body = soup.find("div", id="song-body")
        if not song_body:
            msg = f"[{parsed_song_url}] No 'div#song-body' found."
            if logger:
                logger.error(msg)
            return None, msg
        if logger:
            logger.debug(f"[{parsed_song_url}] Found 'div#song-body'.")

        if logger:
            logger.debug(
                f"[{parsed_song_url}] Searching for 'div.ltf' containers within song_body."
            )
        ltf_divs = song_body.find_all("div", class_="ltf")
        if not ltf_divs:
            msg = f"[{parsed_song_url}] No 'div.ltf' container found in song_body."
            if logger:
                logger.error(msg)
            return None, msg
        if logger:
            logger.debug(f"[{parsed_song_url}] Found {len(ltf_divs)} 'div.ltf' containers.")

        lyrics_lines = []
        for ltf_div in ltf_divs:
            par_divs = ltf_div.find_all("div", class_="par")
            for par_div in par_divs:
                ll_divs = par_div.find_all(
                    "div", class_=re.compile(r"^ll-", flags=re.IGNORECASE)
                )
                for ll_div in ll_divs:
                    line = ll_div.get_text(strip=True)
                    if line:
                        lyrics_lines.append(line)
                lyrics_lines.append("")
        if logger:
            logger.debug(
                f"[{parsed_song_url}] Collected {len(lyrics_lines)} lines/segments for lyrics."
            )

        lyrics = "\n".join(
            lyrics_lines
        ).strip()  # Original was \n, if it was a mistake, it should be \n

        if not lyrics:
            msg = f"[{parsed_song_url}] Lyrics extracted but resulted in an empty string after processing."
            if logger:
                logger.error(msg)
            return None, msg

        if logger:
            logger.info(
                f"[{parsed_song_url}] Successfully extracted and processed lyrics from LyricsTranslate."
            )
        return lyrics, None

    except Exception as e:
        msg = f"[{song_url}] Failed to scrape lyrics from LyricsTranslate due to {type(e).__name__}: {str(e)}"
        if logger:
            logger.error(msg)
        return None, msg


def get_lyrics_from_smule_url(song_url: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Scrape lyrics from smule.com.
    Get lyrics data from smule API.
    Return (lyrics, None) on success, (None, error_message) on failure.
    """
    try:
        key = song_url.split("/")[-2]
        api_url = f"https://www.smule.com/api/arrangement?key={key}"
        page_resp = throttle_request(api_url, timeout=10)
        content = page_resp.read().decode("utf-8")
        data = json.loads(content)

        if "lyrics_list" not in data:
            msg = f"[{song_url}] No lyrics_list found in Smule API response."
            if logger:
                logger.error(msg)
            return None, msg

        if len(data["lyrics_list"]) > 0 and not data["lyrics_list"][0]:
            data["lyrics_list"] = data["lyrics_list"][1:]

        lyrics = "\n".join(data["lyrics_list"])

        if not lyrics.strip():
            msg = f"[{song_url}] NO LYRICS - Lyrics from Smule API are empty after processing."
            if logger:
                logger.error(msg)
            return None, msg

        return lyrics, None
    except Exception as e:
        msg = (
            f"[{song_url}] Failed to scrape lyrics from Smule: {type(e).__name__}: {e}"
        )
        if logger:
            logger.error(msg)
        return None, msg

bracket_only_pattern = re.compile(r"^\[.*?\]$")
bracket_pattern = re.compile(r"\[.*?\]")
parentheses_pattern = re.compile(r"[\(（].*?[\)）]")
character_pattern = re.compile(r"^([^(:：)]+?)[：:]\s*(.+)")


def process_lyrics(
    lyrics: str,
    remove_parentheses_enabled: bool = False,
    remove_brackets_enabled: bool = True,
    process_character_enabled: bool = False,
    process_multiply_enabled: bool = True,
) -> str:
    """
    Clean up lyrics.

    Args:
        lyrics: String to process
        remove_parentheses_enabled: Remove parentheses
        remove_brackets_enabled: Remove brackets
        process_character_enabled: Process characters
        process_multiply_enabled: Process multiply
    """

    def remove_parentheses(single_line: str) -> str:
        """Remove parentheses"""
        single_line = parentheses_pattern.sub("", single_line)
        return single_line.strip()

    def remove_bracket(single_line: str) -> str:
        """Remove brackets"""
        single_line = bracket_pattern.sub("", single_line)
        return single_line.strip()

    def nbsp_to_space(single_line):
        single_line = single_line.replace("\xa0", " ")
        single_line = single_line.replace("\u00A0", " ")
        return single_line

    def lyrics_multiply(single_line: str) -> list[str]:
        x_in_line = "x" in single_line
        mul_in_line = "×" in single_line
        if x_in_line or mul_in_line:
            if x_in_line:
                splitted_line = single_line.split("x")
            else:
                splitted_line = single_line.split("×")
            # Remove the whitespace
            multiple_line = splitted_line[0]
            multiplier = splitted_line[1].strip()
            # if multiplier is only number, make it int
            # if multiplier is a number, convert it to an int
            if multiplier.isdigit():
                multiplier = int(multiplier)
            else:
                multiplier = None

            # If correctly int val, make multple lines
            # If multiplier is a valid integer, create multiple lines
            if isinstance(multiplier, int):
                return [multiple_line] * multiplier
            else:
                return [single_line]

        return [single_line]

    def char_process(single_line: str) -> str:
        char_match = character_pattern.match(single_line)
        if char_match:
            line = char_match.group(2).strip()
            if line:
                return line
        return single_line

    def process_line(multiple_lines: list[str]) -> list[str]:
        final_lines = []
        line_started = False
        for single_line in multiple_lines:
            stripped = single_line.strip()
            empty_line = not stripped

            if bracket_only_pattern.match(stripped):
                # Skip lines that contain only parentheses
                # Skip lines that contain only brackets
                pass
            elif empty_line and not line_started:
                # Skip lines that are empty before the lyrics start
                pass
            else:
                line_started = True

                # Remove parentheses
                if not empty_line:
                    if remove_parentheses_enabled:
                        stripped = remove_parentheses(stripped)
                        if (
                            not stripped
                        ):  # If the original line is not empty but becomes empty after removing parentheses
                            continue

                if remove_brackets_enabled:
                    stripped = remove_bracket(stripped)

                if process_character_enabled:
                    stripped = char_process(stripped)

                if process_multiply_enabled:
                    final_lines.extend(lyrics_multiply(stripped))
                else:
                    final_lines.append(stripped)

        return final_lines

    lyrics = nbsp_to_space(lyrics)

    lines = lyrics.split("\n")

    final_lines = process_line(lines)
    cleaned_lyrics = "\n".join(final_lines).strip()
    return cleaned_lyrics


def get_lyrics_from_url(lyrics_url: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Fetches lyrics from a given URL, dispatching to the appropriate helper.
    Returns (lyrics_content, error_message). error_message is None on success.
    """
    try:
        if "genius.com" in lyrics_url:
            return get_lyrics_from_genius_url(lyrics_url)
        elif "phineasandferb.fandom.com" in lyrics_url:
            return get_lyrics_from_phineas_url(lyrics_url)
        elif "lyricstranslate.com" in lyrics_url:
            return get_lyrics_from_lyricstranslate_url(lyrics_url)
        elif "smule.com" in lyrics_url:
            return get_lyrics_from_smule_url(lyrics_url)
        # Add other site handlers here, e.g., mlp
        elif "mlp.fandom.com" in lyrics_url:  # Assuming this is the domain for MLP
            return get_lyrics_from_mlp_url(lyrics_url)
        elif "kkbox.com" in lyrics_url:
            return get_lyrics_from_kkbox_url(lyrics_url)
        elif "disney.fandom.com" in lyrics_url:
            return get_lyrics_from_disney_fandom_url(lyrics_url)
        else:
            msg = f"Unsupported lyrics URL format: {lyrics_url}"
            logger.warning(msg)
            return None, msg
    except Exception as e:
        msg = f"Failed to get lyrics from URL ({lyrics_url}) due to {type(e).__name__}: {str(e)}"
        logger.error(msg)
        return None, msg


def download_lyrics_for_songs(input_file: str, output_base_dir: str):
    """
    Loads song data from a JSON file and downloads lyrics.
    """
    try:
        with open(input_file, "r", encoding="utf-8") as f:
            songs_data = json.load(f)
    except FileNotFoundError:
        logger.error(f"Input file not found: {input_file}")
        return
    except json.JSONDecodeError:
        logger.error(f"Error parsing JSON from file: {input_file}")
        return

    os.makedirs(output_base_dir, exist_ok=True)
    failed_log_path = "download_failed.jsonl"
    # failed_log_path deletion
    if os.path.exists(failed_log_path):
        os.remove(failed_log_path)

    # Handle both old dict format and new array format
    if isinstance(songs_data, list):
        # New array format - convert to dict for processing
        songs_dict = {}
        for song_item in songs_data:
            if "song_title" in song_item:
                song_key = song_item["song_title"]
                # Create song_info dict with all fields except song_title
                song_info = {k: v for k, v in song_item.items() if k != "song_title"}
                songs_dict[song_key] = song_info
        songs_data = songs_dict
    elif not isinstance(songs_data, dict):
        logger.error(f"Unexpected data format in {input_file}. Expected list or dict.")
        return

    for song_key, song_info in tqdm(songs_data.items(), desc="Downloading Lyrics"):
        logger.info(f"Processing song: {song_key}")
        song_output_dir = os.path.join(output_base_dir, song_key)
        os.makedirs(song_output_dir, exist_ok=True)

        if "lyrics_url" in song_info and isinstance(song_info["lyrics_url"], dict):
            for lang_code, url in song_info["lyrics_url"].items():
                if not url:
                    logger.debug(
                        f"Skipping {lang_code} for {song_key}: No URL provided."
                    )
                    continue

                lang_dir = os.path.join(song_output_dir, lang_code)
                os.makedirs(lang_dir, exist_ok=True)
                lyrics_file_path = os.path.join(lang_dir, "lyrics.txt")

                if (
                    os.path.exists(lyrics_file_path)
                    and os.path.getsize(lyrics_file_path) > 0
                ):
                    logger.info(
                        f"Lyrics for {song_key} ({lang_code}) already exist at {lyrics_file_path}"
                    )
                    continue

                logger.info(
                    f"Downloading lyrics for {song_key} ({lang_code}) from {url}"
                )
                lyrics_content, error_detail = get_lyrics_from_url(url)

                if lyrics_content is not None:
                    processed_lyrics = process_lyrics(lyrics_content)
                    if processed_lyrics:
                        try:
                            with open(lyrics_file_path, "w", encoding="utf-8") as f_out:
                                f_out.write(processed_lyrics)
                            logger.info(f"Saved lyrics to {lyrics_file_path}")
                        except IOError as e:
                            logger.error(
                                f"Could not write lyrics to {lyrics_file_path}: {e}"
                            )
                            # This is a file write error, consider logging this to failed.jsonl if needed
                    else:
                        logger.warning(
                            f"Lyrics for {song_key} ({lang_code}) from {url} became empty after processing."
                        )
                        failure_data = {
                            "song_key": song_key,
                            "language": lang_code,
                            "url": url,
                            "reason": "Empty after processing (was not None initially)",  # More specific reason
                        }
                        try:
                            with open(
                                failed_log_path, "a", encoding="utf-8"
                            ) as f_jsonl:
                                f_jsonl.write(
                                    json.dumps(failure_data, ensure_ascii=False) + "\n"
                                )
                        except IOError as e:
                            logger.error(
                                f"Could not write to failed log {failed_log_path}: {e}"
                            )
                else:  # lyrics_content is None, meaning get_lyrics_from_url failed
                    reason_for_failure = (
                        error_detail
                        if error_detail
                        else "Failed to retrieve from URL (unknown specific reason)"
                    )
                    logger.warning(
                        f"Failed to retrieve lyrics for {song_key} ({lang_code}) from {url}. Reason: {reason_for_failure}"
                    )
                    failure_data = {
                        "song_key": song_key,
                        "language": lang_code,
                        "url": url,
                        "reason": reason_for_failure,
                    }
                    try:
                        with open(failed_log_path, "a", encoding="utf-8") as f_jsonl:
                            f_jsonl.write(
                                json.dumps(failure_data, ensure_ascii=False) + "\n"
                            )
                    except IOError as e:
                        logger.error(
                            f"Could not write to failed log {failed_log_path}: {e}"
                        )
        else:
            logger.warning(f"No 'lyrics_url' dictionary found for song: {song_key}")

    logger.info("Lyrics download process finished.")


def test_get_lyrics_from_lyricstranslate_url():
    """
    Tests the get_lyrics_from_lyricstranslate_url function.
    You should replace the test_url with an actual and valid URL from lyricstranslate.com.
    """
    # IMPORTANT: Replace this with a real, working URL from lyricstranslate.com for testing
    # For example: "https://lyricstranslate.com/en/adele-hello-lyrics.html"
    test_url = "https://lyricstranslate.com/en/example-artist-example-song-lyrics.html"  # Placeholder URL
    logger.info(
        f"--- Starting test for get_lyrics_from_lyricstranslate_url with URL: {test_url} ---"
    )

    # Ensure logging is configured if this test is run in a context where it's not already set up
    # (Though in this script, it's configured globally at the top)

    lyrics_content, error_detail = get_lyrics_from_lyricstranslate_url(test_url)

    if error_detail:
        logger.error(f"Test for {test_url} failed or an error occurred: {error_detail}")
    elif lyrics_content:
        logger.info(f"Test for {test_url} successful! Lyrics found.")
        # Print a snippet of lyrics to avoid flooding the console if they are very long
        # Using repr to see newlines as \n, which might be how they are stored by the function
        snippet = repr(
            lyrics_content[:200] + "..."
            if len(lyrics_content) > 200
            else lyrics_content
        )
        print(f"Lyrics Snippet (first 200 chars or less, with repr):\n{snippet}")
    else:
        # This case means lyrics_content is None and error_detail is also None
        logger.warning(
            f"Test for {test_url} completed. No lyrics were found, and no specific error was returned."
        )
        logger.warning(
            "This could mean the page was valid but contained no parsable lyrics, the URL led to an empty lyrics page, or the content was filtered out."
        )

    logger.info(f"--- Finished test for get_lyrics_from_lyricstranslate_url ---")


def main():
    parser = argparse.ArgumentParser(
        description="Download lyrics using URLs from a JSON file."
    )
    parser.add_argument(
        "--input",
        type=str,
        default="mavl_dataset.json",
        help="Path to the input JSON file (e.g., mavl_dataset.json)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="mavl_datasets",
        help="Base directory to save downloaded lyrics files",
    )
    args = parser.parse_args()

    download_lyrics_for_songs(args.input, args.output)


if __name__ == "__main__":
    # --- To run the Lyricstranslate specific test ---
    # 1. IMPORTANT: Update the `test_url` in the `test_get_lyrics_from_lyricstranslate_url` function
    #    with a real and valid URL from lyricstranslate.com.
    #    (A placeholder is currently used).
    # 2. Uncomment the following line to run the test:
    # test_get_lyrics_from_lyricstranslate_url()
    #
    # 3. If you run the test, you might want to comment out the `main()` call below
    #    to prevent the main script from running.
    # -------------------------------------------------

    # Default execution (main script):
    main()
