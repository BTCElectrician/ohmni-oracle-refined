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
