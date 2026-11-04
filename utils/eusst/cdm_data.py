########################################
# EU SST CDMS & Events
########################################

#---------------------------------------
# Import Modules
#---------------------------------------

# Python Standard Library
import json
import os
import sys
import time

import datetime as dt
import xml.etree.ElementTree as ET

from typing import Dict, List, Optional
from pathlib import Path

# External Dependencies
import httpx
import polars as pl

# Internal project imports
from utils.api_helpers import *
from utils.eusst.config import *
from utils.ap_logs import get_logger

#---------------------------------------
# Configure Logger
#---------------------------------------

logger = get_logger()

#---------------------------------------
# EU SST API CALLS
#---------------------------------------


def get_eusst_data(data_type: str, query_params: dict = None) -> list:
    """
    Unified pagination engine for EU SST datasets.
    
    Accepts:
        data_type: "cdm" or "event"
        query_params: Optional dict of OData filters/parameters
    """
    # 1. Map the parameter to the correct config URL
    if data_type.lower() == "cdm":
        url = EUSST_CDM_URL
    elif data_type.lower() == "event":
        url = EUSST_EVENT_URL
    elif data_type.lower() == "report":
        url = EUSST_REPORT_URL
    else:
        raise ValueError(
            f"Invalid data_type '{data_type}'. Must be 'cdm' or 'event'."
        )

    current_params = query_params.copy() if query_params else {}
    skip_value = int(current_params.get("$skip", 0))

    master_records_list = []
    page_count = 1

    while True:
        current_params["$skip"] = str(skip_value)
        logger.info(
            f"Fetching {data_type.upper()} page {page_count} (Current skip: {skip_value})..."
        )

        # 2. Call the single generic api_call worker
        raw_text = api_call(
            service_name="eusst", url=url, query_params=current_params
        )

        # Scenario A: Clean break on 204 No Content
        if not raw_text:
            logger.info(
                f"Received 204 No Content on page {page_count}. Collection finalized."
            )
            break

        data = json.loads(raw_text)
        page_records = data.get("value", []) if isinstance(data, dict) else data

        if not page_records:
            logger.info(
                f"No more records returned for {data_type.upper()}. Stopping collection."
            )
            break

        master_records_list.extend(page_records)
        logger.info(
            f"Collected {len(page_records)} {data_type.upper()} records from page {page_count}."
        )

        # Check if we hit the standard OData limit cap
        if len(page_records) < 500:
            break

        skip_value += 500
        page_count += 1

    return master_records_list


#---------------------------------------
# Process CDMs to Data Formats
#---------------------------------------


def _parse_cdm_xml(xml_string: str) -> dict:
    """Internal helper to parse the cdmAsXml string into a flat dictionary."""
    xml_data = {}
    if not xml_string:
        return xml_data

    try:
        root = ET.fromstring(xml_string.strip())

        # 1. Parse relativeMetadataData attributes
        metadata_data = root.find(".//relativeMetadataData")
        if metadata_data is not None:
            for elem in metadata_data:
                if elem.tag != "relativeStateVector" and elem.text and elem.text.strip(
                ):
                    if elem.tag == "COMMENT":
                        xml_data["xml_comment"] = (
                            xml_data.get("xml_comment", "") + " | "
                            + elem.text.strip()
                        ).strip(" | ")
                    else:
                        xml_data[f"xml_{elem.tag}"] = elem.text.strip()

            # 2. Parse nested relativeStateVector fields
            state_vector = metadata_data.find("relativeStateVector")
            if state_vector is not None:
                for elem in state_vector:
                    if elem.text and elem.text.strip():
                        xml_data[f"xml_{elem.tag}"] = elem.text.strip()

        # 3. Parse Segment blocks (Object 1 and Object 2)
        segments = root.findall(".//segment")
        for i, segment in enumerate(segments, start=1):
            prefix = f"xml_obj{i}_"

            metadata = segment.find("metadata")
            if metadata is not None:
                for elem in metadata:
                    if elem.text and elem.text.strip(
                    ) and elem.tag != "COMMENT":
                        xml_data[f"{prefix}{elem.tag}"] = elem.text.strip()

            state_vec = segment.find(".//stateVector")
            if state_vec is not None:
                for elem in state_vec:
                    if elem.text and elem.text.strip():
                        xml_data[f"{prefix}{elem.tag}"] = elem.text.strip()

    except ET.ParseError as e:
        logger.warning(f"Warning: Failed to parse XML string: {e}")

    return xml_data


def eusst_cdms_json(raw_cdms) -> List[Dict]:
    """Parses raw API data structural wrappers and returns clean JSON."""
    if not raw_cdms:
        return []

    records = raw_cdms.get("value",
                           [raw_cdms]) if isinstance(raw_cdms,
                                                     dict) else list(raw_cdms)
    fully_parsed_json_list = []

    for record in records:
        if not isinstance(record, dict):
            continue

        xml_string = record.get("cdmAsXml", "")
        xml_flat_fields = _parse_cdm_xml(xml_string)

        combined_record = {
            **record,
            **xml_flat_fields
        }
        combined_record.pop("cdmAsXml", None)
        fully_parsed_json_list.append(combined_record)

    return fully_parsed_json_list


def eusst_cdms_df(raw_cdms) -> pl.DataFrame:
    """Parses raw data streams into a structured Polars DataFrame."""
    if not raw_cdms:
        return pl.DataFrame()

    records = raw_cdms.get("value",
                           [raw_cdms]) if isinstance(raw_cdms,
                                                     dict) else list(raw_cdms)
    processed_records = []

    for record in records:
        if not isinstance(record, dict):
            continue

        xml_string = record.get("cdmAsXml", "")
        xml_flat_fields = _parse_cdm_xml(xml_string)

        combined_record = {
            **record,
            **xml_flat_fields
        }
        combined_record.pop("cdmAsXml", None)

        if "headerComments" in combined_record and isinstance(
                combined_record["headerComments"], list):
            combined_record["headerComments"] = ", ".join(
                combined_record["headerComments"]
            )

        processed_records.append(combined_record)

    if not processed_records:
        return pl.DataFrame()

    df = pl.DataFrame(processed_records)

    cast_operations = []
    float_cols = [
        "missDistance",
        "collisionProbability",
        "relativeSpeed",
        "relativePositionT",
        "relativePositionN",
        "relativePositionR"
    ]
    datetime_cols = ["creationDate", "publishDate", "tca"]

    for col in float_cols:
        if col in df.columns:
            cast_operations.append(pl.col(col).cast(pl.Float64, strict=False))

    for col in datetime_cols:
        if col in df.columns:
            cast_operations.append(pl.col(col).str.to_datetime(strict=False))

    if cast_operations:
        df = df.with_columns(cast_operations)

    return df
