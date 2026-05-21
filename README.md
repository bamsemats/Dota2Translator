# Dota 2 Chat Translator (High-Performance PaddleOCR Edition)

A specialized computer vision pipeline for real-time game chat translation. This tool is specifically engineered to handle the unique challenges of in-game OCR: transparent backgrounds, stylized fonts, and 4K screen resolutions.

## Core Architecture (May 21, 2026 Refactor)

- **Temporal Blending (Multi-Frame):** Captures 3 high-speed frames (70ms total) and merges them to suppress moving terrain noise.
- **PaddleOCRv5 Mobile Engine:** Uses the latest lightweight models for high accuracy with sub-2-second latency.
- **Surgical Geometry Merging:** OCR fragments are grouped by vertical center and **strictly sorted horizontally** by their start position. This ensures `[Tag] Sender: Message` is reassembled in the correct order, even if detected out of sequence.
- **4K Efficiency Pass:** Caps OCR detection resolution at 1600px and preprocessing at 2000px width. This prevents the "20-second lag" seen on high-res systems while keeping characters sharp.
- **Visual Anchor Pivots:** Combines CV-based colon detection with regex parsing to group multi-line wrapped messages.

## Key Features

- **Inclusive Language Support:** Optimized for Japanese Kanji, Cyrillic, and Latin-based languages (Swedish, Spanish, etc.) using `PP-OCRv5 Multilingual`.
- **Hinted Language Detection:** Filters `langdetect` results against your dashboard settings to prevent false positives (e.g., misidentifying Swedish as Dutch).
- **Instant UI Preview:** Captures and displays the chat region immediately upon hotkey press for a responsive feel.
- **Original-Text Deduplication:** Checks raw OCR text before translation, allowing multiple foreign phrases with identical English meanings to be displayed.
- **Discord-Inspired UI:** High-contrast, theme-aware chat log with persistent sender registry.

## Prerequisites

- **Python 3.13:** Required. (Python 3.14 is currently unsupported by `paddlepaddle`).
- **Google Cloud Project:** Required for the Cloud Translation API.

## Installation

```bash
# 1. Clone & Enter
git clone <repository-url>
cd Dota2ChatTranslater

# 2. Virtual Environment (Recommended)
py -3.13 -m venv venv
venv\Scripts\activate

# 3. Install Dependencies
pip install -r requirements.txt
```

## Running the App

Always use the Python 3.13 launcher:
```bash
py -3.13 main.py
```

## Technical Roadmap & TODO

- [ ] **OCR Fine-Tuning:** Improve accuracy for intricate, thin-stroke characters (Kanji/Hanzi).
- [ ] **Rare Language Support:** Expand specific model mappings for uncommon scripts and edge cases.
- [ ] **Adaptive Thresholding:** Research localized binarization that preserves player color information.
- [ ] **Multi-Threaded Translation:** Decouple API calls from the OCR thread for parallel UI updates.
