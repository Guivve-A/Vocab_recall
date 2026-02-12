# VocabRecall

Desktop app for building German vocabulary decks from PDF/TXT files and studying
them with SM-2 spaced repetition.

## Features

- Nested folders and deck organization.
- Import from `.pdf`, `.txt`, `.md`, `.csv`, `.tsv`.
- Automatic structured list detection (`front ; back`) or NLP extraction.
- German vocabulary extraction with spaCy, plus regex fallback when spaCy is unavailable.
- Study session with due-card mode (SM-2) and all-card review mode.
- Local SQLite storage (no cloud dependency).

## Requirements

- Python 3.10 or newer.
- Windows/macOS/Linux environment with Tk support.

## Quick Start

```bash
git clone https://github.com/Guivve-A/Vocab_recall.git
cd Vocab_recall
python -m venv .venv
```

### Activate environment

Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
```

macOS/Linux:

```bash
source .venv/bin/activate
```

### Install dependencies and run

```bash
python -m pip install -r requirements.txt
python -m spacy download de_core_news_sm
python main.py
```

## Running Tests

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

## Build Executable (optional)

```bash
python -m pip install pyinstaller
pyinstaller VocabRecall.spec
```

## Project Structure

```text
.
|-- main.py
|-- requirements.txt
|-- requirements-dev.txt
|-- core/
|-- db/
|-- ui/
|-- tests/
|-- assets/
|-- ejemplo_vocabulario.txt
`-- VocabRecall.spec
```

## Notes

- The app stores local data in `data/vocabrecall.db`.
- This database file is ignored by git and not committed.

## License

MIT. See `LICENSE`.
