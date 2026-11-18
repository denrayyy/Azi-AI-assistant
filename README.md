# Azi AI Assistant

Azi is a desktop AI assistant companion for Windows that walks around your screen as an animated dog. Click the companion to open a chat window, talk with a local Ollama model, save conversation history, and use supported commands to launch apps or folders.

## Features

- Animated desktop dog with idle, walking, sleeping, and speech states
- Chat interface built with PyQt6
- Local AI responses through Ollama
- Persistent conversation memory using SQLite
- Voice-related dependencies included for future or optional interaction
- Windows app and folder command handling

## Requirements

- Windows
- Python 3.10 or newer
- Ollama installed and running locally
- An Ollama model such as `llama3`

## Setup

From the project directory:

```powershell
cd assistant
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
ollama pull llama3
python main.py
```

The application uses `http://localhost:11434` for Ollama by default.
