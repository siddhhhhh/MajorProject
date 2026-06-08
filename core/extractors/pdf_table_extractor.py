"""
pdf_table_extractor.py
======================
Camelot-based PDF table extraction for ESGLens.

Extracts carbon/emissions data from tabular sections of ESG/sustainability
PDF reports.  The existing text-chunking pipeline misses structured table data
(e.g. Shell and Ørsted returning 0 emissions); this module addresses that gap
by using Camelot's lattice and stream flavors with intelligent page filtering.

Dependencies
------------
    pip install "camelot-py[cv]" opencv-python-headless ghostscript PyMuPDF

Ghostscript must also be installed at OS level and available on PATH.
"""

from __future__ import annotations

import logging
import re
import io
import contextlib
import threading
from pathlib import Path
from typing import Any

import camelot
import fitz  # PyMuPDF
import tempfile
import os

# Silence MuPDF non-fatal warnings (tagged-PDF structure-tree errors etc.).
# Process-wide once set; idempotent if already silenced elsewhere.
try:
    fitz.TOOLS.mupdf_display_errors(False)
    fitz.TOOLS.mupdf_display_warnings(False)
except Exception:
    pass

logger = logging.getLogger(__name__)
logging.getLogger("pypdf").setLevel(logging.ERROR)

# ---------------------------------------------------------------------------
# Carbon / emissions keywords used for page & table filtering
# ---------------------------------------------------------------------------
CARBON_KEYWORDS: list[str] = [
    "scope 1", "scope 2", "scope 3",
    "scope1", "scope2", "scope3",
    "direct emissions", "indirect emissions",
    "ghg emissions", "greenhouse gas emissions",
    "tco2e", "mtco2e", "ktco2e", "co2e",
]

_KEYWORD_PATTERN: re.Pattern = re.compile(
    "|".join(re.escape(kw) for kw in CARBON_KEYWORDS),
    re.IGNORECASE,
)

# Regex helpers for numeric emission value parsing
_SCOPE_PATTERN = re.compile(
    r"scope\s*([123])(?:[^\d\n]{1,50}?)([\d,]+(?:\.\d+)?)\b",
    re.IGNORECASE,
)
_UNIT_PATTERN = re.compile(
    r"(mt\s?co2e?|ktco2e?|tco2e?|million\s?t(?:onnes?)?\s?co2e?)",
    re.IGNORECASE,
)
_YEAR_PATTERN = re.compile(r"\b(20[12]\d)\b")
_PDF_NOISE_LOCK = threading.Lock()


# ===================================================================
# Private helpers
# ===================================================================

@contextlib.contextmanager
def _suppress_native_pdf_noise():
    """Silence native Ghostscript/Camelot output emitted below Python stderr."""
    devnull = None
    saved_stdout = None
    saved_stderr = None
    with _PDF_NOISE_LOCK:
        try:
            devnull = os.open(os.devnull, os.O_WRONLY)
            saved_stdout = os.dup(1)
            saved_stderr = os.dup(2)
            os.dup2(devnull, 1)
            os.dup2(devnull, 2)
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                yield
        finally:
            if saved_stdout is not None:
                os.dup2(saved_stdout, 1)
                os.close(saved_stdout)
            if saved_stderr is not None:
                os.dup2(saved_stderr, 2)
                os.close(saved_stderr)
            if devnull is not None:
                os.close(devnull)

def _find_carbon_pages(pdf_path: str) -> list[int]:
    """Fast-scan PDF pages with PyMuPDF and return 1-indexed page numbers
    that contain at least one carbon/emissions keyword.

    This avoids running Camelot on every page of a 200-page report,
    dramatically reducing runtime.

    Parameters
    ----------
    pdf_path : str
        Absolute or relative path to the PDF file.

    Returns
    -------
    list[int]
        Sorted list of 1-indexed page numbers with carbon content.
    """
    carbon_pages: list[int] = []
    try:
        doc = fitz.open(pdf_path)
        for page_num in range(len(doc)):
            page_text = doc[page_num].get_text("text") or ""
            if _KEYWORD_PATTERN.search(page_text):
                carbon_pages.append(page_num + 1)  # Camelot uses 1-indexed
        doc.close()
        logger.info(
            "PyMuPDF scan: %d carbon-relevant page(s) found in %s",
            len(carbon_pages), pdf_path,
        )
    except Exception:
        logger.exception("PyMuPDF page scan failed for %s", pdf_path)
    return carbon_pages


def _table_has_carbon_data(table: Any) -> bool:
    """Check whether a Camelot Table object contains carbon/emissions keywords.

    Parameters
    ----------
    table : camelot.core.Table
        A single table extracted by Camelot.

    Returns
    -------
    bool
        True if the table's text matches at least one carbon keyword.
    """
    try:
        df = table.df
        text_blob = " ".join(
            str(cell) for row in df.values for cell in row
        )
        return bool(_KEYWORD_PATTERN.search(text_blob))
    except Exception:
        logger.exception("Error inspecting table for carbon keywords")
        return False

def _sanitize_pdf_for_extraction(pdf_path: str) -> str:
    """Remove form/widget annotations that make Ghostscript noisy or brittle."""
    doc = None
    try:
        doc = fitz.open(pdf_path)
        removed = 0

        for page in doc:
            for widget in list(page.widgets() or []):
                try:
                    page.delete_widget(widget)
                    removed += 1
                except Exception:
                    logger.debug(
                        "Could not delete PDF widget xref=%s on page %s",
                        getattr(widget, "xref", "?"),
                        page.number + 1,
                        exc_info=True,
                    )

            for annot in list(page.annots() or []):
                try:
                    page.delete_annot(annot)
                    removed += 1
                except Exception:
                    logger.debug(
                        "Could not delete PDF annotation xref=%s on page %s",
                        getattr(annot, "xref", "?"),
                        page.number + 1,
                        exc_info=True,
                    )

            # Some malformed PDFs expose broken widgets only through the raw
            # page dictionary. Removing /Annots prevents Ghostscript from
            # traversing stale widget references.
            try:
                doc.xref_set_key(page.xref, "Annots", "null")
            except Exception:
                logger.debug(
                    "Could not clear /Annots for page %s", page.number + 1,
                    exc_info=True,
                )

        try:
            catalog_xref = doc.pdf_catalog()
            if catalog_xref:
                doc.xref_set_key(catalog_xref, "AcroForm", "null")
        except Exception:
            logger.debug("Could not clear PDF /AcroForm catalog entry", exc_info=True)

        fd, temp_path = tempfile.mkstemp(suffix=".pdf", prefix="sanitized_")
        os.close(fd)

        # garbage=4 and clean=True rewrite cross-reference tables and drop
        # unreferenced widget objects left behind by the source PDF.
        doc.save(temp_path, garbage=4, clean=True, deflate=True)
        doc.close()
        logger.debug("Sanitized %s for table extraction; removed %d annotations/widgets.", pdf_path, removed)
        return temp_path
    except Exception as e:
        logger.warning("PDF sanitization failed, proceeding with original: %s", e)
        return pdf_path
    finally:
        if doc is not None:
            try:
                doc.close()
            except Exception:
                pass


# ===================================================================
# Public API
# ===================================================================

def extract_carbon_tables(pdf_path: str) -> list[dict]:
    """Extract tables containing carbon/emissions data from a PDF.

    Strategy:
        1. Use PyMuPDF to identify pages with carbon keywords.
        2. For each relevant page, try Camelot **lattice** flavor first
           (works best for bordered tables).
        3. Fall back to **stream** flavor if lattice finds nothing.
        4. Filter results to only tables that contain carbon keywords.

    Parameters
    ----------
    pdf_path : str
        Path to the PDF file.

    Returns
    -------
    list[dict]
        Each dict has keys:
        - ``page``      : int — 1-indexed page number
        - ``flavor``    : str — "lattice" or "stream"
        - ``accuracy``  : float — Camelot's parsing accuracy score
        - ``dataframe`` : pandas.DataFrame — the table data
        - ``raw_text``  : str — flattened cell text for downstream regex
    """
    original_pdf_path_str = str(Path(pdf_path).resolve())
    carbon_pages = _find_carbon_pages(original_pdf_path_str)

    if not carbon_pages:
        logger.warning(
            "No carbon-relevant pages found in %s — returning empty.",
            original_pdf_path_str,
        )
        return []
        
    pdf_path_str = _sanitize_pdf_for_extraction(original_pdf_path_str)

    pages_str = ",".join(str(p) for p in carbon_pages)
    results: list[dict] = []

    # Fast-fail: if the PDF's structure is broken (NullObject etc) and the
    # first N pages all error with no extracted tables, abort the rest of
    # the pages for this PDF — they will fail the same way. Without this,
    # a 90-page broken PDF burns ~10 minutes producing nothing.
    _consecutive_failures = 0
    _MAX_CONSECUTIVE_FAILURES = 3

    for page_num in carbon_pages:
        page_str = str(page_num)
        tables_found = False
        temp_write_blocked = False
        _page_had_any_success = False  # track whether either flavor produced data

        # --- Attempt 1: lattice ---
        try:
            with _suppress_native_pdf_noise():
                tables = camelot.read_pdf(
                    pdf_path_str,
                    pages=page_str,
                    flavor="lattice",
                    suppress_stdout=True,
                )
            for tbl in tables:
                if _table_has_carbon_data(tbl):
                    raw = " ".join(
                        str(c) for row in tbl.df.values for c in row
                    )
                    results.append({
                        "page": page_num,
                        "flavor": "lattice",
                        "accuracy": round(tbl.accuracy, 2),
                        "dataframe": tbl.df,
                        "raw_text": raw,
                    })
                    tables_found = True
            if tables_found:
                _page_had_any_success = True
                _consecutive_failures = 0
                logger.debug(
                    "Page %d: %d carbon table(s) via lattice",
                    page_num, sum(1 for r in results if r["page"] == page_num),
                )
                continue  # skip stream if lattice worked
        except PermissionError:
            temp_write_blocked = True
            logger.exception(
                "Camelot temp-file write failed on page %d of %s; aborting further table extraction for this PDF",
                page_num, pdf_path_str,
            )
        except Exception as e:
            if "Ghostscript" in str(e):
                logger.debug("Skipping lattice extraction because Ghostscript is not installed.")
            else:
                logger.warning(
                    "Lattice extraction failed on page %d of %s: %s",
                    page_num, pdf_path_str, str(e),
                )

        if temp_write_blocked:
            break

        # --- Attempt 2: stream fallback ---
        try:
            with _suppress_native_pdf_noise():
                tables = camelot.read_pdf(
                    pdf_path_str,
                    pages=page_str,
                    flavor="stream",
                    suppress_stdout=True,
                )
            for tbl in tables:
                if _table_has_carbon_data(tbl):
                    raw = " ".join(
                        str(c) for row in tbl.df.values for c in row
                    )
                    results.append({
                        "page": page_num,
                        "flavor": "stream",
                        "accuracy": round(tbl.accuracy, 2),
                        "dataframe": tbl.df,
                        "raw_text": raw,
                    })
            if any(r["page"] == page_num and r["flavor"] == "stream" for r in results):
                _page_had_any_success = True
                logger.debug(
                    "Page %d: carbon table(s) found via stream",
                    page_num
                )
            logger.info(
                "Page %d: %d carbon table(s) via stream",
                page_num,
                sum(1 for r in results if r["page"] == page_num and r["flavor"] == "stream"),
            )
        except PermissionError:
            logger.exception(
                "Camelot temp-file write failed on page %d of %s; aborting further table extraction for this PDF",
                page_num, pdf_path_str,
            )
            break
        except Exception as e:
            if "Ghostscript" in str(e):
                logger.debug("Skipping stream extraction because Ghostscript is not installed.")
            else:
                logger.warning(
                    "Stream extraction failed on page %d of %s: %s",
                    page_num, pdf_path_str, str(e),
                )

        # Track consecutive failures and bail out of this PDF early.
        if _page_had_any_success:
            _consecutive_failures = 0
        else:
            _consecutive_failures += 1
            if _consecutive_failures >= _MAX_CONSECUTIVE_FAILURES:
                logger.warning(
                    "Aborting table extraction for %s after %d consecutive "
                    "page failures (likely structural PDF error like NullObject); "
                    "fitz-extracted text from this PDF is still available.",
                    pdf_path_str, _consecutive_failures,
                )
                break

    logger.info(
        "Total carbon tables extracted from %s: %d", original_pdf_path_str, len(results),
    )
    
    if pdf_path_str != original_pdf_path_str:
        try:
            os.remove(pdf_path_str)
        except Exception:
            pass
            
    return results


def extract_emissions_values(pdf_path: str) -> dict:
    """High-level function: extract and parse carbon emissions values from a PDF.

    Calls :func:`extract_carbon_tables` and applies regex to locate
    Scope 1 / 2 / 3 numeric values, the reporting unit, and the year.

    Parameters
    ----------
    pdf_path : str
        Path to the PDF file.

    Returns
    -------
    dict
        Keys:
        - ``scope1``       : float | None
        - ``scope2``       : float | None
        - ``scope3``       : float | None
        - ``unit``         : str | None  (e.g. "tCO2e", "MtCO2e")
        - ``year``         : int | None
        - ``tables_found`` : int
        - ``source``       : str  ("camelot_pdf_table_extractor")
        - ``raw_matches``  : list[dict]  — every scope match for audit
    """
    result: dict = {
        "scope1": None,
        "scope2": None,
        "scope3": None,
        "unit": None,
        "year": None,
        "tables_found": 0,
        "source": "camelot_pdf_table_extractor",
        "raw_matches": [],
    }

    # Page-count guard: Camelot iterates per-page with lattice + stream
    # flavors; large PDFs (Reliance's 146-page sustainability report) can
    # OOM-kill the Python process at the C extension level — no Python
    # exception, just a vanishing process. We skip any PDF with more than
    # 100 pages to keep the pipeline durable. The chunk-based extractor
    # still gets to scan the full document.
    try:
        import fitz  # PyMuPDF
        with fitz.open(pdf_path) as _doc:
            _page_count = _doc.page_count
        if _page_count > 100:
            logger.info(
                "Skipping Camelot extraction for %s: %d pages exceeds 100-page guard.",
                pdf_path, _page_count,
            )
            return result
    except Exception:
        # If page-count check fails we still attempt extraction — better
        # to risk a crash than silently skip every PDF.
        pass

    try:
        tables = extract_carbon_tables(pdf_path)
    except Exception:
        logger.exception("extract_carbon_tables raised for %s", pdf_path)
        return result

    result["tables_found"] = len(tables)

    # Merge all raw_text blobs for regex scanning
    all_text = "\n".join(t["raw_text"] for t in tables)

    # --- Parse scope values ---
    for match in _SCOPE_PATTERN.finditer(all_text):
        scope_num = match.group(1)  # "1", "2", or "3"
        value_str = match.group(2).replace(",", "")
        try:
            value = float(value_str)
        except ValueError:
            continue

        key = f"scope{scope_num}"
        result["raw_matches"].append({
            "scope": int(scope_num),
            "value": value,
            "matched_text": match.group(0),
        })

        # Keep the first (usually most prominent) value per scope
        if result[key] is None:
            result[key] = value

    # --- Parse unit ---
    unit_match = _UNIT_PATTERN.search(all_text)
    if unit_match:
        result["unit"] = unit_match.group(1).strip()

    # --- Parse year ---
    year_match = _YEAR_PATTERN.search(all_text)
    if year_match:
        result["year"] = int(year_match.group(1))

    logger.info(
        "Emissions extraction from %s: scope1=%s, scope2=%s, scope3=%s, "
        "unit=%s, year=%s, tables=%d",
        pdf_path, result["scope1"], result["scope2"], result["scope3"],
        result["unit"], result["year"], result["tables_found"],
    )
    return result
