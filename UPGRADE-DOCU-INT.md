1. Install and Configure Azure Document Intelligence

A) Add to Your Requirements
In your requirements.txt file, add:

azure-ai-documentintelligence==1.0.0
azure-core>=1.44.1

Then run:

pip install -r requirements.txt

B) Set Environment Variables
Because Azure Document Intelligence requires an endpoint and a key, you should store these in your .env file (similar to how you store your OPENAI_API_KEY). For example:

DOCUMENTINTELLIGENCE_ENDPOINT=https://<your-resource-name>.cognitiveservices.azure.com/
DOCUMENTINTELLIGENCE_API_KEY=<your-azure-document-intelligence-key>
Important: Never commit your real .env to source control. Use .env.example to show placeholders instead.
2. Create a New File: panel_schedule_intelligence.py

In your project root (or inside utils/ or processing/—your choice), create a new file named panel_schedule_intelligence.py. This code:

Initializes an Azure Document Intelligence client
Provides an async function to process just electrical panel schedule PDFs
Extracts relevant table and text data
Example Content (feel free to adapt folder references as needed):

# File: panel_schedule_intelligence.py
from azure.core.credentials import AzureKeyCredential
from azure.ai.documentintelligence import DocumentIntelligenceClient
import logging
import os
import json
import asyncio
from typing import Dict, List

class PanelScheduleProcessor:
    """
    Azure Document Intelligence processor specifically for electrical panel schedules.
    Designed to be integrated into your larger document processing pipeline.
    """
    
    def __init__(self, endpoint: str, api_key: str, **kwargs):
        """
        Initialize the processor with Azure credentials.
        
        Args:
            endpoint (str): Azure Document Intelligence endpoint
            api_key (str): Azure Document Intelligence key
            **kwargs: Additional configuration options (e.g., batch_size, timeout, etc.)
        """
        self.client = DocumentIntelligenceClient(
            endpoint=endpoint,
            credential=AzureKeyCredential(api_key)
        )
        self.logger = logging.getLogger(__name__)
        self.batch_size = kwargs.get('batch_size', 1)
        self.timeout = kwargs.get('timeout', 300)

    async def process_panel_schedule(self, file_path: str) -> Dict:
        """
        Process a single panel schedule PDF using Azure Document Intelligence
        and return structured information as a Python dict.
        """
        try:
            # Read PDF bytes
            with open(file_path, "rb") as f:
                document_bytes = f.read()

            # Call Azure prebuilt-layout model
            poller = self.client.begin_analyze_document(
                "prebuilt-layout",
                document_bytes,
                content_type="application/pdf"
            )
            result = poller.result()

            # Extract structured data from the result
            panel_data = self._extract_panel_data(result)
            circuit_data = self._extract_circuit_data(result)
            specs = self._extract_specifications(result)
            revisions = self._extract_revisions(result)

            # Return a dict that you can later serialize to JSON
            return {
                "panel": {
                    **panel_data,
                    "specifications": specs,
                    "circuits": circuit_data,
                    "revisions": revisions
                }
            }

        except Exception as e:
            self.logger.error(f"Error processing panel schedule {file_path}: {str(e)}")
            raise

    def _extract_panel_data(self, result) -> Dict:
        """
        Extract basic panel metadata. You can adjust logic to parse text content or table cells.
        """
        return {
            "name": "",
            "voltage": "",
            "phases": None,
            "rating": "",
            "main_type": ""
        }

    def _extract_circuit_data(self, result) -> List[Dict]:
        """
        Extract circuit table information (one row per circuit, etc.).
        """
        circuits = []
        # Custom logic to parse the result tables
        return circuits

    def _extract_specifications(self, result) -> Dict:
        """
        Example specs that might appear in the panel schedule.
        """
        return {
            "sections": "",
            "nema_enclosure": "",
            "amps": "",
            "phases": "",
            "voltage": "",
            "frequency": "",
            "dimensions": {
                "height": "",
                "width": "",
                "depth": ""
            }
        }

    def _extract_revisions(self, result) -> List[Dict]:
        """
        If your panel schedule has a revision block or notes.
        """
        return []

    async def batch_process(self, file_paths: List[str]) -> Dict[str, Dict]:
        """
        Optionally, you can process multiple panel schedule PDFs in a batch.
        This is just an example if you want to pass in many PDFs at once.
        """
        results = {}
        # A small helper to process in chunks
        for idx, file_path in enumerate(file_paths):
            try:
                data = await self.process_panel_schedule(file_path)
                results[file_path] = data
            except Exception as e:
                results[file_path] = {"error": str(e)}
        return results
Key Points

Model: Using "prebuilt-layout" suits panel schedules because it preserves table structures.
Async: The process_panel_schedule method is asynchronous (though the internal begin_analyze_document call is not strictly async in older versions—but the pattern remains the same).
Result: You get a Python dict with structured data about the panel.
3. Use Your Panel Schedule Processor in file_processor.py

Your existing file_processor.py runs an async function called process_pdf_async for every PDF. We only want to use Azure Document Intelligence if:

The drawing_type is "Electrical", and
The PDF actually appears to be a panel schedule (for example, the filename includes "Panel" or the first page’s text includes some keywords).
Below is an example change inside process_pdf_async showing how you might detect a panel schedule and hand it off to the new PanelScheduleProcessor.

You can tweak detection logic any way you like (e.g., scanning the PDF text for "Panel Schedule").
# File: processing/file_processor.py

import os
import json
import logging
from tqdm.asyncio import tqdm

from utils.pdf_processor import extract_text_and_tables_from_pdf
from utils.drawing_processor import process_drawing
from templates.room_templates import process_architectural_drawing

# 1) Import our new panel schedule intelligence
from panel_schedule_intelligence import PanelScheduleProcessor

# Load Azure env vars (optionally do this in your settings.py or however you prefer)
import dotenv
dotenv.load_dotenv()
AZURE_ENDPOINT = os.getenv("DOCUMENTINTELLIGENCE_ENDPOINT")
AZURE_API_KEY = os.getenv("DOCUMENTINTELLIGENCE_API_KEY")

# Create a single instance of the panel schedule processor (optional to reuse)
panel_processor = None
if AZURE_ENDPOINT and AZURE_API_KEY:
    panel_processor = PanelScheduleProcessor(endpoint=AZURE_ENDPOINT, api_key=AZURE_API_KEY)

async def process_pdf_async(
    pdf_path,
    client,
    output_folder,
    drawing_type,
    templates_created
):
    """
    Process a single PDF asynchronously:
      1) Detect if it's an Electrical Panel Schedule. If so, run Azure Doc Intelligence approach.
      2) Otherwise, do normal GPT-based approach.
    """
    file_name = os.path.basename(pdf_path)
    with tqdm(total=100, desc=f"Processing {file_name}", leave=False) as pbar:
        try:
            pbar.update(10)  # Start
            raw_content = await extract_text_and_tables_from_pdf(pdf_path)
            pbar.update(20)  # PDF text/tables extracted

            # ---------------------------------------------------------
            # DETECTION LOGIC:
            # If "Electrical" and file name or content mention "panel"
            # Feel free to refine or add a better check:
            # ---------------------------------------------------------
            is_panel_schedule = False
            if drawing_type == "Electrical":
                lower_fname = file_name.lower()
                if "panel" in lower_fname or "panel schedule" in raw_content.lower():
                    is_panel_schedule = True

            if is_panel_schedule and panel_processor:
                # Use Azure Document Intelligence for panel schedules
                logging.info(f"Detected Electrical Panel Schedule in {file_name}. Using Azure Document Intelligence.")
                
                panel_data = await panel_processor.process_panel_schedule(pdf_path)
                pbar.update(40)

                # Write result to JSON
                type_folder = os.path.join(output_folder, "PanelSchedules")
                os.makedirs(type_folder, exist_ok=True)
                output_filename = os.path.splitext(file_name)[0] + '_panel.json'
                output_path = os.path.join(type_folder, output_filename)
                
                with open(output_path, 'w') as f:
                    json.dump(panel_data, f, indent=2)

                pbar.update(20)
                logging.info(f"Successfully processed panel schedule: {output_path}")

                # We'll skip the normal GPT approach since we already got structured data
                pbar.update(10)  # Finish
                return {"success": True, "file": output_path, "panel_schedule": True}

            else:
                # ---------------------------------------------------------
                # Normal GPT approach
                # ---------------------------------------------------------
                structured_json = await process_drawing(raw_content, drawing_type, client)
                pbar.update(40)  # GPT processing

                type_folder = os.path.join(output_folder, drawing_type)
                os.makedirs(type_folder, exist_ok=True)
                output_filename = os.path.splitext(file_name)[0] + '_structured.json'
                output_path = os.path.join(type_folder, output_filename)

                # Attempt to parse JSON response
                try:
                    parsed_json = json.loads(structured_json)
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
                    logging.info(f"Raw GPT response: {structured_json}")

                    raw_output_filename = os.path.splitext(file_name)[0] + '_raw_response.json'
                    raw_output_path = os.path.join(type_folder, raw_output_filename)

                    with open(raw_output_path, 'w') as f:
                        f.write(structured_json)
                    
                    logging.warning(f"Saved raw response to {raw_output_path}")
                    return {"success": False, "error": "Failed to parse JSON", "file": pdf_path}

        except Exception as e:
            pbar.update(100)
            logging.error(f"Error processing {pdf_path}: {str(e)}")
            return {"success": False, "error": str(e), "file": pdf_path}
How This Works
Extract Raw PDF Content
We use your existing extract_text_and_tables_from_pdf function to grab text and tables.
Check for Electrical + “Panel”
If drawing_type == "Electrical", we do a lightweight check to see if the PDF is likely a panel schedule (e.g., file name contains "panel" or the raw text has "panel schedule").
You can expand this logic to be more precise if desired.
Azure Document Intelligence
If your detection is positive, you call panel_processor.process_panel_schedule(pdf_path).
The returned dictionary is saved as a JSON file in a PanelSchedules/ folder (instead of the normal Electrical/).
You skip the GPT approach, because you’ve already extracted structured data from Azure’s Document Intelligence.
Default GPT Flow
If it’s not an electrical panel schedule, you do your normal GPT approach as before.
4. Validate Everything

Environment: Ensure you have DOCUMENTINTELLIGENCE_ENDPOINT and DOCUMENTINTELLIGENCE_API_KEY set in your .env.
Imports: Check that your azure-ai-documentintelligence library is installed and your panel_schedule_intelligence.py is in a location recognized by your Python imports.
Run:
python main.py <input_folder> [output_folder]
Your logs should indicate when it “Detected Electrical Panel Schedule” and used Azure. Otherwise, it’ll fall back to the normal GPT pipeline.
5. Final Tips

Logging: If you want more detailed logs from Azure Document Intelligence, configure Python logging to debug level.
Error Handling: The example code has a try/except block in process_panel_schedule(). Ensure you capture these logs in your main pipeline.
Refining the Parser: The _extract_* methods in PanelScheduleProcessor can be tailored to your own needs. For instance, you can scan the recognized tables to find circuit numbers, breaker sizes, or any other headings you expect in a panel schedule.
Async vs. Sync: The official Azure Document Intelligence client might have slight differences between synchronous and asynchronous usage. The snippet above uses the general “begin_analyze_document” approach with a poller, which is typically synchronous. This is fine to wrap in async, but if you have trouble, just remember that the overall pipeline can still handle it in a background thread.