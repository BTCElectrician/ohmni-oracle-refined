import logging
import os
import json
from typing import Dict, List

from azure.core.credentials import AzureKeyCredential
from azure.ai.documentintelligence import DocumentIntelligenceClient

class PanelScheduleProcessor:
    """
    A minimal approach to ensure we capture *all* text from a PDF recognized as
    a 'panel schedule,' WITHOUT using GPT at all. This eliminates issues with
    malformed JSON or chunking errors from GPT.

    Steps:
      1. 'prebuilt-read' to extract all text
      2. Split text into ~5000-char chunks (to keep the final JSON from being massive)
      3. Return a final JSON with those chunks
    """

    def __init__(self, endpoint: str, api_key: str, **kwargs):
        """
        Args:
            endpoint (str): e.g. "https://<region>.api.cognitive.microsoft.com/"
            api_key (str): Your Azure Document Intelligence API key
        """
        self.client = DocumentIntelligenceClient(
            endpoint=endpoint,
            credential=AzureKeyCredential(api_key)
        )
        self.logger = logging.getLogger(__name__)

        # You can adjust how big each chunk is
        self.max_chars_per_chunk = 5000

    def process_panel_schedule(self, file_path: str) -> Dict:
        """
        Main pipeline:
          - Use 'prebuilt-read' to OCR the PDF
          - Split the text into chunks of ~5000 characters
          - Return a JSON-like dict with all chunks

        Returns:
          {
            "file_name": "<filename>",
            "extracted_chunks": [
              { "chunk_index": 1, "chunk_text": "..." },
              { "chunk_index": 2, "chunk_text": "..." },
              ...
            ]
          }
        """
        # We'll build this fallback if something fails
        fallback_output = {
            "file_name": os.path.basename(file_path),
            "extracted_chunks": [],
            "error": None
        }
        try:
            self.logger.info(f"Processing potential panel schedule: {file_path}")

            # 1) Read PDF bytes
            with open(file_path, "rb") as f:
                pdf_bytes = f.read()

            # 2) Analyze with 'prebuilt-read' from azure-ai-documentintelligence==1.0.0
            poller = self.client.begin_analyze_document(
                model_id="prebuilt-read",
                body=pdf_bytes,
                content_type="application/pdf"
            )
            result = poller.result()
            self.logger.info("Azure Document Intelligence completed successfully.")

            # 3) Extract text
            raw_content = self._extract_azure_read_text(result)
            self.logger.info(f"Extracted PDF content length: {len(raw_content)} characters")

            # 4) Split into chunks
            chunks = self._chunk_text(raw_content, self.max_chars_per_chunk)
            self.logger.info(f"Split OCR text into {len(chunks)} chunk(s).")

            # 5) Build final JSON
            final_result = {
                "file_name": os.path.basename(file_path),
                "extracted_chunks": [],
            }
            for i, chunk_text in enumerate(chunks, start=1):
                final_result["extracted_chunks"].append({
                    "chunk_index": i,
                    "chunk_text": chunk_text
                })

            return final_result

        except Exception as e:
            self.logger.exception(f"Failed to process panel schedule: {e}")
            fallback_output["error"] = str(e)
            return fallback_output

    def _extract_azure_read_text(self, result) -> str:
        """
        Extract text from the 'prebuilt-read' result object.
        Returns a single string with all lines from all pages.
        """
        if not result or not getattr(result, "pages", None):
            self.logger.warning("No pages found in the DocumentIntelligence result.")
            return ""

        all_lines = []
        for page in result.pages:
            for line in page.lines:
                all_lines.append(line.content)
        return "\n".join(all_lines)

    def _chunk_text(self, text: str, max_chars: int) -> List[str]:
        """
        Splits a large string into multiple segments, each up to max_chars long.
        """
        chunks = []
        start_idx = 0
        while start_idx < len(text):
            end_idx = start_idx + max_chars
            chunk = text[start_idx:end_idx]
            chunks.append(chunk)
            start_idx = end_idx
        return chunks
