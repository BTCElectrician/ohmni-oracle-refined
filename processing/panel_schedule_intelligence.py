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
