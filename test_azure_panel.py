import os
import sys
import json
import logging
import asyncio

from dotenv import load_dotenv
from processing.panel_schedule_intelligence import PanelScheduleProcessor
from processing.file_processor import is_panel_schedule

def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )

async def main():
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

    pdf_files = []
    if os.path.isfile(path_arg) and path_arg.lower().endswith(".pdf"):
        pdf_files.append(path_arg)
    elif os.path.isdir(path_arg):
        for root, _, files in os.walk(path_arg):
            for f in files:
                if f.lower().endswith(".pdf"):
                    pdf_files.append(os.path.join(root, f))

    output_folder = os.path.join(os.getcwd(), "test_output")
    os.makedirs(output_folder, exist_ok=True)

    for pdf_path in pdf_files:
        file_name = os.path.basename(pdf_path)
        if is_panel_schedule(file_name, ""):
            logging.info(f"Detected panel schedule in '{file_name}'...")
            try:
                # Now calls the panel processor's method WITHOUT GPT
                result_data = panel_processor.process_panel_schedule(pdf_path)
                logging.info(f"Successfully processed '{file_name}'.")
            except Exception as e:
                logging.exception(f"Error: {e}")
                result_data = {"extracted_chunks": [], "error": str(e)}

            out_file = os.path.join(
                output_folder,
                f"{os.path.splitext(file_name)[0]}_test_panel.json"
            )
            with open(out_file, "w") as f:
                json.dump(result_data, f, indent=2)
            logging.info(f"Wrote output to '{out_file}'")
        else:
            logging.info(f"'{file_name}' does NOT appear to be a panel schedule.")


if __name__ == "__main__":
    setup_logging()
    asyncio.run(main())
