# File: processing/panel_schedule_intelligence.py

import logging
import os
import json
from typing import Dict

from azure.core.credentials import AzureKeyCredential
from azure.ai.documentintelligence import DocumentIntelligenceClient
from azure.ai.documentintelligence.models import DocumentAnalysisFeature

class PanelScheduleProcessor:
    """
    Processes an electrical panel schedule using Azure Document Intelligence (GA 1.0.0).
    It automatically extracts tables and other layout info using the 'prebuilt-document' model.
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
        2) Analyzes with the 'prebuilt-document' model
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

            # 2) Analyze using "prebuilt-document" (GA 1.0 syntax)
            #    Pass your PDF bytes as 'body', set content_type to 'application/pdf'.
            poller = self.client.begin_analyze_document(
                model_id="prebuilt-document",
                body=pdf_bytes,
                content_type="application/pdf",
                # Optionally, choose which features to enable:
                features=[
                    DocumentAnalysisFeature.TABLES,
                    DocumentAnalysisFeature.KEY_VALUE_PAIRS,
                    DocumentAnalysisFeature.FIGURES
                ],
                # You can also limit pages or set locale if needed, for example:
                # pages="1-",
                # locale="en-US"
            )

            result = poller.result()

            # 3A) Pull out table data
            tables_data = []
            if hasattr(result, "tables") and result.tables:
                self.logger.info(f"Found {len(result.tables)} table(s) in document.")
                for table_idx, table in enumerate(result.tables):
                    # Log a quick summary
                    self.logger.debug(
                        f"Table {table_idx}: {table.row_count} rows x {table.column_count} columns"
                    )

                    # Build a 2D list (rows, columns)
                    table_rows = []
                    for cell in table.cells:
                        # Make sure the list is big enough for this row
                        while len(table_rows) <= cell.row_index:
                            table_rows.append([])

                        row = table_rows[cell.row_index]
                        # Pad columns if needed
                        while len(row) < cell.column_index:
                            row.append("")
                        # Insert or overwrite the cell content
                        row.insert(cell.column_index, cell.content)

                    tables_data.append({
                        "table_index": table_idx,
                        "row_count": table.row_count,
                        "column_count": table.column_count,
                        "rows": table_rows
                    })

            # 3B) Pull out style data (if available)
            styles_data = []
            if hasattr(result, "styles") and result.styles:
                for style_idx, style in enumerate(result.styles):
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
