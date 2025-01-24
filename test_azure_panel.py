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
    """
    Simple console-based logging setup (no log file).
    """
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )

async def main():
    """
    Test script to isolate Azure Document Intelligence for panel schedules.
    Usage:
      1) python test_azure_panel.py /path/to/panel.pdf
      2) python test_azure_panel.py /path/to/folder/with/pdfs/
    """
    if len(sys.argv) < 2:
        print("Usage: python test_azure_panel.py <pdf_file_or_folder>")
        sys.exit(1)

    path_arg = sys.argv[1]
    if not os.path.exists(path_arg):
        print(f"Error: Path '{path_arg}' does not exist.")
        sys.exit(1)

    # 1) Load .env to get your Azure credentials
    load_dotenv()
    endpoint = os.getenv("DOCUMENTINTELLIGENCE_ENDPOINT")
    api_key = os.getenv("DOCUMENTINTELLIGENCE_API_KEY")

    if not endpoint or not api_key:
        logging.error("Azure Document Intelligence credentials not found in environment. Exiting.")
        sys.exit(1)

    # 2) Initialize the Azure Document Intelligence panel schedule processor
    panel_processor = PanelScheduleProcessor(endpoint=endpoint, api_key=api_key)

    # Collect all PDF files to examine
    pdf_files = []
    if os.path.isfile(path_arg):
        # Single PDF
        if path_arg.lower().endswith(".pdf"):
            pdf_files.append(path_arg)
        else:
            logging.error(f"File '{path_arg}' is not a PDF.")
            sys.exit(1)
    else:
        # It's a directory -> gather PDF files
        for root, _, files in os.walk(path_arg):
            for file in files:
                if file.lower().endswith(".pdf"):
                    pdf_files.append(os.path.join(root, file))

    if not pdf_files:
        logging.warning(f"No PDF files found at '{path_arg}'")
        sys.exit(0)

    # 3) For each PDF, check if it appears to be a panel schedule, then process
    output_folder = os.path.join(os.getcwd(), "test_output")
    os.makedirs(output_folder, exist_ok=True)

    for pdf_path in pdf_files:
        file_name = os.path.basename(pdf_path)
        # Use your existing name-based detection
        if is_panel_schedule(file_name, ""):
            logging.info(f"Detected panel schedule in '{file_name}'. Processing with Azure Document Intelligence...")

            try:
                # Optional text extraction, just for debug info
                raw_content = await extract_text_and_tables_from_pdf(pdf_path)
                logging.info(f"Extracted PDF content length: {len(raw_content)} characters")

                # Process with Azure
                panel_data = await panel_processor.process_panel_schedule(pdf_path)
                logging.info(f"Successfully processed '{file_name}' via Azure Document Intelligence.")

                # Save output
                base_name = os.path.splitext(file_name)[0]
                output_file = os.path.join(output_folder, f"{base_name}_test_panel.json")
                with open(output_file, "w") as f:
                    json.dump(panel_data, f, indent=2)

                logging.info(f"Saved panel schedule result to: '{output_file}'")

            except Exception as e:
                logging.exception(f"Error processing panel schedule '{file_name}': {str(e)}")

        else:
            logging.info(f"'{file_name}' does NOT appear to be a panel schedule. Skipping.")

if __name__ == "__main__":
    setup_logging()
    asyncio.run(main())
