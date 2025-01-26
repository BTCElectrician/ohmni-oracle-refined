# processing/panel_schedule_intelligence.py

import os
import logging
import json
import re
from typing import Dict, List, Any

from azure.core.credentials import AzureKeyCredential
from azure.ai.documentintelligence import DocumentIntelligenceClient
from openai import AsyncOpenAI

class PanelScheduleProcessor:
    """
    A chunk-based approach: We split each recognized table into small row groups,
    parse them with GPT individually, then unify the results into one panel object.
    """

    def __init__(self, endpoint: str, api_key: str, **kwargs):
        self.logger = logging.getLogger(__name__)

        # Azure Document Intelligence
        self.document_client = DocumentIntelligenceClient(
            endpoint=endpoint,
            credential=AzureKeyCredential(api_key)
        )
        # GPT
        self.openai_api_key = os.getenv("OPENAI_API_KEY")
        if not self.openai_api_key:
            raise ValueError("OPENAI_API_KEY must be set in environment variables")
        self.gpt_client = AsyncOpenAI(api_key=self.openai_api_key)

        # Additional config
        # You can tweak 'batch_size' to parse, say, 3 or 5 rows at a time.
        self.batch_size = kwargs.get('batch_size', 5)
        self.timeout = kwargs.get('timeout', 300)

    async def process_panel_schedule(self, file_path: str) -> Dict[str, Any]:
        fallback_output = {"panels": [], "error": None}
        try:
            with open(file_path, "rb") as f:
                pdf_bytes = f.read()

            # 1) Analyze with Azure
            poller = self.document_client.begin_analyze_document(
                "prebuilt-layout",
                pdf_bytes,
                content_type="application/pdf"
            )
            result = poller.result()
            self.logger.info(f"DEBUG: Azure analysis complete for {file_path}")

            if not hasattr(result, "tables") or not result.tables:
                self.logger.warning("No tables found in PDF. Possibly no panel schedules?")
                return {"panels": [], "error": None}

            # We'll store multiple panel objects (one per recognized table)
            raw_panels = []
            for t_index, table in enumerate(result.tables):
                panel_obj = await self._process_table_in_chunks(table, t_index+1)
                if panel_obj:
                    raw_panels.append(panel_obj)

            # If multiple panels share the same PanelName, unify them
            merged_panels = self._merge_panels_by_name(raw_panels)

            return {"panels": merged_panels, "error": None}
        except Exception as e:
            self.logger.exception(f"Error processing {file_path}: {e}")
            fallback_output["error"] = str(e)
            return fallback_output

    async def _process_table_in_chunks(self, table, table_number: int) -> Dict[str, Any]:
        """
        Split the table into small row-chunks, parse each chunk with GPT,
        unify the results into a single panel object.
        We'll guess or track a single panel name for the entire table, but
        you can adapt if a single table has multiple panels.
        """
        # Convert table to rows
        all_rows = self._extract_table_rows(table)
        # Divide them in batches of self.batch_size
        chunked_rows = []
        for i in range(0, len(all_rows), self.batch_size):
            chunk = all_rows[i:i+self.batch_size]
            chunked_rows.append(chunk)

        # We'll keep track of all circuits from all chunks
        all_circuits = []
        # Also track panel name / type if GPT mentions them
        panel_name = ""
        panel_type = ""
        specifications = {}
        dimensions = {}
        panel_totals = {}

        for c_index, chunk_rows in enumerate(chunked_rows):
            # Convert chunk_rows to text
            chunk_text = self._chunk_rows_to_text(chunk_rows)
            # Call GPT
            parse_result = await self._ask_gpt_for_rows(
                chunk_text,
                table_number,
                chunk_index=(c_index+1)
            )
            # parse_result might have a partial "PanelName" or "circuits"

            # Unify
            if parse_result.get("PanelName"):
                panel_name = panel_name or parse_result["PanelName"]
            if parse_result.get("PanelType"):
                panel_type = panel_type or parse_result["PanelType"]
            if parse_result.get("circuits"):
                all_circuits += parse_result["circuits"]

            # specs/dims/panel_totals
            for key in ["specifications","dimensions","panel_totals"]:
                new_val = parse_result.get(key, {})
                if new_val:  # if not empty
                    if key == "specifications":
                        specifications = {**specifications, **new_val}
                    elif key == "dimensions":
                        dimensions = {**dimensions, **new_val}
                    elif key == "panel_totals":
                        panel_totals = {**panel_totals, **new_val}

        # Deduplicate circuits, unify them
        all_circuits = self._deduplicate_circuits(all_circuits)

        # Build final panel object
        panel_obj = {
            "PanelName": panel_name,
            "PanelType": panel_type or "Other",
            "circuits": all_circuits,
            "specifications": specifications,
            "dimensions": dimensions,
            "panel_totals": panel_totals
        }

        # Optionally skip if no circuits found
        if not all_circuits and not panel_name:
            return {}

        return panel_obj

    def _extract_table_rows(self, table) -> List[List[str]]:
        """
        Return a list of lists. Each sub-list is a row of text cells.
        e.g. [ ["1-3-5", "CU-1.2", "50A"], ["2-4-6", "WH-1", "70A"] ]
        """
        rows_data = [[] for _ in range(table.row_count)]
        for cell in table.cells:
            txt = cell.content.strip()
            rows_data[cell.row_index].append(txt)
        return rows_data

    def _chunk_rows_to_text(self, chunk_rows: List[List[str]]) -> str:
        """
        Convert a list of row-arrays into a small text snippet.
        For example:
          Row 1: 1-3-5 | CU-1.2 | 50A
          Row 2: 2-4-6 | WH-1   | 70A
        """
        lines = []
        for r_index, row in enumerate(chunk_rows):
            row_str = " | ".join(row)
            lines.append(f"Row {r_index+1}: {row_str}")
        return "\n".join(lines)

    async def _ask_gpt_for_rows(self, rows_text: str, table_number: int, chunk_index: int) -> Dict[str, Any]:
        """
        Ask GPT to parse these chunked rows. Because each chunk is small,
        GPT is less likely to skip or merge them incorrectly.
        """
        system_prompt = (
            "You are an expert at reading partial panel schedule rows.\n"
            "You see a few rows from a panel schedule. Return a JSON with:\n"
            "  'PanelName': (string, if found),\n"
            "  'PanelType': (if found among the data),\n"
            "  'circuits': an array of circuit objects with keys:\n"
            "     circuit, load_name, trip, poles, connected_load (optional)\n"
            "  'specifications': {}, 'dimensions': {}, 'panel_totals': {}\n"
            "If the rows only have partial info, return what you can.\n"
            "Do NOT unify duplicates across other chunks. Just parse these rows.\n"
            "No extra text, only JSON.\n"
        )

        user_prompt = (
            f"TABLE {table_number}, CHUNK {chunk_index}:\n\n{rows_text}\n\n"
            "Extract circuits from these rows, plus any panel name or type you find. Return valid JSON only."
        )

        try:
            resp = await self.gpt_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                max_tokens=1000,
                temperature=0.0
            )
            content = resp.choices[0].message.content.strip()
            data = json.loads(content)

            # Ensure structure
            for key in ["PanelName","PanelType","circuits","specifications","dimensions","panel_totals"]:
                if key not in data:
                    if key == "circuits":
                        data[key] = []
                    elif key in ["specifications","dimensions","panel_totals"]:
                        data[key] = {}
                    else:
                        data[key] = ""
            return data
        except Exception as e:
            self.logger.error(f"GPT parse error (table {table_number}, chunk {chunk_index}): {e}")
            return {
                "PanelName": "",
                "PanelType": "",
                "circuits": [],
                "specifications": {},
                "dimensions": {},
                "panel_totals": {}
            }

    def _deduplicate_circuits(self, circuits: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Basic deduplicate logic. If GPT repeated the same circuit #, unify them.
        Also cast circuit to string in case GPT gave an int.
        """
        final = []
        seen = set()

        def norm(value):
            # cast to string to avoid 'int' object has no attribute 'lower'
            s = str(value)
            return s.lower().replace(" ","")

        for c in circuits:
            circuit_val = c.get("circuit","")
            c_str = norm(circuit_val)
            if c_str in seen:
                continue
            seen.add(c_str)
            final.append(c)
        return final

    def _merge_panels_by_name(self, raw_panels: List[Dict[str,Any]]) -> List[Dict[str,Any]]:
        """
        If multiple tables produce the same PanelName, unify them by name.
        """
        merged_dict = {}
        for p in raw_panels:
            name = p.get("PanelName","Unknown").strip()
            key = name.lower() or "unknown"
            if key not in merged_dict:
                merged_dict[key] = p
            else:
                existing = merged_dict[key]
                # merge circuits
                existing["circuits"] += p["circuits"]
                existing["circuits"] = self._deduplicate_circuits(existing["circuits"])
                # Merge specs, etc.
                for k in ["specifications","dimensions","panel_totals"]:
                    merged_val = {**existing.get(k, {}), **p.get(k, {})}
                    existing[k] = merged_val
                # fill name/type if missing
                if not existing["PanelName"] and p["PanelName"]:
                    existing["PanelName"] = p["PanelName"]
                if existing["PanelType"]=="Other" and p["PanelType"]!="Other":
                    existing["PanelType"] = p["PanelType"]
                merged_dict[key] = existing
        return list(merged_dict.values())
