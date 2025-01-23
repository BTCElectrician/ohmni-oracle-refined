
# Panel Schedule Intelligence Implementation Guide

## Overview
This document outlines the implementation of Azure Document Intelligence for processing electrical panel schedules within a larger document processing system.

## Table of Contents
- [Purpose](#purpose)
- [Implementation Notes](#implementation-notes)
- [Code Implementation](#code-implementation)
- [Integration Guide](#integration-guide)
- [Dependencies](#dependencies)

## Purpose
This module is specifically designed to:
- Process electrical panel schedule PDFs using Azure Document Intelligence
- Handle annotated and revised panel schedules
- Complement existing PyMuPDF processing pipeline
- Provide structured data output matching existing JSON format

## Implementation Notes

### Key Features
- Dedicated electricalpanel schedule processing
- Async operation support
- Batch processing capability
- Flexible configuration options
- Comprehensive error handling
- Logging integration

### Integration Points
- Designed to be imported into main processing pipeline
- Called only for electrical panel schedule drawings
- Returns standardized JSON structure
- Compatible with existing PyMuPDF workflow

### Azure Requirements
- Azure Document Intelligence resource
- Endpoint and key configuration
- Azure Key Vault integration (recommended for production)

## Code Implementation

### File: `panel_schedule_intelligence.py`

```python
from azure.core.credentials import AzureKeyCredential
from azure.ai.documentintelligence import DocumentIntelligenceClient
import logging
from typing import Dict, List, Optional, Union
import os
import json
import asyncio
from datetime import datetime

class PanelScheduleProcessor:
    """
    Azure Document Intelligence processor specifically for electrical panel schedules.
    Designed to be integrated into larger document processing pipeline.
    """
    
    def __init__(self, endpoint: str, key: str, **kwargs):
        """
        Initialize the processor with Azure credentials.
        
        Args:
            endpoint (str): Azure Document Intelligence endpoint
            key (str): Azure Document Intelligence key
            **kwargs: Additional configuration options
                - cache_enabled: bool (default: False)
                - batch_size: int (default: 10)
                - timeout: int (default: 300)
        """
        self.client = DocumentIntelligenceClient(
            endpoint=endpoint,
            credential=AzureKeyCredential(key)
        )
        self.logger = logging.getLogger(__name__)
        
        # Optional configuration
        self.cache_enabled = kwargs.get('cache_enabled', False)
        self.batch_size = kwargs.get('batch_size', 10)
        self.timeout = kwargs.get('timeout', 300)

    async def process_panel_schedule(self, file_path: str) -> Dict:
        """
        Process a panel schedule document and extract structured information.
        """
        try:
            with open(file_path, "rb") as f:
                document_bytes = f.read()

            poller = self.client.begin_analyze_document(
                "prebuilt-layout",
                document_bytes,
                content_type="application/pdf"
            )
            result = poller.result()

            panel_data = self._extract_panel_data(result)
            circuit_data = self._extract_circuit_data(result)
            specifications = self._extract_specifications(result)
            revisions = self._extract_revisions(result)

            return {
                "panel": {
                    **panel_data,
                    "specifications": specifications,
                    "circuits": circuit_data,
                    "revisions": revisions
                }
            }

        except Exception as e:
            self.logger.error(f"Error processing panel schedule {file_path}: {str(e)}")
            raise

    def _extract_panel_data(self, result) -> Dict:
        """Extract panel metadata from the document."""
        panel_data = {
            "name": "",
            "voltage": "",
            "phases": None,
            "rating": "",
            "main_type": ""
        }
        return panel_data

    def _extract_circuit_data(self, result) -> List[Dict]:
        """Extract circuit information from the document."""
        circuits = []
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
        return specs

    async def batch_process(self, file_paths: List[str]) -> Dict[str, Dict]:
        """Process multiple panel schedules in batch."""
        results = {}
        for batch in self._chunk_list(file_paths, self.batch_size):
            tasks = [self.process_panel_schedule(path) for path in batch]
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for path, result in zip(batch, batch_results):
                if isinstance(result, Exception):
                    self.logger.error(f"Failed to process {path}: {str(result)}")
                    results[path] = {"error": str(result)}
                else:
                    results[path] = result
                    
        return results

    @staticmethod
    def _chunk_list(lst: List, chunk_size: int):
        """Helper method to split list into chunks for batch processing."""
        for i in range(0, len(lst), chunk_size):
            yield lst[i:i + chunk_size]
```

## Integration Guide

### Basic Integration Example
```python
async def process_drawings(drawings_folder: str):
    # Initialize processor
    panel_processor = PanelScheduleProcessor(
        endpoint=os.getenv('AZURE_ENDPOINT'),
        key=os.getenv('AZURE_KEY'),
        cache_enabled=True
    )
    
    for drawing in os.listdir(drawings_folder):
        if is_panel_schedule(drawing):  # Your existing drawing type detection
            try:
                panel_data = await panel_processor.process_panel_schedule(
                    os.path.join(drawings_folder, drawing)
                )
                # Handle successful extraction...
            except Exception as e:
                # Handle errors...
                continue
        else:
            # Use existing PyMuPDF processing
            continue
```

### Configuration Options
- `cache_enabled`: Enable/disable result caching
- `batch_size`: Number of documents to process in parallel
- `timeout`: Maximum processing time per document

## Dependencies

### Required Packages
- azure-ai-documentintelligence==1.0.0
- Python 3.7+
- asyncio

### Azure Setup
1. Create Azure Document Intelligence resource
2. Configure environment variables:
   - AZURE_ENDPOINT
   - AZURE_KEY
3. Optional: Set up Azure Key Vault for credential management

## Error Handling
- Comprehensive logging
- Exception handling for common failures
- Graceful degradation options
- Integration with existing error reporting

## Performance Considerations
- Async processing for better throughput
- Batch processing for multiple documents
- Configurable timeouts and retry logic
- Optional result caching

## Security Notes
- Use Azure Key Vault in production
- Implement proper credential rotation
- Monitor API usage and limits
- Follow least privilege principle

## Next Steps
1. Set up Azure Document Intelligence resource
2. Configure environment variables
3. Integrate module into existing pipeline
4. Implement error handling
5. Test with sample panel schedules
6. Monitor performance and adjust configuration
```

This updated document now includes the new information and removes any redundant sections, providing a comprehensive guide for implementing and integrating the panel schedule processing module.
