Directory structure:
└── btcelectrician-ohmni-oracle-refined/
    ├── README.md
    ├── UPGRADE-DOCU-INT.md
    ├── main.py
    ├── requirements.txt
    ├── snapshot.md
    ├── test_azure_panel.py
    ├── .cursorrules
    ├── .env.example
    ├── config/
    │   ├── __init__.py
    │   └── settings.py
    ├── processing/
    │   ├── __init__.py
    │   ├── batch_processor.py
    │   ├── file_processor.py
    │   ├── job_processor.py
    │   ├── panel_schedule_intelligence.py
    │   └── panel_schedule_intelligence_backup.py
    ├── templates/
    │   ├── __init__.py
    │   ├── a_rooms_template.json
    │   ├── e_rooms_template.json
    │   └── room_templates.py
    └── utils/
        ├── __init__.py
        ├── api_utils.py
        ├── constants.py
        ├── drawing_processor.py
        ├── drawing_utils.py
        ├── file_utils.py
        ├── logging_utils.py
        ├── pdf_processor.py
        └── pdf_utils.py


Files Content:

================================================
File: README.md
================================================
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

================================================
File: main.py
================================================
import os
import sys
import asyncio
import logging

from openai import AsyncOpenAI
from config.settings import OPENAI_API_KEY
from utils.logging_utils import setup_logging
from processing.job_processor import process_job_site_async

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python main.py <input_folder> [output_folder]")
        sys.exit(1)
    
    job_folder = sys.argv[1]
    output_folder = sys.argv[2] if len(sys.argv) > 2 else os.path.join(job_folder, "output")
    
    if not os.path.exists(job_folder):
        print(f"Error: Input folder '{job_folder}' does not exist.")
        sys.exit(1)
    
    # 1) Set up logging
    setup_logging(output_folder)
    logging.info(f"Processing files from: {job_folder}")
    logging.info(f"Output will be saved to: {output_folder}")
    
    # 2) Create OpenAI Client
    client = AsyncOpenAI(api_key=OPENAI_API_KEY)
    
    # 3) Run asynchronous job processing
    asyncio.run(process_job_site_async(job_folder, output_folder, client))


================================================
File: requirements.txt
================================================
aiohappyeyeballs==2.4.4
aiohttp==3.11
aiosignal==1.3.2
annotated-types==0.7.0
anyio==4.8.0
attrs==24.3.0
azure-ai-documentintelligence==1.0.0
azure-core>=1.32.0
certifi==2024.12.14
cffi==1.17.1
charset-normalizer==3.4.1
cryptography==44.0.0
distro==1.9.0
frozenlist==1.4.1
h11==0.14.0
httpcore==1.0.7
httpx==0.28.1
idna==3.10
jiter==0.8.2
multidict==6.1.0
openai==1.59.8
pillow==10.4.0
pycparser==2.22
pydantic==2.10.5
pydantic_core==2.27.2
PyMuPDF==1.24.11
pypdfium2==4.30.0
python-dotenv==1.0.1
requests==2.32.3
sniffio==1.3.1
tqdm==4.66.5
typing_extensions==4.12.2
urllib3==2.2.3
Wand==0.6.13
yarl==1.17.0


================================================
File: test_azure_panel.py
================================================
#!/usr/bin/env python
import os
import sys
import json
import logging
import asyncio

from dotenv import load_dotenv
from processing.panel_schedule_intelligence import PanelScheduleProcessor
from processing.file_processor import is_panel_schedule
from utils.pdf_processor import extract_text_and_tables_from_pdf

def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )

async def main():
    """
    Usage:
      python test_azure_panel.py <pdf_file_or_folder>
    """
    if len(sys.argv) < 2:
        print("Usage: python test_azure_panel.py <pdf_file_or_folder>")
        sys.exit(1)

    path_arg = sys.argv[1]
    if not os.path.exists(path_arg):
        print(f"Error: Path '{path_arg}' does not exist.")
        sys.exit(1)

    load_dotenv()
    endpoint = os.getenv("DOCUMENTINTELLIGENCE_ENDPOINT")
    api_key = os.getenv("DOCUMENTINTELLIGENCE_API_KEY")
    if not endpoint or not api_key:
        logging.error("Azure Document Intelligence credentials not found in environment.")
        sys.exit(1)

    panel_processor = PanelScheduleProcessor(endpoint=endpoint, api_key=api_key)

    # Gather PDF files
    pdf_files = []
    if os.path.isfile(path_arg) and path_arg.lower().endswith(".pdf"):
        pdf_files.append(path_arg)
    elif os.path.isdir(path_arg):
        for root, _, files in os.walk(path_arg):
            for f in files:
                if f.lower().endswith(".pdf"):
                    pdf_files.append(os.path.join(root, f))
    else:
        logging.error(f"No valid PDF or folder at: {path_arg}")
        sys.exit(1)

    if not pdf_files:
        logging.warning(f"No PDF files found at '{path_arg}'")
        return

    output_folder = os.path.join(os.getcwd(), "test_output")
    os.makedirs(output_folder, exist_ok=True)

    for pdf_path in pdf_files:
        file_name = os.path.basename(pdf_path)
        if is_panel_schedule(file_name, ""):
            logging.info(f"Detected panel schedule in '{file_name}'. Processing with Azure Document Intelligence...")
            panel_data = None  # keep track of the result or error

            try:
                # Optional text extraction, just for logs
                raw_content = await extract_text_and_tables_from_pdf(pdf_path)
                logging.info(f"Extracted PDF content length: {len(raw_content)} characters")

                # Call the specialized method
                panel_data = await panel_processor.process_panel_schedule(pdf_path)
                logging.info(f"Successfully processed '{file_name}' via Azure Document Intelligence.")

            except Exception as e:
                # If there's any unhandled error
                logging.exception(f"Error processing panel schedule '{file_name}': {str(e)}")
                # We'll store an error JSON

            finally:
                # ALWAYS write some JSON, even if error
                if panel_data is None:
                    panel_data = {
                        "PanelName": "",
                        "circuits": [],
                        "GenericPanelTypes": {},
                        "error": "Failed to process panel schedule"
                    }

                base_name = os.path.splitext(file_name)[0]
                output_file = os.path.join(output_folder, f"{base_name}_test_panel.json")
                with open(output_file, "w") as f:
                    json.dump(panel_data, f, indent=2)

                logging.info(f"Wrote output to '{output_file}'")

        else:
            logging.info(f"'{file_name}' does NOT appear to be a panel schedule. Skipping.")

if __name__ == "__main__":
    setup_logging()
    asyncio.run(main())


================================================
File: .cursorrules
================================================
Commit Message Prefixes:
* "fix:" for bug fixes
* "feat:" for new features
* "perf:" for performance improvements
* "docs:" for documentation changes
* "style:" for formatting changes
* "refactor:" for code refactoring
* "test:" for adding missing tests
* "chore:" for maintenance tasks
Rules:
* Use lowercase for commit messages
* Keep the summary line concise
* Include description for non-obvious changes
* Reference issue numbers when applicable
Documentation

* Maintain clear README with setup instructions
* Document API interactions and data flows
* Keep manifest.json well-documented
* Don't include comments unless it's for complex logic
* Document permission requirements
Development Workflow

* Use proper version control
* Implement proper code review process
* Test in multiple environments
* Follow semantic versioning for releases
* Maintain changelog


================================================
File: .env.example
================================================
# OpenAI API Configuration
OPENAI_API_KEY=your_openai_key_here

# Azure Document Intelligence Configuration
DOCUMENTINTELLIGENCE_ENDPOINT=<yourEndpoint>
DOCUMENTINTELLIGENCE_API_KEY=<yourKey>

# Optional Configuration
# LOG_LEVEL=INFO
# BATCH_SIZE=10
# API_RATE_LIMIT=60
# TIME_WINDOW=60 

================================================
File: config/settings.py
================================================
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# OpenAI API Configuration
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY must be set in environment variables")

# Logging Configuration
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')

# Processing Configuration
BATCH_SIZE = int(os.getenv('BATCH_SIZE', '10'))
API_RATE_LIMIT = int(os.getenv('API_RATE_LIMIT', '60'))
TIME_WINDOW = int(os.getenv('TIME_WINDOW', '60'))

# Template Configuration
TEMPLATE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'templates') 

================================================
File: processing/__init__.py
================================================
# Processing package initialization 

================================================
File: processing/batch_processor.py
================================================
import time
import asyncio
import logging

from processing.file_processor import process_pdf_async
from utils.constants import get_drawing_type

API_RATE_LIMIT = 60  # Adjust if needed
TIME_WINDOW = 60     # Time window to respect the rate limit

async def process_batch_async(batch, client, output_folder, templates_created):
    """
    Given a batch of PDF file paths, process each one asynchronously,
    respecting the API rate limit (API_RATE_LIMIT calls per TIME_WINDOW).
    """
    tasks = []
    start_time = time.time()

    for index, pdf_file in enumerate(batch):
        # Rate-limit control
        if index > 0 and index % API_RATE_LIMIT == 0:
            elapsed = time.time() - start_time
            if elapsed < TIME_WINDOW:
                await asyncio.sleep(TIME_WINDOW - elapsed)
            start_time = time.time()
        
        drawing_type = get_drawing_type(pdf_file)
        tasks.append(
            process_pdf_async(
                pdf_path=pdf_file,
                client=client,
                output_folder=output_folder,
                drawing_type=drawing_type,
                templates_created=templates_created
            )
        )
    
    return await asyncio.gather(*tasks)


================================================
File: processing/file_processor.py
================================================
import os
import json
import logging
from tqdm.asyncio import tqdm
import re
from dotenv import load_dotenv

from utils.pdf_processor import extract_text_and_tables_from_pdf
from utils.drawing_processor import process_drawing
from templates.room_templates import process_architectural_drawing
from .panel_schedule_intelligence import PanelScheduleProcessor

# Load environment variables
load_dotenv()

# Initialize panel schedule processor if credentials are available
panel_processor = None
AZURE_ENDPOINT = os.getenv("DOCUMENTINTELLIGENCE_ENDPOINT")
AZURE_API_KEY = os.getenv("DOCUMENTINTELLIGENCE_API_KEY")

if AZURE_ENDPOINT and AZURE_API_KEY:
    panel_processor = PanelScheduleProcessor(endpoint=AZURE_ENDPOINT, api_key=AZURE_API_KEY)

def is_panel_schedule(file_name: str, raw_content: str) -> bool:
    """
    Determine if a PDF is likely an electrical panel schedule
    based solely on the file name (no numeric or content checks).
    
    Args:
        file_name (str): Name of the PDF file
        raw_content (str): (Unused) Extracted text content from the PDF
        
    Returns:
        bool: True if the file name contains certain panel-schedule keywords
    """
    # We skip numeric references entirely and rely on these keywords (both spaced and hyphenated):
    panel_keywords = [
        "electrical panel schedule",
        "panel schedule",
        "panel schedules",
        "power schedule",
        "lighting schedule",
        # ADDITIONAL HYPHENATED VERSIONS:
        "electrical-panel-schedule",
        "panel-schedule",
        "panel-schedules",
        "power-schedule",
        "lighting-schedule"
    ]
    file_name_lower = file_name.lower()
    
    return any(keyword in file_name_lower for keyword in panel_keywords)

async def process_pdf_async(
    pdf_path,
    client,
    output_folder,
    drawing_type,
    templates_created
):
    """
    Process a single PDF asynchronously:
      1) For electrical panel schedules, use Azure Document Intelligence
      2) For other drawings, use the standard GPT pipeline
    """
    file_name = os.path.basename(pdf_path)
    with tqdm(total=100, desc=f"Processing {file_name}", leave=False) as pbar:
        try:
            pbar.update(10)  # Start
            raw_content = await extract_text_and_tables_from_pdf(pdf_path)
            pbar.update(20)  # PDF text/tables extracted

            # Check if this is an electrical panel schedule
            if drawing_type == "Electrical" and panel_processor and is_panel_schedule(file_name, raw_content):
                logging.info(f"Detected electrical panel schedule in {file_name}. Using Azure Document Intelligence.")
                
                try:
                    # Process with Azure Document Intelligence
                    panel_data = await panel_processor.process_panel_schedule(pdf_path)
                    pbar.update(40)  # Azure processing done
                    
                    # Save to PanelSchedules subfolder
                    panel_folder = os.path.join(output_folder, "PanelSchedules")
                    os.makedirs(panel_folder, exist_ok=True)
                    
                    output_filename = os.path.splitext(file_name)[0] + '_panel.json'
                    output_path = os.path.join(panel_folder, output_filename)
                    
                    with open(output_path, 'w') as f:
                        json.dump(panel_data, f, indent=2)
                    
                    pbar.update(30)  # JSON saved
                    logging.info(f"Successfully processed panel schedule: {output_path}")
                    return {"success": True, "file": output_path, "panel_schedule": True}
                    
                except Exception as e:
                    logging.error(f"Azure Document Intelligence processing failed for {file_name}: {str(e)}")
                    logging.info("Falling back to standard GPT processing...")
                    # Continue with standard processing if Azure fails
            
            # Standard GPT processing for non-panel schedules or fallback
            structured_json = await process_drawing(raw_content, drawing_type, client)
            pbar.update(40)  # GPT processing done
            
            type_folder = os.path.join(output_folder, drawing_type)
            os.makedirs(type_folder, exist_ok=True)

            # Attempt to parse JSON response
            try:
                parsed_json = json.loads(structured_json)
                output_filename = os.path.splitext(file_name)[0] + '_structured.json'
                output_path = os.path.join(type_folder, output_filename)
                
                with open(output_path, 'w') as f:
                    json.dump(parsed_json, f, indent=2)
                
                pbar.update(20)  # JSON saved
                logging.info(f"Successfully processed and saved: {output_path}")
                
                # If Architectural, generate room templates
                if drawing_type == 'Architectural':
                    result = process_architectural_drawing(parsed_json, pdf_path, type_folder)
                    templates_created['floor_plan'] = True
                    logging.info(f"Created room templates: {result}")
                
                pbar.update(10)  # Finishing
                return {"success": True, "file": output_path, "panel_schedule": False}
            
            except json.JSONDecodeError as e:
                pbar.update(100)
                logging.error(f"JSON parsing error for {pdf_path}: {str(e)}")
                logging.info(f"Raw API response: {structured_json}")
                
                raw_output_filename = os.path.splitext(file_name)[0] + '_raw_response.json'
                raw_output_path = os.path.join(type_folder, raw_output_filename)
                
                with open(raw_output_path, 'w') as f:
                    f.write(structured_json)
                
                logging.warning(f"Saved raw API response to {raw_output_path}")
                return {"success": False, "error": "Failed to parse JSON", "file": pdf_path}
        
        except Exception as e:
            pbar.update(100)
            logging.error(f"Error processing {pdf_path}: {str(e)}")
            return {"success": False, "error": str(e), "file": pdf_path}


================================================
File: processing/job_processor.py
================================================
import os
import logging
import asyncio
from tqdm.asyncio import tqdm

from utils.file_utils import traverse_job_folder
from processing.batch_processor import process_batch_async

async def process_job_site_async(job_folder, output_folder, client):
    """
    Orchestrates processing of a 'job site,' i.e., an entire folder of PDF files.
    """
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)
    
    pdf_files = traverse_job_folder(job_folder)
    logging.info(f"Found {len(pdf_files)} PDF files in {job_folder}")
    
    if not pdf_files:
        logging.warning("No PDF files found. Please check the input folder.")
        return
    
    templates_created = {"floor_plan": False}
    batch_size = 10
    total_batches = (len(pdf_files) + batch_size - 1) // batch_size
    
    all_results = []
    with tqdm(total=len(pdf_files), desc="Overall Progress") as overall_pbar:
        for i in range(0, len(pdf_files), batch_size):
            batch = pdf_files[i:i+batch_size]
            logging.info(f"Processing batch {i//batch_size + 1} of {total_batches}")
            
            batch_results = await process_batch_async(batch, client, output_folder, templates_created)
            all_results.extend(batch_results)
            
            successes = [r for r in batch_results if r['success']]
            failures = [r for r in batch_results if not r['success']]
            
            overall_pbar.update(len(batch))
            logging.info(f"Batch completed. Successes: {len(successes)}, Failures: {len(failures)}")
            
            for failure in failures:
                logging.error(f"Failed to process {failure['file']}: {failure['error']}")

    successes = [r for r in all_results if r['success']]
    failures = [r for r in all_results if not r['success']]
    
    logging.info(f"Processing complete. Total successes: {len(successes)}, Total failures: {len(failures)}")
    if failures:
        logging.warning("Failures:")
        for failure in failures:
            logging.warning(f"  {failure['file']}: {failure['error']}")


================================================
File: processing/panel_schedule_intelligence.py
================================================
# processing/panel_schedule_intelligence.py

from azure.core.credentials import AzureKeyCredential
from azure.ai.documentintelligence import DocumentIntelligenceClient
import os
import logging
import json
from typing import Dict, List
import re

# NEW: Use the AsyncOpenAI client
from openai import AsyncOpenAI

# Optional regex for typical panel name patterns like "L1", "H2", "A125", etc.
PANEL_NAME_PATTERN = re.compile(r'^[A-Z]{1,3}\d{1,3}$')

class PanelScheduleProcessor:
    """
    Processes an electrical panel schedule PDF using:
      1) Azure Document Intelligence (prebuilt-layout) to extract tables
      2) GPT to interpret table columns (header row) and map them to circuit fields
    """

    def __init__(self, endpoint: str, api_key: str, **kwargs):
        """
        :param endpoint: Azure Document Intelligence endpoint URL
        :param api_key: Azure Document Intelligence API key
        :param kwargs: optional arguments for config (batch_size, timeout, etc.)
        """
        self.logger = logging.getLogger(__name__)

        # Azure Document Intelligence client
        self.document_client = DocumentIntelligenceClient(
            endpoint=endpoint,
            credential=AzureKeyCredential(api_key)
        )

        # GPT (OpenAI) configuration
        self.openai_api_key = os.getenv("OPENAI_API_KEY")
        if not self.openai_api_key:
            raise ValueError("OPENAI_API_KEY must be set for GPT usage.")

        # NEW: Initialize the async OpenAI client
        self.client = AsyncOpenAI(api_key=self.openai_api_key)

        # Optional custom settings
        self.batch_size = kwargs.get('batch_size', 1)
        self.timeout = kwargs.get('timeout', 300)

    async def process_panel_schedule(self, file_path: str) -> Dict:
        """
        Main entry point: parse a panel schedule PDF into a structured dict.

        Returns a structure like:
        {
          "PanelName": "L1",
          "GenericPanelTypes": {
             "LoadCenter": {...},
             "MainPanel": {...},
             "DistributionPanel": {...}
          },
          "circuits": [...],   # array of circuit objects
          "error": None or "some error message"
        }
        """
        fallback_output = {
            "PanelName": "",
            "GenericPanelTypes": {
                "LoadCenter": {},
                "MainPanel": {},
                "DistributionPanel": {}
            },
            "circuits": [],
            "error": None
        }

        try:
            # Read the PDF file as bytes
            with open(file_path, "rb") as f:
                pdf_bytes = f.read()

            # 1) Analyze the PDF with Azure Document Intelligence (prebuilt-layout)
            poller = self.document_client.begin_analyze_document(
                "prebuilt-layout",
                pdf_bytes,
                content_type="application/pdf"
            )
            result = poller.result()
            self.logger.info(f"DEBUG: Azure analysis complete for {file_path}")

            # 2) Extract any top-level panel data (like PanelName)
            extracted_data = self._extract_panel_data(result)

            # 3) Use GPT to interpret each table’s header and map the data into circuit objects
            circuit_info = await self._extract_circuit_data_with_gpt(result)

            final_output = {
                "PanelName": extracted_data.get("PanelName", ""),
                "GenericPanelTypes": {
                    "LoadCenter": extracted_data.get("LoadCenter", {}),
                    "MainPanel": extracted_data.get("MainPanel", {}),
                    "DistributionPanel": extracted_data.get("DistributionPanel", {})
                },
                "circuits": circuit_info,
                "error": None
            }
            return final_output

        except Exception as e:
            self.logger.exception(f"Azure/GPT processing failed for {file_path}")
            fallback_output["error"] = str(e)
            return fallback_output

    def _extract_panel_data(self, result) -> Dict:
        """
        Scans recognized tables for a possible panel name or any top-level data.
        Returns a dict with:
          "PanelName": "L1" (if found)
          "LoadCenter": {...}, "MainPanel": {...}, "DistributionPanel": {...}
        (You can expand or customize as needed.)
        """
        self.logger.info("DEBUG: Entering _extract_panel_data method")

        # Basic default structure
        parsed_data = {
            "PanelName": "",
            "LoadCenter": {
                "panelboard_schedule": {}
            },
            "MainPanel": {
                "panel": {}
            },
            "DistributionPanel": {
                "panel": {}
            }
        }

        # If no tables recognized, nothing more we can do here
        if not hasattr(result, "tables") or not result.tables:
            self.logger.warning("No tables in result. No panel name found.")
            return parsed_data

        # Optionally: Attempt to detect "PanelName" by scanning each cell with a regex
        for table in result.tables:
            for cell in table.cells:
                text = cell.content.strip()
                if PANEL_NAME_PATTERN.match(text):
                    parsed_data["PanelName"] = text
                    self.logger.info(f"Found panel name: {text}")
                    # break after first match, or remove if you want multiple matches
                    return parsed_data

        return parsed_data

    async def _extract_circuit_data_with_gpt(self, result) -> List[Dict]:
        """
        Iterates over recognized tables. For each table:
          1) Identify which row is likely the header row
          2) Ask GPT to map those header columns to a known set of fields
          3) Parse all subsequent rows into circuit objects using that mapping

        Returns a list of circuit dictionaries.
        """
        circuits = []

        if not hasattr(result, "tables") or not result.tables:
            self.logger.info("No tables found in result. Returning empty circuit list.")
            return circuits

        for t_idx, table in enumerate(result.tables):
            self.logger.info(f"Analyzing table {t_idx} with row_count={table.row_count}, col_count={table.column_count}")

            # (A) Choose a "header row"—here, we'll pick whichever row has the most text
            header_row_idx = self._guess_header_row(table)
            if header_row_idx < 0:
                self.logger.info("No plausible header row. Skipping this table.")
                continue

            # (B) Gather the text of the header row into a list
            header_cells = [c for c in table.cells if c.row_index == header_row_idx]
            header_cells_sorted = sorted(header_cells, key=lambda x: x.column_index)
            header_text_list = [cell.content.strip() for cell in header_cells_sorted]

            # (C) Let GPT figure out which column is circuit #, breaker trip, etc.
            column_map = await self._ask_gpt_for_column_mapping(header_text_list)
            if not column_map:
                self.logger.warning("GPT returned empty column map. Skipping table.")
                continue

            # (D) Parse each subsequent row using the column map
            for row_idx in range(header_row_idx + 1, table.row_count):
                row_cells = [c for c in table.cells if c.row_index == row_idx]
                row_cells_sorted = sorted(row_cells, key=lambda x: x.column_index)
                circuit_obj = self._map_row_to_circuit(row_cells_sorted, column_map)
                if circuit_obj:
                    circuits.append(circuit_obj)

        return circuits

    def _guess_header_row(self, table) -> int:
        """
        Picks the row with the greatest total text length as the 'header row'.
        Returns the row index, or -1 if none found.
        """
        max_len = 0
        candidate = -1

        for row_idx in range(table.row_count):
            row_cells = [c for c in table.cells if c.row_index == row_idx]
            row_text = " ".join(cell.content.strip() for cell in row_cells)
            if len(row_text) > max_len:
                max_len = len(row_text)
                candidate = row_idx

        return candidate

    async def _ask_gpt_for_column_mapping(self, header_text_list: List[str]) -> Dict[int, str]:
        """
        Sends the header row’s column titles to GPT, asking for a JSON mapping:
          {
            "0": "ckt_number",
            "1": "breaker_trip",
            "2": "poles",
            "3": "load_description",
            ...
          }
        We convert that JSON into a Python dict {0: "ckt_number", ...}.
        """
        system_prompt = (
            "You are an expert at reading electrical panel schedule headers. "
            "Given a list of column names for an electrical panel schedule, return a JSON mapping of "
            "each column index (0-based) to a short semantic label. Example labels: "
            "['ckt_number', 'breaker_trip', 'poles', 'load_description', 'voltage', 'phase', 'unused']. "
            "If uncertain, label the column 'unused'. Return JSON only, with no extra text."
        )

        user_prompt = (
            f"Header columns:\n{json.dumps(header_text_list, indent=2)}\n\n"
            f"Return JSON in the format: {{\"0\":\"ckt_number\",\"1\":\"poles\",...}}"
        )

        try:
            # UPDATED: Use self.client instead of openai.ChatCompletion.acreate
            response = await self.client.chat.completions.create(
                model="gpt-4o-mini",  # keep your custom model
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                max_tokens=400,
                temperature=0.0
            )
            content = response.choices[0].message.content.strip()

            # Parse JSON into a Python dict
            mapping_raw = json.loads(content)
            column_map = {}
            for k, v in mapping_raw.items():
                col_idx = int(k)
                column_map[col_idx] = v
            return column_map

        except Exception as e:
            self.logger.error(f"GPT API call failed: {str(e)}")
            return {}

    def _map_row_to_circuit(self, row_cells_sorted: List, column_map: Dict[int, str]) -> Dict:
        """
        For a single row, we create a circuit dict by looking up each cell’s column index in 'column_map'.
        Returns None if the row is empty or if we can’t map anything meaningful.
        """
        circuit_obj = {}
        meaningful = False

        for i, cell in enumerate(row_cells_sorted):
            text_val = cell.content.strip()
            if i in column_map:
                field_name = column_map[i]
                # If GPT labeled it 'unused', skip
                if field_name not in ("unused", ""):
                    circuit_obj[field_name] = text_val
                    if text_val:
                        meaningful = True

        return circuit_obj if meaningful else None




================================================
File: templates/__init__.py
================================================
# Templates package initialization 

================================================
File: templates/a_rooms_template.json
================================================
{
    "room_id": "",
    "room_name": "",
    "walls": {
      "north": "",
      "south": "",
      "east": "",
      "west": ""
    },
    "ceiling_height": "",
    "dimensions": ""
  }
  

================================================
File: templates/e_rooms_template.json
================================================
{
    "room_id": "",
    "room_name": "",
    "circuits": {
      "lighting": [],
      "power": []
    },
    "light_fixtures": {
      "fixture_ids": [],
      "fixture_count": {}
    },
    "outlets": {
      "regular_outlets": 0,
      "controlled_outlets": 0
    },
    "data": 0,
    "floor_boxes": 0,
    "mechanical_equipment": [],
    "switches": {
      "type": "",
      "model": "",
      "dimming": ""
    }
  }
  

================================================
File: templates/room_templates.py
================================================
import json
import os

def load_template(template_name):
    current_dir = os.path.dirname(os.path.abspath(__file__))
    template_path = os.path.join(current_dir, f"{template_name}_template.json")
    try:
        with open(template_path, 'r') as file:
            return json.load(file)
    except FileNotFoundError:
        print(f"Template file not found: {template_path}")
        return {}
    except json.JSONDecodeError:
        print(f"Error decoding JSON from file: {template_path}")
        return {}

def generate_rooms_data(parsed_data, room_type):
    template = load_template(room_type)
    
    metadata = parsed_data.get('metadata', {})
    
    rooms_data = {
        "metadata": metadata,
        "project_name": metadata.get('project', ''),
        "floor_number": '',
        "rooms": []
    }
    
    parsed_rooms = parsed_data.get('rooms', [])
    
    if not parsed_rooms:
        print(f"No rooms found in parsed data for {room_type}.")
        return rooms_data

    for parsed_room in parsed_rooms:
        room_number = str(parsed_room.get('number', ''))
        room_name = parsed_room.get('name', '')
        
        if not room_number or not room_name:
            print(f"Skipping room with incomplete data: {parsed_room}")
            continue
        
        room_data = template.copy()
        room_data['room_id'] = f"Room_{room_number}"
        room_data['room_name'] = f"{room_name}_{room_number}"
        
        # Copy all fields from parsed_room to room_data
        for key, value in parsed_room.items():
            if key not in ['number', 'name']:
                room_data[key] = value
        
        rooms_data['rooms'].append(room_data)
    
    return rooms_data

def process_architectural_drawing(parsed_data, file_path, output_folder):
    """
    Process architectural drawing data (parsed JSON),
    and generate both e_rooms and a_rooms JSON outputs.
    """
    is_reflected_ceiling = "REFLECTED CEILING PLAN" in file_path.upper()
    
    floor_number = ''  # If floor number is available in the future, extract it here
    
    e_rooms_data = generate_rooms_data(parsed_data, 'e_rooms')
    a_rooms_data = generate_rooms_data(parsed_data, 'a_rooms')
    
    e_rooms_file = os.path.join(output_folder, f'e_rooms_details_floor_{floor_number}.json')
    a_rooms_file = os.path.join(output_folder, f'a_rooms_details_floor_{floor_number}.json')
    
    with open(e_rooms_file, 'w') as f:
        json.dump(e_rooms_data, f, indent=2)
    with open(a_rooms_file, 'w') as f:
        json.dump(a_rooms_data, f, indent=2)
    
    return {
        "e_rooms_file": e_rooms_file,
        "a_rooms_file": a_rooms_file,
        "is_reflected_ceiling": is_reflected_ceiling
    }

if __name__ == "__main__":
    # Optional test block; can be removed or kept for debugging
    test_file_path = "path/to/your/test/file.json"
    test_output_folder = "path/to/your/test/output/folder"
    
    with open(test_file_path, 'r') as f:
        test_parsed_data = json.load(f)
    
    result = process_architectural_drawing(test_parsed_data, test_file_path, test_output_folder)
    print(result)


================================================
File: utils/__init__.py
================================================
# Utilities package initialization 

================================================
File: utils/api_utils.py
================================================
import asyncio
import logging
import random

MAX_RETRIES = 3
RETRY_DELAY = 5  # seconds

async def async_safe_api_call(client, *args, **kwargs):
    """
    Safely call the OpenAI API with retries and backoff.
    """
    retries = 0
    delay = 1  # initial backoff

    while retries < MAX_RETRIES:
        try:
            return await client.chat.completions.create(*args, **kwargs)
        except Exception as e:
            if "rate limit" in str(e).lower():
                logging.warning(f"Rate limit hit, retrying in {delay} seconds...")
                retries += 1
                delay = min(delay * 2, 60)  # cap backoff at 60s
                await asyncio.sleep(delay + random.uniform(0, 1))  # add jitter
            else:
                logging.error(f"API call failed: {e}")
                await asyncio.sleep(RETRY_DELAY)
                retries += 1

    logging.error("Max retries reached for API call")
    raise Exception("Failed to make API call after maximum retries")


================================================
File: utils/constants.py
================================================
import os

DRAWING_TYPES = {
    'Architectural': ['A', 'AD'],
    'Electrical': ['E', 'ED'],
    'Mechanical': ['M', 'MD'],
    'Plumbing': ['P', 'PD'],
    'Site': ['S', 'SD'],
    'Civil': ['C', 'CD'],
    'Low Voltage': ['LV', 'LD'],
    'Fire Alarm': ['FA', 'FD'],
    'Kitchen': ['K', 'KD']
}

def get_drawing_type(filename: str) -> str:
    """
    Detect the drawing type by examining the first 1-2 letters of the filename.
    """
    prefix = os.path.basename(filename).split('.')[0][:2].upper()
    for dtype, prefixes in DRAWING_TYPES.items():
        if any(prefix.startswith(p.upper()) for p in prefixes):
            return dtype
    return 'General'


================================================
File: utils/drawing_processor.py
================================================
from openai import AsyncOpenAI

DRAWING_INSTRUCTIONS = {
    "Electrical": "Focus on panel schedules, circuit info, equipment schedules with electrical characteristics, and installation notes.",
    "Mechanical": "Capture equipment schedules, HVAC details (CFM, capacities), and installation instructions.",
    "Plumbing": "Include fixture schedules, pump details, water heater specs, pipe sizing, and system instructions.",
    "Architectural": """
    Extract and structure the following information:
    1. Room details: Create a 'rooms' array with objects for each room, including:
       - 'number': Room number (as a string)
       - 'name': Room name
       - 'finish': Ceiling finish
       - 'height': Ceiling height
    2. Room finish schedules
    3. Door/window details
    4. Wall types
    5. Architectural notes
    Ensure all rooms are captured and properly structured in the JSON output.
    """,
    "General": "Organize all relevant data into logical categories based on content type."
}

async def process_drawing(raw_content: str, drawing_type: str, client: AsyncOpenAI):
    """
    Use GPT to parse PDF text + table data into structured JSON
    based on the drawing type.
    """
    system_message = f"""
    Parse this {drawing_type} drawing/schedule into a structured JSON format. Guidelines:
    1. For text: Extract key information, categorize elements.
    2. For tables: Preserve structure, use nested arrays/objects.
    3. Create a hierarchical structure, use consistent key names.
    4. Include metadata (drawing number, scale, date) if available.
    5. {DRAWING_INSTRUCTIONS.get(drawing_type, DRAWING_INSTRUCTIONS["General"])}
    6. For all drawing types, if room information is present, always include a 'rooms' array in the JSON output, 
       with each room having at least 'number' and 'name' fields.
    Ensure the entire response is a valid JSON object.
    """
    
    try:
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_message},
                {"role": "user", "content": raw_content}
            ],
            temperature=0.2,
            max_tokens=16000,
            response_format={"type": "json_object"}
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"Error processing {drawing_type} drawing: {str(e)}")
        raise


================================================
File: utils/drawing_utils.py
================================================
"""
Additional drawing-related helper functions.
""" 

================================================
File: utils/file_utils.py
================================================
import os
import logging
from typing import List

logger = logging.getLogger(__name__)

def traverse_job_folder(job_folder: str) -> List[str]:
    """
    Traverse the job folder and collect all PDF files.
    """
    pdf_files = []
    try:
        for root, _, files in os.walk(job_folder):
            for file in files:
                if file.lower().endswith('.pdf'):
                    pdf_files.append(os.path.join(root, file))
        logger.info(f"Found {len(pdf_files)} PDF files in {job_folder}")
    except Exception as e:
        logger.error(f"Error traversing job folder {job_folder}: {str(e)}")
    return pdf_files

def cleanup_temporary_files(output_folder: str) -> None:
    """
    Clean up any temporary files created during processing (not currently used).
    """
    pass

def get_project_name(job_folder: str) -> str:
    """
    Extract the project name from the job folder path.
    """
    return os.path.basename(job_folder)


================================================
File: utils/logging_utils.py
================================================
import os
import logging
from datetime import datetime

def setup_logging(output_folder: str) -> None:
    """
    Configure and initialize logging for the application.
    Creates a 'logs' folder in the output directory.
    """
    log_folder = os.path.join(output_folder, 'logs')
    os.makedirs(log_folder, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = os.path.join(log_folder, f"process_log_{timestamp}.txt")
    
    logging.basicConfig(
        filename=log_file,
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    print(f"Logging to: {log_file}")


================================================
File: utils/pdf_processor.py
================================================
import pymupdf
import json
import os
from openai import AsyncOpenAI

async def extract_text_and_tables_from_pdf(pdf_path: str) -> str:
    doc = pymupdf.open(pdf_path)
    all_content = ""
    for page in doc:
        text = page.get_text()
        all_content += "TEXT:\n" + text + "\n"
        
        tables = page.find_tables()
        for table in tables:
            all_content += "TABLE:\n"
            markdown = table.to_markdown()
            all_content += markdown + "\n"
    
    return all_content

async def structure_panel_data(client: AsyncOpenAI, raw_content: str) -> dict:
    prompt = f"""
    You are an expert in electrical engineering and panel schedules. 
    Please structure the following content from an electrical panel schedule into a valid JSON format. 
    The content includes both text and tables. Extract key information such as panel name, voltage, amperage, circuits, 
    and any other relevant details.
    Pay special attention to the tabular data, which represents circuit information.
    Ensure your entire response is a valid JSON object.
    Raw content:
    {raw_content}
    """
    response = await client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are a helpful assistant that structures electrical panel data into JSON."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.2,
        max_tokens=2000,
        response_format={"type": "json_object"}
    )
    return json.loads(response.choices[0].message.content)

async def process_pdf(pdf_path: str, output_folder: str, client: AsyncOpenAI):
    print(f"Processing PDF: {pdf_path}")
    raw_content = await extract_text_and_tables_from_pdf(pdf_path)
    
    structured_data = await structure_panel_data(client, raw_content)
    
    panel_name = structured_data.get('panel_name', 'unknown_panel').replace(" ", "_").lower()
    filename = f"{panel_name}_electric_panel.json"
    filepath = os.path.join(output_folder, filename)
    
    with open(filepath, 'w') as f:
        json.dump(structured_data, f, indent=2)
    
    print(f"Saved structured panel data: {filepath}")
    return raw_content, structured_data


================================================
File: utils/pdf_utils.py
================================================
import pdfplumber
import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

def extract_text(file_path: str) -> str:
    """
    Extract text from a PDF file using pdfplumber.
    """
    logger.info(f"Starting text extraction for {file_path}")
    try:
        with pdfplumber.open(file_path) as pdf:
            logger.info(f"Successfully opened {file_path}")
            text = ""
            for i, page in enumerate(pdf.pages):
                logger.info(f"Processing page {i+1} of {len(pdf.pages)}")
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
                else:
                    logger.warning(f"No text extracted from page {i+1}")
        
        if not text:
            logger.warning(f"No text extracted from {file_path}")
        else:
            logger.info(f"Successfully extracted text from {file_path}")
        
        return text
    except Exception as e:
        logger.error(f"Error extracting text from {file_path}: {str(e)}")
        raise

def extract_images(file_path: str) -> List[Dict[str, Any]]:
    """
    Extract images from a PDF file using pdfplumber.
    """
    try:
        images = []
        with pdfplumber.open(file_path) as pdf:
            for i, page in enumerate(pdf.pages):
                for image in page.images:
                    images.append({
                        'page': i + 1,
                        'bbox': image['bbox'],
                        'width': image['width'],
                        'height': image['height'],
                        'type': image['type']
                    })
        
        logger.info(f"Extracted {len(images)} images from {file_path}")
        return images
    except Exception as e:
        logger.error(f"Error extracting images from {file_path}: {str(e)}")
        raise

def get_pdf_metadata(file_path: str) -> Dict[str, Any]:
    """
    Get metadata from a PDF file using pdfplumber.
    """
    try:
        with pdfplumber.open(file_path) as pdf:
            metadata = pdf.metadata
        logger.info(f"Successfully extracted metadata from {file_path}")
        return metadata
    except Exception as e:
        logger.error(f"Error extracting metadata from {file_path}: {str(e)}")
        raise


