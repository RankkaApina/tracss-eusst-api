########################################
# CDM / OCM BULK DATA
########################################

#---------------------------------------
# Import Modules
#---------------------------------------

# Standard Library
import os
import sys
import time
import json
import itertools
import threading
import glob
import random
import logging

from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

import datetime as dt

# External Dependencies
import httpx
import polars as pl

# Internal relative imports
from utils.api_helpers import *
from utils.tracss.config import *
from utils.ap_logs import get_logger

#---------------------------------------
# Configure Logger
#---------------------------------------

logger = get_logger()

#---------------------------------------
# CLASS bulkDownloader
#---------------------------------------


class bulkDownloader:

    def __init__(self, datatype: str = 'cdm'):
        self.stop_event = threading.Event()
        self.total_objects_downloaded = 0
        self.failed_pages = set()
        self._page_lock = threading.Lock()
        self._count_lock = threading.Lock()
        self._failed_lock = threading.Lock()
        self.start_time = time.time()
        self._current_page = 0

        self.endpoint = datatype

        if self.endpoint == 'ocm':
            self.bulk_url = TRACSS_BULK_OCM_URL
            self.version_marker = '"CCSDS_OCM_VERS"'
            self.page_size = TRACSS_OCM_PAGE_SIZE
            self.max_workers = TRACSS_OCM_MAX_WORKERS
        else:
            self.bulk_url = TRACSS_BULK_CDM_URL
            self.version_marker = '"TRACSS_CDM_VERS"'
            self.page_size = TRACSS_CDM_PAGE_SIZE
            self.max_workers = TRACSS_CDM_MAX_WORKERS

        self.raw_path = TRACSS_RAW_DATA

    def _already_downloaded(self, output_dir: str, page: int) -> bool:
        """Return True if a non-empty .raw file already exists for this page."""
        filename = f"{self.endpoint}_page_{page:05d}.raw"
        file_path = os.path.join(output_dir, filename)
        return os.path.isfile(file_path) and os.path.getsize(file_path) > 0

    def _next_page(self, output_dir: str) -> int:
        """
        Atomically get the next page number
        """
        with self._page_lock:
            # Then skip any already-downloaded pages
            while self._already_downloaded(output_dir, self._current_page):
                logger.info(
                    f"Skipping already-downloaded page {self._current_page}"
                )
                self._current_page += 1
            page = self._current_page
            self._current_page += 1
        return page

    def _fetch_page(
        self, client, output_dir, query_params, page, max_retries=3
    ):
        page_start = time.time()  
        
        # Fast-exit if another thread already hit end-of-data
        if self.stop_event.is_set():
            return

        params = {
            "size": self.page_size,
            "page": page,
            "format": "JSON"
        }
        params = params | query_params

        for attempt in range(1, max_retries + 1):
            try:
                response = client.get(self.bulk_url, params=params)

                if response.status_code == 503:
                    retry_after = response.headers.get("Retry-After")
                    wait = float(
                        retry_after
                    ) if retry_after else (2**attempt) + random.uniform(0, 1)
                    logger.warning(
                        f"[503 Service Unavailable] Page {page}, attempt {attempt} — backing off {wait:.1f}s"
                    )
                    time.sleep(wait)
                    continue  # Go to next attempt directly, skip the raise

                if response.status_code != 200:
                    raise httpx.HTTPStatusError(
                        f"Bad status code {response.status_code}",
                        request=response.request,
                        response=response
                    )

                if not response.text.strip():
                    batch_count = 0
                else:
                    batch_count = response.text.count(self.version_marker)

                # Genuine end-of-data: signal all threads to stop
                if batch_count == 0:
                    self.stop_event.set()
                    return

                filename = f"{self.endpoint}_page_{page:05d}.raw"
                file_path = os.path.join(output_dir, filename)

                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(response.text)

                with self._count_lock:
                    self.total_objects_downloaded += batch_count

                total_elapsed = time.time() - self.start_time
                elapsed = time.time() - page_start
                logger.info(
                    f"Page {page}: {batch_count:,} objects | Time: {elapsed:.1f}s\n"
                    f"\tProgress: {self.total_objects_downloaded:,} Total  | Time: {total_elapsed:.1f}s"
                )

                with self._failed_lock:
                    self.failed_pages.discard(page)
                return

            except Exception as e:
                logger.warning(
                    f"[Attempt {attempt}/{max_retries}] Thread issue on page {page}: {e}"
                )
                if attempt < max_retries:
                    time.sleep(2 * attempt)
                else:
                    logger.error(
                        f"[Final Error] Page {page} failed permanently after {max_retries} attempts."
                    )
                    with self._failed_lock:
                        self.failed_pages.add(page)

    def download_chunk(
        self,
        output_dir: str,
        token: str,
        query_params: dict = None,
        page: int = None,
    ):
        headers = {
            "Authorization": f"Bearer {token}"
        }

        with httpx.Client(
                timeout=60.0,
                http2=True,
                headers=headers,
        ) as client:

            # Single-page mode: used for targeted retries
            if page is not None:
                self._fetch_page(client, output_dir, query_params, page)
                return

            # Continuous mode: each worker pulls the next available page
            while not self.stop_event.is_set():
                next_pg = self._next_page(output_dir)
                self._fetch_page(client, output_dir, query_params, next_pg)

    def run(
        self,
        folder: str,
        query_params: dict = None,
        skip_pages: int = 0,
        retry_pages: list = None,
    ):
        """
        Parameters
        ----------
        folder : str
            Subfolder under TRACSS_RAW_DATA for output files.
        query_params : dict, optional
            Extra query parameters forwarded to every API request.
        skip_pages : int, optional
            Resume offset — skip all pages below this number.
            Example: skip_pages=6 resumes from page 6 onward.
            Pages that already have a .raw file on disk are also
            skipped automatically regardless of this value.
        retry_pages : list[int], optional
            Explicit list of page numbers to (re)fetch, ignoring
            the normal sequential flow entirely.
            Example: retry_pages=[14] re-pulls only page 14.
        """
        logger.info(
            f"Starting bulk {self.endpoint.upper()} pull from {self.bulk_url}"
        )

        self._current_page = skip_pages
        if skip_pages:
            logger.info(
                f"Resuming from page {skip_pages} (skipping 0–{skip_pages - 1})"
            )
        if retry_pages:
            logger.info(f"Targeted retry mode — pages: {sorted(retry_pages)}")

        output_dir = os.path.join(self.raw_path, folder)
        os.makedirs(output_dir, exist_ok=True)

        token = get_token("tracss")

        # ── Targeted retry mode ──────────────────────────────────────────────
        # Re-fetch only the explicitly specified pages; skip normal bulk flow.
        if retry_pages:
            for page in sorted(retry_pages):
                self.download_chunk(output_dir, token, query_params, page=page)
            total_time = time.time() - self.start_time
            logger.info(
                f"{self.endpoint.upper()} Targeted retry complete in {total_time:.2f}s"
            )
            if self.failed_pages:
                logger.error(f"[!] Still failing: {sorted(self.failed_pages)}")
            return

        # ── Normal bulk download ─────────────────────────────────────────────
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = [
                executor.submit(
                    self.download_chunk,
                    output_dir,
                    token,
                    query_params,
                    None,
                ) for _ in range(self.max_workers)
            ]
            for i, f in enumerate(futures):
                try:
                    f.result()
                except Exception as e:
                    logger.info(
                        f"[Future error] Worker {i}: {type(e).__name__}: {e}"
                    )

        # ── Final cleanup for any persistently failed pages ──────────────────
        if self.failed_pages:
            logger.info(
                f"Retrying {len(self.failed_pages)} failed pages: {sorted(self.failed_pages)}"
            )
            for page in sorted(list(self.failed_pages)):
                self.download_chunk(output_dir, token, query_params, page=page)

        total_time = time.time() - self.start_time
        logger.info(f"{self.endpoint.upper()} Download Complete!")
        logger.info(
            f"Final Count: {self.total_objects_downloaded:,} objects in {total_time:.2f}s"
        )
        if self.failed_pages:
            logger.error(
                f"[!] Warning: The following pages failed permanently: {sorted(self.failed_pages)}"
            )


#---------------------------------------
# CLASS bulkTransformer
#---------------------------------------


class bulkTransformer:

    def __init__(self, datatype: str = 'cdm'):
        self.endpoint = datatype
        self.raw_path = TRACSS_RAW_DATA

    def _read_concatenated_json(self, filepath: str) -> list:
        """Parse a .raw file containing one or more concatenated JSON objects."""
        results = []
        decoder = json.JSONDecoder()
        with open(filepath, 'r', encoding='utf-8') as f:
            text = f.read().strip()
        pos = 0
        while pos < len(text):
            try:
                obj, end_pos = decoder.raw_decode(text, pos)
                results.append(obj)
                pos = end_pos
                while pos < len(text) and text[pos] in ' \t\n\r':
                    pos += 1
            except json.JSONDecodeError as e:
                logger.info(
                    f"[!] JSON decode error in {filepath} at pos {pos}: {e}"
                )
                break
        return results

    def _parse_file(self, filepath: str) -> pl.DataFrame:
        """Read a single .raw file and return a Polars DataFrame."""
        records = self._read_concatenated_json(filepath)
        logger.info(
            f"    {os.path.basename(filepath)}: {len(records):,} records"
        )
        if not records:
            return None
        return pl.DataFrame(records)

    def run(self, folder: str, fmt: str = "csv", max_workers: int = 4):
        """
        Parameters
        ----------
        folder : str
            Subfolder under TRACSS_RAW_DATA containing .raw files.
        fmt : str
            Output format — "csv", "json", or "all".
        max_workers : int
            Threads used to parse .raw files in parallel.
            Tune based on file size; I/O-bound so 4–8 is usually fine.
        """
        input_dir = os.path.join(self.raw_path, folder)
        files = sorted(
            glob.glob(os.path.join(input_dir, f"{self.endpoint}_*.raw"))
        )

        if not files:
            logger.warning(f"No files found in {input_dir}")
            return

        logger.info(
            f"Reading {len(files)} files from {input_dir} using {max_workers} threads"
        )

        # Parse files in parallel
        frames = []
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_file = {
                executor.submit(self._parse_file, f): f
                for f in files
            }
            for future in as_completed(future_to_file):
                result = future.result()
                if result is not None:
                    frames.append(result)

        if not frames:
            logger.warning("No records parsed — nothing to write.")
            return

        # Concatenate all frames at once (much faster than extending a Python list)
        df = pl.concat(frames, rechunk=True)

        df = df.sort("CREATION_DATE", descending=False)

        logger.info(f"Writing {len(df):,} rows")
        

        if fmt in ("json", "all"):
            json_path = os.path.join(TRACSS_JSON_DATA, f"{folder}.json")
            df.write_json(json_path)
            logger.info(f"Records written to {json_path}")

        if fmt in ("csv", "all"):
            csv_path = os.path.join(TRACSS_CSV_DATA, f"{folder}.csv")
            df.write_csv(csv_path)
            logger.info(f"Records written to {csv_path}")
