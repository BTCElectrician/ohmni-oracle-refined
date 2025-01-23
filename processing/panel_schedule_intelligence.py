
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

            # Extract structured data from the result
            panel_data = self._extract_panel_data(result)
            circuit_data = self._extract_circuit_data(result)
            specs = self._extract_specifications(result)
            revisions = self._extract_revisions(result)

            # Return a dict that can be serialized to JSON
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
        """Extract basic panel metadata from the document."""
        panel_data = {
            "name": "",
            "voltage": "",
            "phases": None,
            "rating": "",
            "main_type": ""
        }
        
        # Process tables to find panel information
        for table in result.tables:
            for cell in table.cells:
                text = cell.content.lower()
                if "panel" in text or "name" in text:
                    # Look for adjacent cell with panel name
                    panel_data["name"] = self._get_adjacent_cell_value(table, cell)
                elif "voltage" in text:
                    panel_data["voltage"] = self._get_adjacent_cell_value(table, cell)
                elif "phase" in text:
                    phase_text = self._get_adjacent_cell_value(table, cell)
                    try:
                        panel_data["phases"] = int(phase_text.split()[0])
                    except (ValueError, IndexError):
                        pass
                elif "rating" in text or "amp" in text:
                    panel_data["rating"] = self._get_adjacent_cell_value(table, cell)
                elif "main" in text and ("type" in text or "breaker" in text):
                    panel_data["main_type"] = self._get_adjacent_cell_value(table, cell)
        
        return panel_data

    def _extract_circuit_data(self, result) -> List[Dict]:
        """Extract circuit information from the document tables."""
        circuits = []
        
        for table in result.tables:
            # Look for tables with circuit information
            if self._is_circuit_table(table):
                header_row = self._get_header_row(table)
                if not header_row:
                    continue
                
                # Process each row as a circuit
                for row_idx in range(header_row + 1, len(table.cells)):
                    circuit = self._process_circuit_row(table, row_idx, header_row)
                    if circuit:
                        circuits.append(circuit)
        
        return circuits

    def _extract_specifications(self, result) -> Dict:
        """Extract panel specifications from the document."""
        specs = {
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
        
        # Process text and tables for specifications
        for table in result.tables:
            for cell in table.cells:
                text = cell.content.lower()
                if "nema" in text:
                    specs["nema_enclosure"] = self._get_adjacent_cell_value(table, cell)
                elif "section" in text:
                    specs["sections"] = self._get_adjacent_cell_value(table, cell)
                elif "dimension" in text or "size" in text:
                    dim_text = self._get_adjacent_cell_value(table, cell)
                    self._parse_dimensions(dim_text, specs["dimensions"])
        
        return specs

    def _extract_revisions(self, result) -> List[Dict]:
        """Extract revision history if present in the document."""
        revisions = []
        
        for table in result.tables:
            if self._is_revision_table(table):
                for row_idx in range(1, len(table.cells)):
                    revision = self._process_revision_row(table, row_idx)
                    if revision:
                        revisions.append(revision)
        
        return revisions

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