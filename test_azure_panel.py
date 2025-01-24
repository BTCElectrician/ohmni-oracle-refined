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
