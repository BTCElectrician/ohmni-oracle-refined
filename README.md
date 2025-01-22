# Ohmni Oracle

This project processes various types of drawings (e.g., architectural, electrical, mechanical) by:
1. Extracting text from PDF files (using PyMuPDF / pdfplumber)
2. Converting it into structured JSON via GPT-4

## Installation

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd ohmni-oracle
   ```

2. **Create a virtual environment** (recommended):
   ```bash
   python -m venv venv
   source venv/bin/activate  # Linux/Mac
   venv\Scripts\activate     # Windows
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up environment variables**:
   - Copy `.env.example` to `.env`
   - Add your OpenAI API key to `.env`

5. **Run**:
   ```bash
   python main.py <input_folder> [output_folder]
   ```

## Project Structure

```
btcelectrician-ohmni_oracle/
├── config/
│   ├── settings.py
│   └── .gitignore
├── processing/
│   ├── batch_processor.py
│   ├── file_processor.py
│   └── job_processor.py
├── templates/
│   ├── a_rooms_template.json
│   ├── e_rooms_template.json
│   └── room_templates.py
├── utils/
│   ├── api_utils.py
│   ├── constants.py
│   ├── drawing_processor.py
│   ├── file_utils.py
│   ├── logging_utils.py
│   ├── pdf_processor.py
│   └── pdf_utils.py
├── .env
├── main.py
├── README.md
└── requirements.txt
```

## Features

- Processes multiple types of drawings (Architectural, Electrical, etc.)
- Extracts text and tables from PDFs
- Converts unstructured data to structured JSON
- Handles batch processing with rate limiting
- Generates room templates for architectural drawings
- Comprehensive logging and error handling

## Configuration

The following environment variables can be configured in `.env`:

- `OPENAI_API_KEY`: Your OpenAI API key (required)
- `LOG_LEVEL`: Logging level (default: INFO)
- `BATCH_SIZE`: Number of PDFs to process in parallel (default: 10)
- `API_RATE_LIMIT`: Maximum API calls per time window (default: 60)
- `TIME_WINDOW`: Time window in seconds for rate limiting (default: 60)

## License

[Your chosen license] 