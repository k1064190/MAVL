# MAVL: Multilingual Audio-Video Lyrics Dataset for Animated Song Translation

<div align="center">
  <img src="assets/mavl_logo.png" alt="MAVL Dataset Overview" width="200">
</div>

[![Hugging Face Dataset](https://img.shields.io/badge/%F0%9F%A4%97%20Hugging%20Face-MAVL-blue)](https://huggingface.co/datasets/Noename/MAVL)
[![arXiv](https://img.shields.io/badge/arXiv-2505.18614-b31b1b.svg)](https://arxiv.org/abs/2505.18614)

This repository provides code and resources for working with the Multilingual Audio-Video Lyrics (MAVL) dataset, available on Hugging Face ([https://huggingface.co/datasets/Noename/MAVL](https://huggingface.co/datasets/Noename/MAVL)). The MAVL dataset is described in detail in the paper "[MAVL: A Multilingual Audio-Video Lyrics Dataset for Animated Song Translation](https://arxiv.org/abs/2505.18614)".

## Dataset Description

The MAVL dataset contains a collection of YouTube URLs corresponding to songs from animated musicals. It includes meticulously aligned lyrics (English, Spanish, French, Korean, and Japanese) with corresponding timestamps, song titles, and artist information. MAVL is designed as the first multilingual, multimodal benchmark for singable lyrics translation.

**Crucially, this dataset does not contain the actual audio, video, or full lyric text files directly due to copyright considerations.** Instead, it provides structured metadata and URLs, along with a compact representation of lyrics (e.g., first letters of words, first/last words of lines) and their syllable counts, and precise timestamps. This allows for the reconstruction of original lyrics and the download of associated multimedia content via provided scripts.

## Dataset Structure

The dataset is provided in a JSON format. Each entry represents a song and contains:

* **Song Title:** The name of the animated song.
* **`lyrics`**: A nested structure containing lyric lines for each language (`US_og` for original English, `ES` for Spanish, `FR` for French, `KO` for Korean, `JA` for Japanese). Each line includes:
    * `text`: A compact representation of the original lyric line (e.g., `[["Tsimp", "There's", "pants"]]` for "Squirrels in my pants"). This is designed to allow for the reconstruction of the full lyric text using external resources.
    * `line_number`: The sequential number of the lyric line.
    * `syllable_count`: The syllable count of the lyric line.
    * `start`: Start timestamp of the lyric line in the audio/video.
    * `end`: End timestamp of the lyric line in the audio/video.
* **`youtube_url`**: Dictionary containing YouTube URLs for the original and dubbed versions in different languages.
* **`lyrics_url`**: Dictionary containing URLs to external websites where the full lyrics can be found for each language.
* **`video`**: Boolean flags indicating the availability of video for each language.

## Usage Instructions

### Prerequisites

1. **Install required dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Download the MAVL dataset** from Hugging Face:
   ```bash
   # Download mavl_dataset.json from https://huggingface.co/datasets/Noename/MAVL
   # Place it in your working directory
   ```

### Step 1: Download Full Lyrics

The first step is to download the complete lyrics from the URLs provided in the dataset:

```bash
python dataset/download_lyrics.py --input mavl_dataset.json --output mavl_datasets
```

**Parameters:**
- `--input`: Path to the MAVL dataset JSON file (default: `mavl_dataset.json`)
- `--output`: Base directory where lyrics will be saved (default: `mavl_datasets`)

This creates a directory structure like:
```
mavl_datasets/
├── Song Title 1/
│   ├── US_og/
│   │   └── lyrics.txt
│   ├── ES/
│   │   └── lyrics.txt
│   └── ...
└── Song Title 2/
    └── ...
```

**Note:** This process may take some time as it respects rate limits for lyrics websites. Failed downloads are logged to `download_failed.jsonl`.

### Step 2: Restore Complete Lyrics

After downloading the lyrics, restore the full text from the compact representation:

```bash
python dataset/restore_lyrics.py
```

This script:
- Uses the compact clues in `mavl_dataset.json` 
- Matches them with the downloaded lyrics in `mavl_datasets/`
- Outputs complete lyrics to `mavl_dataset_restored.json`

The restored dataset contains the full lyric text instead of the compact representation.

### Step 3: Download YouTube Videos and Audio

To download the multimedia content:

```bash
python dataset/download_yt.py --input mavl_dataset.json --output mavl_datasets
```

**Parameters:**
- `--input`: Path to the MAVL dataset JSON file (default: `mavl_dataset.json`)
- `--output`: Base directory where videos and audio will be saved (default: `mavl_datasets`)

This downloads:
- `video.mp4`: The YouTube video file
- `audio.wav`: Extracted audio in WAV format

Directory structure after this step:
```
mavl_datasets/
├── Song Title 1/
│   ├── US_og/
│   │   ├── lyrics.txt
│   │   ├── video.mp4
│   │   └── audio.wav
│   └── ...
└── ...
```

**Requirements:** This step requires `yt-dlp` and `ffmpeg` to be installed on your system.

### Step 4: Process Lyrics for Copyright Protection (Optional)

If you need to create a copyright-protected version of full lyrics:

```bash
python dataset/process_lyrics.py --lyrics_path mavl_dataset_restored.json --output_path copyright_protected_lyrics.json
```

This reverses the restoration process, converting full lyrics back to compact representations.

## Code Descriptions

  * **`dataset/download_lyrics.py`**: This script downloads the full lyrics from the `lyrics_url` provided in the MAVL dataset.
  * **`dataset/restore_lyrics.py`**: This script reconstructs the original lyrics from the compact representation provided in the dataset.
  * **`dataset/download_yt.py`**: This script downloads the video and audio files from the YouTube URLs specified in the dataset.
  * **`dataset/process_lyrics.py`**: This script processes the full lyrics to generate a copyright-protected representation, as used in the MAVL dataset (e.g., first letters of words, syllable counts).
  * **`ipa_converter/`**: This directory contains code for converting lyrics to the International Phonetic Alphabet (IPA) using the `epitran` library. It includes:
      * `epitran_utils.py`: Utility functions for IPA conversion.
      * `valid_mappings.csv`: Mappings for handling specific characters or words during IPA conversion.
      * `test.py`: Test scripts for the IPA converter.
      * The code in this directory handles numerical and other non-alphabetic characters by converting them to their written-out forms in the target language before IPA conversion. It also includes logic to handle embedded English words within other languages.
  * **`language_processors/`**: This directory contains language-specific transliteration tools used by the `ipa_converter`.
  * **`process_syllable/`**: This directory contains code for counting syllables in each language. It includes:
      * Language-specific syllable counting scripts (e.g., `english.py`, `korean.py`).
      * A `syllabifier/` subdirectory with resources and code for syllabification, including:
          * CMU dictionary files for English.
          * Scripts for parsing the CMU dictionary and performing syllabification.


## Technical Attributions for Processing Tools

The MAVL dataset's detailed annotations, including syllable counts and IPA transcriptions, rely on several external tools and libraries. We acknowledge and appreciate the work of their respective creators. The specific tools used for each language for syllable counting and IPA conversion are detailed in Table 20 of our accompanying paper and are summarized below:

### Syllable Counting Tools

* **English:** Utilizes the `Syllabifier` tool, often associated with the [CMU Pronouncing Dictionary](http://www.speech.cs.cmu.edu/cgi-bin/cmudict) for phoneme-based syllabification.
* **Spanish:** Employs the python-ported version of [count-syllables-in-spanish](https://github.com/pablolucianop/count-syllables-in-spanish).
* **French:** Leverages the python-ported version of [syllabify-fr](https://github.com/UrielCh/syllabify-fr).
* **Korean:** Syllable count is determined by the `length of text`, referring to the number of Hangul blocks (characters).
* **Japanese:** Uses the enhanced, python-ported version of [japanese-mora-counter](https://github.com/grocio/japanese-mora-counter) to count morae, which serve as the rhythmic unit in Japanese.

### IPA Conversion Tools

* **All Languages (English, Spanish, French, Korean, Japanese):** All IPA transcriptions are generated using `epitran` ([https://github.com/dmort27/epitran](https://github.com/dmort27/epitran)), a Python library for transcribing orthographic text into IPA.
    * For English, `epitran` can optionally leverage the [CMU Pronouncing Dictionary](http://www.speech.cs.cmu.edu/cgi-bin/cmudict) for improved accuracy.
    * The `language_processors` directory in this repository includes custom logic to preprocess numbers and handle embedded English words before `epitran` conversion for better cross-lingual consistency.

## Intended Uses & Limitations

This dataset is intended solely for **non-commercial research purposes**, such as lyrics translation, music-lyrics alignment, music information retrieval, and multimodal language model development.

**IMPORTANT LIMITATIONS:**

  * Users must independently ensure their use of the content linked via URLs complies with copyright law and YouTube's Terms of Service.
  * The dataset provides only URLs and research-generated metadata/annotations; it does not grant any rights to the underlying copyrighted content.
  * YouTube links and external lyrics links may become invalid over time.
  * The dataset primarily focuses on animated musicals and may not generalize to all musical genres or styles.
  * The current lyric representation requires external processing to reconstruct full lyric text.

## License

This dataset is distributed under the **CC BY-NC 4.0 (Creative Commons Attribution-NonCommercial 4.0 International)** license (see the `LICENSE` file for full details). Key points include:

  * **Attribution (BY):** You must give appropriate credit to the original creators ([Woohyun Cho/MIRLAB]).
  * **NonCommercial (NC):** You may not use the dataset for commercial purposes.
  * **Underlying Content Ownership:** It is crucial to understand that **this dataset does not grant any rights to the copyrighted songs/videos** linked via YouTube URLs or the full lyric texts obtained from external sources. Users are solely responsible for ensuring their use of this content complies with applicable copyright laws and YouTube's Terms of Service.
  * **Dataset Compilation & Annotations:** Permission is granted to use, copy, and modify the URL compilation and any original annotations (such as timestamps, syllable counts, and IPA transcriptions) for non-commercial research, provided attribution is given to the dataset creators ([Woohyun Cho/MIRLAB]) and the license terms are followed. This metadata, compiled by our research, can be freely adapted for non-commercial purposes with proper acknowledgment.
  * **NO WARRANTY:** The dataset is provided "AS IS" without warranty. Links may become broken over time.
  * **Liability:** The dataset creators are not liable for any issues arising from the use of the dataset or the linked content.

## Citation

If you use the MAVL dataset in your research, please cite our paper:

```bibtex
@misc{cho2025mavlmultilingualaudiovideolyrics,
      title={MAVL: A Multilingual Audio-Video Lyrics Dataset for Animated Song Translation},
      author={Woohyun Cho and Youngmin Kim and Sunghyun Lee and Youngjae Yu},
      year={2025},
      eprint={2505.18614},
      archivePrefix={arXiv},
      primaryClass={cs.CL},
      url={[https://arxiv.org/abs/2505.18614](https://arxiv.org/abs/2505.18614)},
}
```