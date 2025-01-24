from azure.core.credentials import AzureKeyCredential
from azure.ai.documentintelligence import DocumentIntelligenceClient
import logging
import os
import json
import asyncio
from typing import Dict, List
import re

PANEL_NAME_PATTERN = re.compile(r'^[A-Z]{1,3}\d{1,3}$')

class PanelScheduleProcessor:
    """
    Azure Document Intelligence processor specifically for electrical panel schedules.
    Uses the "prebuilt-layout" model to retrieve pages, tables, etc.
    """

    def __init__(self, endpoint: str, api_key: str, **kwargs):
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
        and return structured information as a Python dict (even if partially empty).
        """
        # A fallback in case we encounter an error
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
            # 1) Read PDF
            with open(file_path, "rb") as f:
                document_bytes = f.read()

            # 2) Call Azure prebuilt-layout model
            poller = self.client.begin_analyze_document(
                "prebuilt-layout",
                document_bytes,
                content_type="application/pdf"
            )
            result = poller.result()
            self.logger.info(f"DEBUG: Azure analysis complete for {file_path}")

            # 3) Extract data from 'result'
            extracted_data = self._extract_panel_data(result)
            circuit_info = self._extract_circuit_data(result)

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
            # If anything fails, we still return a partial JSON with an error message
            self.logger.exception(f"Azure Document Intelligence processing failed for {file_path}")
            fallback_output["error"] = str(e)
            return fallback_output

    def _extract_panel_data(self, result) -> Dict:
        """
        Extract panel data from the 'prebuilt-layout' result.
        We focus on 'tables' because 'documents' is often None for layout models.
        """
        self.logger.info("DEBUG: Entering _extract_panel_data method")

        # If the layout engine recognized any 'documents'
        if getattr(result, "documents", None) is not None:
            self.logger.info(f"DEBUG: Found {len(result.documents)} document(s)")
        else:
            self.logger.info("DEBUG: No 'documents' found in the result. (Normal for prebuilt-layout)")

        # Build default structure
        parsed_data = {
            "PanelName": "",
            "LoadCenter": {
                "panelboard_schedule": {
                    "designation": "",
                    "main_type": "",
                    "mounting": "",
                    "branch_ocp_type": "",
                    "voltage": "",
                    "circuits": {
                        "circuit_no": "",
                        "description": "",
                        "ocp": "",
                        "room_id": []
                    }
                }
            },
            "MainPanel": {
                "panel": {
                    "name": "",
                    "voltage": "",
                    "feed": "",
                    "marks": None,
                    "specifications": {
                        "sections": "",
                        "nema_enclosure": "",
                        "amps": "",
                        "phases": "",
                        "voltage": "",
                        "frequency": "",
                        "interrupt_rating": "",
                        "incoming_feed": "",
                        "mounting": "",
                        "circuits_count": 0,
                        "dimensions": {
                            "height": "",
                            "width": "",
                            "depth": ""
                        },
                        "main_breaker_rating": None,
                        "main_lugs_rating": None
                    },
                    "circuits": {
                        "circuit": "",
                        "circuit_range": None,
                        "load_name": "",
                        "trip": "",
                        "poles": None,
                        "equipment_ref": None,
                        "equipment_refs": []
                    },
                    "panel_totals": {
                        "total_connected_load": None,
                        "total_estimated_demand": None,
                        "total_connected_amps": None,
                        "total_estimated_demand_amps": None
                    }
                }
            },
            "DistributionPanel": {
                "marks": {
                    "section": "",
                    "amps": "",
                    "interrupt_rating": "",
                    "feed": "",
                    "circuits": "",
                    "certifications": [],
                    "dimensions": {
                        "height": "",
                        "width": "",
                        "depth": ""
                    },
                    "breaker": ""
                },
                "panel": {
                    "name": "",
                    "voltage": "",
                    "feed": "",
                    "location": None,
                    "phases": None,
                    "aic_rating": None,
                    "type": None,
                    "rating": None,
                    "circuits": {
                        "circuit": "",
                        "load_name": "",
                        "trip": "",
                        "poles": "",
                        "equipment_ref": None
                    }
                }
            }
        }

        # 1) If no tables found, we can't do much
        if not hasattr(result, "tables") or not result.tables:
            self.logger.warning("No tables found in layout result.")
            return parsed_data

        # 2) Parse each table cell
        for table in result.tables:
            # table.cells is a flat list of DocumentTableCell objects
            for cell in table.cells:
                text_lower = cell.content.lower().strip()

                # Regex check for panel name
                if PANEL_NAME_PATTERN.match(cell.content.strip()):
                    parsed_data["PanelName"] = cell.content.strip()
                    self.logger.info(f"Regex match: Found panel name '{cell.content.strip()}'")

                # For main panel, distribution panel, load center logic
                self._process_table_cell(parsed_data, text_lower, table, cell)

        return parsed_data

    def _extract_circuit_data(self, result) -> List[Dict]:
        """
        Extract circuit rows from the recognized tables (if any).
        We'll guess which table is a "circuit table" using keywords in row 0.
        """
        self.logger.info("DEBUG: Entering _extract_circuit_data method")
        circuits = []

        if not hasattr(result, "tables") or not result.tables:
            self.logger.warning("No tables attribute or empty tables. Returning no circuits.")
            return circuits

        # Iterate all recognized tables
        for t_idx, table in enumerate(result.tables):
            self.logger.info(f"DEBUG: Table {t_idx} has {len(table.cells)} cells, row_count={table.row_count}, col_count={table.column_count}")

            # If we think it's a circuit table
            if self._is_circuit_table(table):
                # 1) Identify which row is the header (circuit/breaker/etc.)
                header_row_idx = self._get_header_row(table)
                if header_row_idx < 0:
                    self.logger.info("No suitable header row found. Skipping table.")
                    continue

                # 2) For each row after header_row_idx, parse circuit data
                for row_idx in range(header_row_idx + 1, table.row_count):
                    circuit = self._process_circuit_row(table, row_idx, header_row_idx)
                    if circuit:
                        circuits.append(circuit)

        return circuits

    def _is_circuit_table(self, table) -> bool:
        """
        Determine if a table looks like a circuit table by checking row 0 text
        for keywords like 'circuit', 'breaker', 'amp', 'pole', 'load'.
        """
        keywords = ["circuit", "breaker", "load", "amp", "pole"]
        # Collect all cells in row 0
        row0_cells = [c for c in table.cells if c.row_index == 0]
        header_text = " ".join(c.content.lower() for c in row0_cells)

        return any(keyword in header_text for keyword in keywords)

    def _get_header_row(self, table) -> int:
        """
        Find a row that includes 'circuit' and either 'breaker' or 'load'.
        If none is found, return -1.
        """
        for row_idx in range(table.row_count):
            row_cells = [c for c in table.cells if c.row_index == row_idx]
            row_text = " ".join(cell.content.lower() for cell in row_cells)

            if "circuit" in row_text and ("breaker" in row_text or "load" in row_text):
                return row_idx

        return -1

    def _process_circuit_row(self, table, row_idx: int, header_row_idx: int) -> Dict:
        """
        Map each cell in the row to its 'header' cell. We rely on column_index to match them up.
        Return a dictionary describing the circuit if we get a 'circuit number', else None.
        """
        row_cells = [c for c in table.cells if c.row_index == row_idx]
        header_cells = [c for c in table.cells if c.row_index == header_row_idx]

        # Sort by column_index so they line up
        row_cells_sorted = sorted(row_cells, key=lambda x: x.column_index)
        header_cells_sorted = sorted(header_cells, key=lambda x: x.column_index)

        circuit = {
            "number": "",
            "poles": "",
            "breaker_size": "",
            "load_description": "",
            "load_kva": "",
            "phase": ""
        }

        # For each column, see if the header cell has a matching keyword
        for col_idx, cell_data in enumerate(row_cells_sorted):
            if col_idx < len(header_cells_sorted):
                header_text = header_cells_sorted[col_idx].content.lower()
                value = cell_data.content.strip()

                if "circuit" in header_text or "no" in header_text:
                    circuit["number"] = value
                elif "pole" in header_text:
                    circuit["poles"] = value
                elif "breaker" in header_text or "amp" in header_text:
                    circuit["breaker_size"] = value
                elif "description" in header_text or "load" in header_text:
                    circuit["load_description"] = value
                elif "kva" in header_text:
                    circuit["load_kva"] = value
                elif "phase" in header_text:
                    circuit["phase"] = value

        return circuit if circuit["number"] else None

    def _process_table_cell(self, parsed_data: Dict, text: str, table, cell):
        """
        Helper method to detect references like 'Main Panel', 'Distribution Panel', 'Load Center'.
        We then grab the next cell's content (i.e., to the right) as the "panel name" or similar.
        """
        try:
            if "main" in text and "panel" in text:
                parsed_data["MainPanel"]["panel"]["type"] = "MainPanel"
                next_val = self._get_adjacent_cell_value(table, cell)
                if next_val:
                    parsed_data["MainPanel"]["panel"]["name"] = next_val
            
            elif "distribution" in text and "panel" in text:
                parsed_data["DistributionPanel"]["panel"]["type"] = "DistributionPanel"
                next_val = self._get_adjacent_cell_value(table, cell)
                if next_val:
                    parsed_data["DistributionPanel"]["panel"]["name"] = next_val
            
            elif "load center" in text:
                parsed_data["LoadCenter"]["panelboard_schedule"]["designation"] = "LoadCenter"
                next_val = self._get_adjacent_cell_value(table, cell)
                if next_val:
                    parsed_data["LoadCenter"]["panelboard_schedule"]["designation"] = next_val

        except Exception as e:
            self.logger.error(f"Error processing table cell: {str(e)}")

    def _get_adjacent_cell_value(self, table, cell) -> str:
        """
        Try to find the cell in the same row, next column over. If missing, return "".
        Because table.cells is flat, filter by row_index then find column_index + 1.
        """
        row_idx = cell.row_index
        col_idx = cell.column_index + 1

        # Find a cell that matches (row_idx, col_idx)
        next_cell = next(
            (c for c in table.cells if c.row_index == row_idx and c.column_index == col_idx),
            None
        )
        return next_cell.content.strip() if next_cell else ""

    # The revision or date processing can remain as-is or be removed if not needed.
