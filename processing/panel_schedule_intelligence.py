from azure.core.credentials import AzureKeyCredential
from azure.ai.documentintelligence import DocumentIntelligenceClient
from azure.ai.documentintelligence.models import AnalyzeDocumentRequest
import logging
import os
import json
from typing import Dict
from openai import AsyncOpenAI
from azure.ai.documentintelligence.models import DocumentAnalysisFeature

class PanelScheduleProcessor:
    """
    Azure Document Intelligence processor specifically for electrical panel schedules,
    now using 'prebuilt-read' purely to extract text. Then we use GPT for the structuring.
    """

    def __init__(self, endpoint: str, api_key: str, **kwargs):
        self.client = DocumentIntelligenceClient(
            endpoint=endpoint,
            credential=AzureKeyCredential(api_key)
        )
        self.logger = logging.getLogger(__name__)

    async def process_panel_schedule(self, file_path: str, gpt_client: AsyncOpenAI) -> Dict:
        """
        1) Use 'prebuilt-layout' to perform OCR on the PDF.
        2) Concatenate recognized text into raw_content.
        3) Pass raw_content to GPT to produce structured JSON.
        """
        fallback_output = {"panel": {}, "circuits": [], "error": None}

        try:
            self.logger.debug(f"Processing: {file_path}")
            
            with open(file_path, "rb") as f:
                poller = self.client.begin_analyze_document(
                    "prebuilt-layout",
                    document=f,
                    content_type="application/pdf"
                )
            
            result = poller.result()
            self.logger.debug("Azure Document Intelligence completed successfully.")

            raw_content = self._extract_azure_read_text(result)
            self.logger.debug(f"raw_content length: {len(raw_content)} characters")

            structured_json = await self._call_gpt_for_structuring(raw_content, gpt_client)
            self.logger.debug(f"GPT returned a dict with keys: {list(structured_json.keys())}")

            return structured_json

        except Exception as e:
            self.logger.exception(f"Failed to process panel schedule: {e}")
            fallback_output["error"] = str(e)
            return fallback_output

    def _extract_azure_read_text(self, result) -> str:
        """
        Extracts text from the Document Intelligence 'prebuilt-read' result object.
        Returns a single string containing all lines from all pages.
        """
        all_text = []
        if not result or not getattr(result, "pages", None):
            self.logger.warning("No pages found in the DocumentIntelligence result.")
            return ""

        self.logger.debug(f"Number of pages found: {len(result.pages)}")
        for page_index, page in enumerate(result.pages):
            self.logger.debug(f"Page {page_index+1} has {len(page.lines)} lines.")
            for line in page.lines:
                all_text.append(line.content)
        return "\n".join(all_text)

    async def _call_gpt_for_structuring(self, raw_content: str, gpt_client: AsyncOpenAI) -> Dict:
        """
        Calls GPT with instructions to produce structured JSON from raw panel schedule text.
        """
        system_prompt = (
            "You are an expert in electrical engineering who structures panel schedule data into JSON. "
            "Please parse the raw OCR text and produce a well-formed JSON object. "
            "Include fields like 'panel name', 'voltage', 'feed', 'circuits', 'trip rating', 'load name', 'phases', 'amps', 'amperage', etc. The content may vary, "
            "so be flexible when naming fields. Use only JSON in your final output."
        )

        # Log truncated content for debugging
        user_prompt = f"Raw OCR text (first 500 chars shown):\n{raw_content[:500]}...\n\n" \
                     "Please structure this into valid JSON. Be flexible with circuit naming."

        self.logger.debug("Sending prompt to GPT.")
        try:
            response = await gpt_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.2,
                max_tokens=3000
            )
            content = response.choices[0].message.content
            self.logger.debug(f"GPT raw response (first 200 chars): {content[:200]}...")
            return json.loads(content)
        except Exception as e:
            self.logger.error(f"Error calling GPT to structure data: {str(e)}")
            return {
                "panel": {},
                "circuits": [],
                "raw_gpt_output": content if 'content' in locals() else "",
                "error": str(e)
            }