import os
import logging
from typing import List

logger = logging.getLogger(__name__)

def traverse_job_folder(job_folder: str) -> List[str]:
    """
    Traverse the job folder and collect all PDF files.
    """
    pdf_files = []
    try:
        for root, _, files in os.walk(job_folder):
            for file in files:
                if file.lower().endswith('.pdf'):
                    pdf_files.append(os.path.join(root, file))
        logger.info(f"Found {len(pdf_files)} PDF files in {job_folder}")
    except Exception as e:
        logger.error(f"Error traversing job folder {job_folder}: {str(e)}")
    return pdf_files

def cleanup_temporary_files(output_folder: str) -> None:
    """
    Clean up any temporary files created during processing (not currently used).
    """
    pass

def get_project_name(job_folder: str) -> str:
    """
    Extract the project name from the job folder path.
    """
    return os.path.basename(job_folder)
