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
    Designed to be integrated into the document processing pipeline.
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
            self.logger.info(f"DEBUG: Azure analysis complete for {file_path}")

            # Extract core panel data
            extracted_data = self._extract_panel_data(result)
            # Extract circuit information
            circuit_info = self._extract_circuit_data(result)

            # Combine into final structure
            final_output = {
                "PanelName": extracted_data.get("PanelName", ""),
                "GenericPanelTypes": {
                    "LoadCenter": extracted_data.get("LoadCenter", {}),
                    "MainPanel": extracted_data.get("MainPanel", {}),
                    "DistributionPanel": extracted_data.get("DistributionPanel", {})
                },
                "circuits": circuit_info
            }

            return final_output

        except Exception as e:
            self.logger.exception(f"Azure Document Intelligence processing failed for {file_path}")
            raise

    def _extract_panel_data(self, result) -> Dict:
        """
        Extract panel data according to the new schema structure.
        """
        self.logger.info("DEBUG: Entering _extract_panel_data method")

        # Log recognized documents & fields
        if hasattr(result, "documents"):
            self.logger.info(f"DEBUG: Found {len(result.documents)} document(s)")
            for i, doc in enumerate(result.documents):
                self.logger.info(f"DEBUG: Document {i} => {len(doc.fields)} fields")
                for field_name, field_value in doc.fields.items():
                    self.logger.info(f"Field '{field_name}' => '{field_value.value}' (conf={field_value.confidence})")

        # Initialize the new schema structure
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

        # Process tables to find panel information
        for table in result.tables:
            for cell in table.cells:
                text = cell.content.lower()
                
                # Check for panel name pattern
                if PANEL_NAME_PATTERN.match(cell.content.strip()):
                    parsed_data["PanelName"] = cell.content.strip()
                    self.logger.info(f"Regex match: Found panel name '{cell.content.strip()}'")

                # Process other fields based on content
                self._process_table_cell(parsed_data, text, table, cell)

        return parsed_data

    def _process_table_cell(self, parsed_data: Dict, text: str, table, cell):
        """Helper method to process individual table cells and update parsed_data"""
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

    def _extract_circuit_data(self, result) -> List[Dict]:
        """
        Extract circuit information from the document tables.
        """
        self.logger.info("DEBUG: Entering _extract_circuit_data method")
        circuits = []

        if hasattr(result, "tables"):
            for t_idx, table in enumerate(result.tables):
                self.logger.info(f"DEBUG: Table {t_idx} has {len(table.cells)} cells")
                
                if self._is_circuit_table(table):
                    header_row = self._get_header_row(table)
                    if header_row >= 0:
                        for row_idx in range(header_row + 1, len(table.cells)):
                            circuit = self._process_circuit_row(table, row_idx, header_row)
                            if circuit:
                                circuits.append(circuit)

        return circuits

    def _get_adjacent_cell_value(self, table, cell) -> str:
        """Helper method to get the value from an adjacent cell."""
        try:
            next_cell = table.cells[cell.row_index][cell.column_index + 1]
            return next_cell.content.strip()
        except IndexError:
            return ""

    def _is_circuit_table(self, table) -> bool:
        """Determine if a table contains circuit information."""
        keywords = ["circuit", "breaker", "load", "amp", "pole"]
        header_text = " ".join(cell.content.lower() for cell in table.cells[0])
        return any(keyword in header_text for keyword in keywords)

    def _get_header_row(self, table) -> int:
        """Find the header row index in a table."""
        for row_idx, row in enumerate(table.cells):
            row_text = " ".join(cell.content.lower() for cell in row)
            if "circuit" in row_text and ("breaker" in row_text or "load" in row_text):
                return row_idx
        return -1

    def _process_circuit_row(self, table, row_idx: int, header_row: int) -> Dict:
        """Process a single circuit row from the table."""
        try:
            row = table.cells[row_idx]
            headers = [cell.content.lower() for cell in table.cells[header_row]]
            
            circuit = {
                "number": "",
                "poles": "",
                "breaker_size": "",
                "load_description": "",
                "load_kva": "",
                "phase": ""
            }
            
            for col_idx, cell in enumerate(row):
                header = headers[col_idx] if col_idx < len(headers) else ""
                value = cell.content.strip()
                
                if "circuit" in header or "no" in header:
                    circuit["number"] = value
                elif "pole" in header:
                    circuit["poles"] = value
                elif "breaker" in header or "amp" in header:
                    circuit["breaker_size"] = value
                elif "description" in header or "load" in header:
                    circuit["load_description"] = value
                elif "kva" in header:
                    circuit["load_kva"] = value
                elif "phase" in header:
                    circuit["phase"] = value
            
            return circuit if circuit["number"] else None
            
        except Exception as e:
            self.logger.error(f"Error processing circuit row: {str(e)}")
            return None

    def _is_revision_table(self, table) -> bool:
        """Determine if a table contains revision information."""
        keywords = ["revision", "rev", "date", "description", "by"]
        header_text = " ".join(cell.content.lower() for cell in table.cells[0])
        return any(keyword in header_text for keyword in keywords)

    def _process_revision_row(self, table, row_idx: int) -> Dict:
        """Process a single revision row from the table."""
        try:
            row = table.cells[row_idx]
            revision = {
                "revision": "",
                "date": "",
                "description": "",
                "by": ""
            }
            
            for cell in row:
                text = cell.content.lower().strip()
                if text:
                    if "rev" in text:
                        revision["revision"] = text
                    elif self._is_date(text):
                        revision["date"] = text
                    elif len(text) <= 3:  # Likely initials
                        revision["by"] = text
                    else:
                        revision["description"] = text
            
            return revision if any(revision.values()) else None
            
        except Exception as e:
            self.logger.error(f"Error processing revision row: {str(e)}")
            return None

    def _is_date(self, text: str) -> bool:
        """Simple helper to check if text might be a date."""
        return any(char.isdigit() for char in text) and ("/" in text or "-" in text)

    def _parse_dimensions(self, dim_text: str, dimensions: Dict) -> None:
        """Parse dimension text into height, width, depth values."""
        try:
            parts = dim_text.lower().split("x")
            if len(parts) >= 3:
                dimensions["height"] = parts[0].strip()
                dimensions["width"] = parts[1].strip()
                dimensions["depth"] = parts[2].strip()
        except Exception:
            pass 