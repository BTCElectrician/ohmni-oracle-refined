import os
import json
import logging
from tqdm.asyncio import tqdm

from utils.pdf_processor import extract_text_and_tables_from_pdf
from utils.drawing_processor import process_drawing
from templates.room_templates import process_architectural_drawing

async def process_pdf_async(
    pdf_path,
    client,
    output_folder,
    drawing_type,
    templates_created
):
    """
    Process a single PDF asynchronously:
      1) Extract text/tables.
      2) Use GPT to convert data into structured JSON.
      3) Save results to disk, possibly generate templates for Architectural PDFs.
    """
    file_name = os.path.basename(pdf_path)
    with tqdm(total=100, desc=f"Processing {file_name}", leave=False) as pbar:
        try:
            pbar.update(10)  # Start
            raw_content = await extract_text_and_tables_from_pdf(pdf_path)
            
            pbar.update(20)  # PDF text/tables extracted
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
                return {"success": True, "file": output_path}
            
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
