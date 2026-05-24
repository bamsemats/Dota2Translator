# Dota 2 Chat Translator (Claude Vision Edition)

A high-fidelity, surgical screen-capture tool that translates in-game chat in real-time using **Claude 3.5 Sonnet Vision**.

## Key Features

- **Unified Vision Pipeline**: Replaces local OCR with Claude 3.5 Sonnet Vision. Each line is captured and sent to Claude for simultaneous high-fidelity transcription and contextual translation.
- **Perfect Multilingual Support**: Flawlessly handles Nordic diacritics (å, ä, ö), Cyrillic (Russian/Ukrainian), Asian scripts, and special characters.
- **Guided Auto-Calibration (F7)**: Automatically detects chat geometry using horizontal projection (pixel variance). Skips avatar icons and finds the perfect text alignment for your specific resolution.
- **Game-Agnostic Engine**: Driven by `chat_format.json`. Easily support any game (Dota 2, LoL, WoW, etc.) by defining a custom regex parser.
- **Bottom-Up Efficiency**: Scans for new messages from the bottom of the chat box. Includes a "seen message" memory to exit early and save API tokens when no new text is found.
- **CPU Optimized**: Environment-level fixes (`FLAGS_enable_pir_api=0`) to ensure lightning-fast PaddleOCR detection on CPU.

## Installation

### Prerequisites
- Python 3.13 (Recommended)
- Windows OS (Tested on Win32)
- Anthropic API Key (with credits)
- Google Cloud Project ID (Optional, for legacy Google Translate support)

### Setup
1. Clone the repository.
2. Install dependencies:
   ```bash
   py -3.13 -m pip install -r requirements.txt
   ```
3. Run the application:
   ```bash
   py -3.13 main.py
   ```

## Configuration

1. **Anthropic API**:
   - Go to [console.anthropic.com](https://console.anthropic.com/) and generate an API key.
   - In the app, go to **Settings** and paste the key into the **Anthropic API** section.
   - Restart the app.

2. **Calibration**:
   - In **Settings**, use "Select New Region" to draw a box around your chat area.
   - Once selected, the app will auto-calibrate.
   - **Tip**: Ensure at least 2-3 lines of chat are visible in-game, then press **F7** or use the **Recalibrate** button in settings to lock in the geometry.

3. **Custom Games**:
   - Edit `chat_format.json` to change the `parser_regex` and `system_keywords` for different games.

## Security
- `config.ini` and `calibration.json` are automatically ignored by Git. Your API keys and local monitor coordinates will never be pushed to public repositories.

## Performance
- The app uses **2x Lanczos4 upscaling** before sending images to Claude.
- **Early Exit logic** ensures that if only 1 new line appears in a 6-line chat history, only 1 API call is made.

---
*Created by Gemini CLI - May 2026*
