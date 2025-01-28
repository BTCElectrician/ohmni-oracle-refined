import logging
import os
import json
from typing import Dict

from azure.core.credentials import AzureKeyCredential
from azure.ai.documentintelligence import DocumentIntelligenceClient
# from azure.ai.documentintelligence.models import DocumentAnalysisFeature  # No longer needed

class PanelScheduleProcessor:
    """
    Processes an electrical panel schedule using Azure Document Intelligence (GA 1.0.0).
    It automatically extracts tables when using the 'prebuilt-layout' model.
    """

    def __init__(self, endpoint: str, api_key: str, **kwargs):
        self.client = DocumentIntelligenceClient(
            endpoint=endpoint,
            credential=AzureKeyCredential(api_key)
        )
        self.logger = logging.getLogger(__name__)

    def process_panel_schedule(self, file_path: str) -> Dict:
        """
        1) Opens the PDF file
        2) Analyzes with the 'prebuilt-layout' model
           (no 'features' parameter needed in GA 1.0.0)
        3) Pulls out table data (and styles if available)
        4) Returns a JSON-like dictionary
        """

        # Basic output structure, including an error field for fallback
        fallback_output = {
            "file_name": os.path.basename(file_path),
            "extracted_tables": [],
            "extracted_styles": [],
            "error": None
        }
        try:
            self.logger.info(f"Processing panel schedule: {file_path}")

            # 1) Read PDF bytes
            with open(file_path, "rb") as f:
                pdf_bytes = f.read()

            # 2) Analyze using "prebuilt-layout" 
            #    (In v1.0.0, the argument is `document=pdf_bytes` rather than `analyze_request=...`)
            poller = self.client.begin_analyze_document(
                model_id="prebuilt-layout",
                document=pdf_bytes,
                content_type="application/octet-stream"
            )
            result = poller.result()

            # 3A) Pull out table data
            tables_data = []
            if hasattr(result, "tables") and result.tables:  # be safe checking
                self.logger.info(f"Found {len(result.tables)} table(s) in document.")
                for table_idx, table in enumerate(result.tables):
                    # Log a quick summary
                    self.logger.debug(
                        f"Table {table_idx}: {table.row_count} rows x {table.column_count} columns"
                    )

                    table_rows = []
                    for cell in table.cells:
                        # Make sure the list is big enough
                        while len(table_rows) <= cell.row_index:
                            table_rows.append([])

                        table_rows[cell.row_index].append(cell.content)

                    # Optional: Log the first row snippet
                    if table_rows and len(table_rows[0]) > 0:
                        snippet = " | ".join(table_rows[0])
                        self.logger.debug(
                            f"Table {table_idx} first row snippet: {snippet[:100]}"
                        )

                    tables_data.append({
                        "table_index": table_idx,
                        "row_count": table.row_count,
                        "column_count": table.column_count,
                        "rows": table_rows
                    })

            # 3B) Pull out style data (if it exists in v1.0.0)
            styles_data = []
            if hasattr(result, "styles") and result.styles:
                for style_idx, style in enumerate(result.styles):
                    # We'll just store a small subset for demonstration
                    styles_data.append({
                        "style_index": style_idx,
                        "is_bold": style.is_bold,
                        "is_italic": style.is_italic,
                        "color": style.color,
                        "font_size": style.font_size
                    })

            # Build final JSON-like output
            final_result = {
                "file_name": os.path.basename(file_path),
                "extracted_tables": tables_data,
                "extracted_styles": styles_data
            }
            return final_result

        except Exception as e:
            self.logger.exception(f"Failed to process panel schedule: {e}")
            fallback_output["error"] = str(e)
            return fallback_output
