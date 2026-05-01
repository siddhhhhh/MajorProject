"""
Governance Pillar Agent
Focused retrieval and scoring for board quality, pay alignment, and legal signals.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
import re

import requests
from bs4 import BeautifulSoup

from utils.free_data_sources import search_duckduckgo
from utils.web_search import RealTimeDataFetcher
from core.sg_evidence import build_sg_evidence_pack


class GovernanceAgent:
    def __init__(self) -> None:
        self.name = "Governance Pillar Forensic Agent"
        self.fetcher = RealTimeDataFetcher()
        self.user_agent = "ESGLens/1.0 (research@esglens.local)"

    def analyze(
        self,
        company: str,
        claim_text: str,
        industry: str,
        evidence: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        claim_text = str(claim_text or "")
        evidence_text = self._collect_text(evidence)
        combined_text = f"{claim_text}\n{evidence_text}".lower()

        sec_proxy = self._parse_sec_proxy_filings(company)
        # Non-US fallback: when the SEC EDGAR path returns no proxy filings
        # (foreign listing, ADR, no DEF 14A obligation), fetch the same
        # board/comp/whistleblower/ethics signals directly from the annual
        # report or governance pages already present in the evidence pool.
        # Without this, companies like Volkswagen (DE — supervisory board
        # publicly disclosed) showed "no relevant disclosure in retrieved
        # evidence" even though their Annual Report carries every figure.
        if not sec_proxy.get("filings"):
            non_us = self._fetch_governance_from_evidence_urls(company, evidence)
            if non_us.get("filings"):
                sec_proxy = non_us
        board = self._extract_board_signals(combined_text, sec_proxy)
        comp = self._extract_compensation_signals(combined_text, sec_proxy)
        audit = self._extract_audit_signals(combined_text)
        legal = self._extract_regulatory_legal_signals(company, combined_text)
        rights = self._extract_shareholder_rights(combined_text)
        tax = self._extract_tax_transparency(combined_text)
        whistleblower = self._extract_whistleblower_signals(combined_text)

        score = 58.0
        findings: List[str] = []
        red_flags: List[str] = []

        if board.get("board_independence_pct") is not None and board["board_independence_pct"] < 40:
            score = min(score, 45.0)
            red_flags.append("Board independence below 40%: automatic governance weakness flag.")

        if board.get("board_gender_pct") is not None and board["board_gender_pct"] < 30:
            score -= 8
            findings.append("Board gender diversity below 30% threshold.")

        if board.get("max_director_tenure_years") is not None and board["max_director_tenure_years"] > 12:
            score -= 6
            findings.append("Director tenure above 12 years may weaken independence.")

        if board.get("max_interlocks") is not None and board["max_interlocks"] > 4:
            score -= 6
            findings.append("Director interlock count above 4 boards flagged.")

        if comp.get("ceo_worker_pay_ratio") is not None and comp["ceo_worker_pay_ratio"] > 300:
            score -= 8
            findings.append("CEO/worker pay ratio exceeds 300x industry alert threshold.")

        esg_claim = any(term in claim_text.lower() for term in ["esg", "sustainab", "ethical", "responsible"])
        if esg_claim and comp.get("lti_esg_pct") == 0:
            score = min(score, 35.0)
            red_flags.append("ESG claim + 0% LTI tied to ESG: contradiction.")

        if "ethical culture" in claim_text.lower() and legal.get("regulatory_fine_signals", 0) > 0:
            score = min(score, 35.0)
            red_flags.append("Ethical culture claim conflicts with regulatory fine signals.")

        if rights.get("dual_class_structure"):
            score -= 6
        if rights.get("poison_pill"):
            score -= 5
        if rights.get("staggered_board"):
            score -= 5

        if tax.get("effective_tax_rate_delta_pct") is not None and tax["effective_tax_rate_delta_pct"] > 10:
            score -= 6
            findings.append("Effective tax rate delta above 10% raises tax transparency concern.")

        if not whistleblower.get("independent_hotline_disclosed"):
            score -= 5
            findings.append("Independent whistleblower hotline not clearly disclosed.")

        if audit.get("all_audit_committee_independent") is True:
            score += 4

        score = round(max(0.0, min(100.0, score)), 1)
        risk_level = self._risk_level(score)
        confidence = 0.66 + min(0.24, len(sec_proxy.get("filings", [])) * 0.04)

        coverage_indicators = sum([
            1 if (board.get("board_independence_pct") is not None or board.get("board_gender_pct") is not None) else 0,
            1 if (comp.get("ceo_worker_pay_ratio") is not None or comp.get("lti_esg_pct") is not None) else 0,
            1 if (audit.get("big4_auditor_mentioned") or audit.get("all_audit_committee_independent")) else 0,
            1 if (tax.get("statutory_tax_rate_pct") is not None or tax.get("effective_tax_rate_pct") is not None) else 0,
            1 if whistleblower.get("independent_hotline_disclosed") else 0,
            1 if any(rights.values()) else 0,
        ])

        if coverage_indicators < 3:
            score = None
            risk_level = "UNKNOWN"
            status = "insufficient_data"
            findings.insert(0, f"Insufficient data: only {coverage_indicators}/6 governance themes detected. Pillar excluded from composite scoring.")
        else:
            status = "success"

        sources = []
        sources.extend(sec_proxy.get("sources", []))
        sources.extend(legal.get("sources", []))

        if status == "insufficient_data":
            confidence = 0.1
        governance_lane = build_sg_evidence_pack(evidence=evidence, claim_text=claim_text).get("pillars", {}).get("governance", {})

        return {
            "company": company,
            "industry": industry,
            "governance_score": score,
            "status": status,
            "risk_level": risk_level,
            "confidence": round(min(0.9, confidence), 2),
            "signals": {
                "sec_proxy_parser": sec_proxy,
                "board": board,
                "executive_compensation": comp,
                "audit_quality": audit,
                "regulatory_legal": legal,
                "shareholder_rights": rights,
                "tax_transparency": tax,
                "whistleblower": whistleblower,
            },
            "rule_flags": {
                "board_independence_below_40": bool(board.get("board_independence_pct") is not None and board.get("board_independence_pct") < 40),
                "esg_claim_with_zero_lti": bool(esg_claim and comp.get("lti_esg_pct") == 0),
                "ethical_claim_with_fines": bool("ethical culture" in claim_text.lower() and legal.get("regulatory_fine_signals", 0) > 0),
            },
            "red_flags": red_flags,
            "key_findings": findings,
            "evidence_sources": sources[:15],
            "extraction_tracks": governance_lane.get("tracks", []),
            "evidence_lane": governance_lane,
            "timestamp": datetime.now().isoformat(),
        }

    def _collect_text(self, evidence: List[Dict[str, Any]]) -> str:
        parts: List[str] = []
        for ev in evidence or []:
            if not isinstance(ev, dict):
                continue
            parts.append(str(ev.get("title", "")))
            parts.append(str(ev.get("snippet", "")))
            parts.append(str(ev.get("relevant_text", "")))
            parts.append(str(ev.get("source", "")))
            parts.append(str(ev.get("source_type", "")))
        return " ".join(parts)

    def _parse_sec_proxy_filings(self, company: str) -> Dict[str, Any]:
        # Two-pass strategy:
        #   1. Direct DEF 14A query against SEC EDGAR (type=DEF+14A) — much
        #      more reliable than filtering the generic "all filings" feed.
        #      The previous code was looking through 12 mixed-type results
        #      and frequently never saw a DEF 14A even for companies that
        #      file one every year (Microsoft, JPM, Tesla all on EDGAR).
        #   2. Fall back to the generic feed for non-US-listed companies.
        filings = self._fetch_def14a_filings_direct(company) or self.fetcher.get_sec_filings_realtime(company)
        proxy_filings = []
        sources: List[Dict[str, Any]] = []

        for row in (filings or [])[:12]:
            if not isinstance(row, dict):
                continue
            title = str(row.get("title", ""))
            form_type = str(row.get("form_type", ""))
            snippet = str(row.get("snippet", ""))
            hay = f"{title} {form_type} {snippet}".upper()
            if "DEF 14A" not in hay and "DEFA14A" not in hay and "PROXY" not in hay:
                continue

            parsed = self._extract_proxy_metrics_from_url(row.get("url", ""))
            proxy_filings.append({
                "title": title,
                "url": row.get("url", ""),
                "form_type": form_type,
                "parsed_metrics": parsed,
            })
            sources.append(
                {
                    "title": title,
                    "url": row.get("url", ""),
                    "source": "SEC EDGAR proxy parser",
                }
            )

            if len(proxy_filings) >= 3:
                break

        return {
            "filings": proxy_filings,
            "filings_count": len(proxy_filings),
            "sources": sources,
        }

    def _fetch_governance_from_evidence_urls(
        self, company: str, evidence: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Non-US fallback: extract board signals directly from annual-report
        and governance pages already in the evidence pool.

        For non-US issuers (VW, BMW, Daimler, Total, Shell, BP, Reliance…)
        the SEC EDGAR DEF 14A path returns nothing, and the regex over
        evidence snippets sees only fragmentary text. The fix is to fetch
        the actual annual-report / governance HTML the evidence retriever
        already discovered — and follow the in-page links to specific
        supervisory-board / remuneration / corporate-governance subpages
        — then run the same metrics extraction pipeline.

        Heuristic: any URL whose domain or path contains tokens that
        identify a governance disclosure surface (annual report, IR site,
        governance page, supervisory board page). For root annual-report
        URLs, harvest in-page links pointing at governance sub-pages.
        """
        if not isinstance(evidence, list) or not evidence:
            return {"filings": [], "filings_count": 0, "sources": []}

        # Prioritisation tokens — earlier = stronger candidate
        priority_tokens = (
            "supervisory-board", "supervisory_board",
            "board-of-directors", "board_of_directors",
            "corporate-governance", "corporate_governance",
            "governance",
            "annual-report", "annualreport", "annual_report",
            "investor", "investors", "ir.",
            "proxy-statement", "proxy_statement",
            "remuneration", "compensation",
        )

        # Sub-page link tokens to follow from a root annual-report page.
        # German two-tier issuers split governance disclosure across many
        # pages (supervisory-board.html, remuneration-report/*, members-of-
        # the-supervisory-board-and-committees.html, fuehrungspositionen-
        # gesetz quota disclosure). The root page rarely carries the actual
        # numbers — they live one click in.
        followable_tokens = (
            "supervisory-board",
            "members-of-the-supervisory-board",
            "members-of-the-board-of-management",
            "board-of-management",
            "remuneration-report",
            "remuneration",
            "corporate-governance",
            "compensation",
            "composition-of-the-supervisory-board",
            # German FüPoG II quota disclosure pages — that's where the
            # women-on-board % is actually published.
            "fuehrungspositionen-gesetz",
            "fuepog",
            "diversity",
            "board-diversity",
            "women-in-leadership",
            "declaration-of-conformity",
            "corporate-governance-declaration",
        )

        candidates: List[tuple] = []  # (priority_score, url, title, followable)
        seen_urls: set = set()
        for ev in evidence:
            if not isinstance(ev, dict):
                continue
            url = str(ev.get("url") or ev.get("source_url") or "").strip()
            if not url or url in seen_urls:
                continue
            url_l = url.lower()
            score = 0
            for i, tok in enumerate(priority_tokens):
                if tok in url_l:
                    score += max(1, len(priority_tokens) - i)
                    break
            if score == 0:
                continue
            seen_urls.add(url)
            title = str(ev.get("title") or "")
            # Mark root annual-report URLs as "followable" — i.e. we should
            # also harvest governance subpage links from their HTML.
            is_root_ar = any(t in url_l for t in ("annualreport", "annual-report", "annual_report"))
            candidates.append((score, url, title, is_root_ar))

        candidates.sort(key=lambda row: row[0], reverse=True)
        candidates = candidates[:6]

        # Stage 1: harvest follow-up URLs from root annual-report pages
        # that haven't been linked directly. We rewrite relative paths into
        # absolute URLs against the parent's base.
        from urllib.parse import urljoin
        # Highest-value sub-page tokens — FüPoG / composition / supervisory
        # board pages typically carry the actual quota numbers, while the
        # generic "report-of-the-supervisory-board" landing page just has
        # narrative meeting minutes. Rank harvested URLs so the high-value
        # ones get fetched first within our budget.
        priority_followups = (
            "fuehrungspositionen-gesetz",
            "fuepog",
            "composition-of-the-supervisory-board",
            "supervisory-board.html",  # canonical CG declaration page
            "remuneration-report",
            "members-of-the-supervisory-board",
            "members-of-the-board-of-management",
            "board-of-management",
            "diversity",
            "declaration-of-conformity",
            "corporate-governance-declaration",
            "remuneration",
            "compensation",
            "corporate-governance",
            "supervisory-board",
        )

        followups: List[tuple] = []  # (priority, url, title)
        for score, url, title, is_root_ar in candidates:
            if not is_root_ar:
                continue
            try:
                resp = requests.get(url, timeout=12, headers={"User-Agent": self.user_agent})
                if resp.status_code != 200:
                    continue
                hrefs = re.findall(r'href="([^"#?]+)"', resp.text)
            except Exception:
                continue
            for href in hrefs:
                href_l = href.lower()
                if not any(t in href_l for t in followable_tokens):
                    continue
                if not any(href_l.endswith(suffix) for suffix in (".html", ".htm", "/")) and "?" not in href_l:
                    if not href_l.endswith(".html"):
                        continue
                full = urljoin(url, href)
                if full in seen_urls:
                    continue
                seen_urls.add(full)
                # Token-aware priority — rank earlier hits higher.
                tok_priority = 0
                for i, tok in enumerate(priority_followups):
                    if tok in href_l:
                        tok_priority = len(priority_followups) - i
                        break
                followups.append((score + 5 + tok_priority, full, f"governance subpage of {title or url}"))
                if len(followups) >= 25:
                    break
            if len(followups) >= 25:
                break

        # Merge: prefer follow-up subpages first since they're typically
        # where the numbers actually live.
        all_targets = sorted(followups, key=lambda r: r[0], reverse=True) + \
                      [(c[0], c[1], c[2]) for c in candidates]
        # De-dup again (followups + candidates can overlap)
        unique_targets: List[tuple] = []
        seen_2 = set()
        for tup in all_targets:
            if tup[1] in seen_2:
                continue
            seen_2.add(tup[1])
            unique_targets.append(tup)

        proxy_filings: List[Dict[str, Any]] = []
        sources: List[Dict[str, Any]] = []
        # Track whether we've already captured the most informative metrics
        # so we know when to stop crawling sub-pages.
        captured = {"board_independence_pct": False, "board_gender_pct": False, "ceo_worker_pay_ratio": False}
        for score, url, title in unique_targets[:12]:  # fetch budget
            parsed = self._extract_proxy_metrics_from_url(url)
            if not parsed:
                continue
            if not any(v not in (None, False) for v in parsed.values()):
                continue
            proxy_filings.append({
                "title": title or url,
                "url": url,
                "form_type": "annual_report_or_governance_page",
                "parsed_metrics": parsed,
            })
            sources.append({
                "title": title or url,
                "url": url,
                "source": "non-US governance fallback",
            })
            for key in captured:
                if parsed.get(key) is not None and parsed.get(key) is not False:
                    captured[key] = True
            # Stop once we have BOTH board independence AND board gender, or
            # we've collected 5 pages — whichever comes first. Without this
            # the crawler used to stop after 3 boilerplate pages and miss
            # the page with the actual quota figures.
            if (captured["board_independence_pct"] and captured["board_gender_pct"]) or len(proxy_filings) >= 5:
                break

        return {
            "filings": proxy_filings,
            "filings_count": len(proxy_filings),
            "sources": sources,
        }

    def _fetch_def14a_filings_direct(self, company: str) -> List[Dict[str, Any]]:
        """Direct SEC EDGAR query for DEF 14A proxy statements.

        Two-step:
          1. Resolve CIK via SEC's company_tickers JSON (free, no auth).
          2. Fetch DEF 14A filings list via the company_facts/submissions API.

        Returns rows compatible with `get_sec_filings_realtime` so the
        downstream filter loop is unchanged. SEC requires a User-Agent
        header with a contact email per their fair-use policy.
        """
        if not company:
            return []
        try:
            sec_headers = {
                "User-Agent": "ESGLens Research siddh@esglens.example contact",
                "Accept-Encoding": "gzip, deflate",
            }
            # Step 1: Resolve CIK from company name. Cache the lookup table.
            if not hasattr(self, "_sec_ticker_cache"):
                tickers_url = "https://www.sec.gov/files/company_tickers.json"
                try:
                    resp = requests.get(tickers_url, headers=sec_headers, timeout=15)
                    if resp.status_code == 200:
                        self._sec_ticker_cache = resp.json()
                    else:
                        self._sec_ticker_cache = {}
                except Exception:
                    self._sec_ticker_cache = {}

            cik_padded: Optional[str] = None
            company_lower = company.lower().strip()
            company_tokens = [
                t for t in re.split(r"[^a-z0-9]+", company_lower)
                if len(t) >= 4 and t not in {"corp", "inc", "ltd", "plc", "company", "limited"}
            ]
            if not company_tokens:
                short = company_lower.split()[0]
                if 2 <= len(short) <= 4:
                    company_tokens = [short]
            for entry in (self._sec_ticker_cache or {}).values():
                if not isinstance(entry, dict):
                    continue
                title = str(entry.get("title", "")).lower()
                ticker = str(entry.get("ticker", "")).lower()
                if not company_tokens:
                    continue
                if any(tok in title for tok in company_tokens) or ticker in company_tokens:
                    cik = entry.get("cik_str")
                    if cik is not None:
                        cik_padded = str(int(cik)).zfill(10)
                        break
            if not cik_padded:
                return []

            # Step 2: Fetch recent submissions list and filter for DEF 14A.
            sub_url = f"https://data.sec.gov/submissions/CIK{cik_padded}.json"
            sub_resp = requests.get(sub_url, headers=sec_headers, timeout=15)
            if sub_resp.status_code != 200:
                return []
            sub = sub_resp.json()
            recent = (sub.get("filings") or {}).get("recent") or {}
            forms = recent.get("form") or []
            accession_numbers = recent.get("accessionNumber") or []
            primary_documents = recent.get("primaryDocument") or []
            filing_dates = recent.get("filingDate") or []
            # Two-pass: first prioritize DEF 14A (the actual proxy
            # statement with board composition / pay tables), then
            # DEFA14A (amendments) as fallback. DEFA14A filings are
            # typically short supplemental documents that don't carry the
            # structured tables we need to parse — Microsoft's 5 most
            # recent DEFA14As all returned null on board-independence.
            def14a_results: List[Dict[str, Any]] = []
            defa14a_results: List[Dict[str, Any]] = []
            for i, form_type in enumerate(forms):
                form_upper = str(form_type).upper().strip()
                if form_upper not in {"DEF 14A", "DEFA14A"}:
                    continue
                if i >= len(accession_numbers) or i >= len(primary_documents):
                    continue
                accession = str(accession_numbers[i]).replace("-", "")
                doc = primary_documents[i]
                filed = filing_dates[i] if i < len(filing_dates) else ""
                url = (
                    f"https://www.sec.gov/Archives/edgar/data/"
                    f"{int(cik_padded)}/{accession}/{doc}"
                )
                row = {
                    "source": "SEC EDGAR (data.sec.gov)",
                    "url": url,
                    "title": f"{sub.get('name', company)} - {form_type} ({filed})",
                    "snippet": f"Filed: {filed} | Type: {form_type} | CIK: {cik_padded}",
                    "date": filed,
                    "form_type": str(form_type),
                    "data_source": "SEC EDGAR - submissions API",
                }
                if form_upper == "DEF 14A":
                    def14a_results.append(row)
                else:
                    defa14a_results.append(row)
                if len(def14a_results) >= 3:
                    break
            return (def14a_results + defa14a_results)[:5]
        except Exception:
            return []

    def _extract_proxy_metrics_from_url(self, url: str) -> Dict[str, Optional[float]]:
        if not url:
            return {}

        try:
            resp = requests.get(
                url,
                timeout=12,
                headers={"User-Agent": self.user_agent},
            )
            if resp.status_code != 200:
                return {}

            soup = BeautifulSoup(resp.text[:600000], "html.parser")
            text = soup.get_text(" ", strip=True).lower()

            # Board independence — % patterns OR X-of-Y fraction. The
            # X-of-Y form ("11 of our 12 directors are independent") is
            # how Microsoft/JPM proxies usually phrase it; the previous
            # regex captured only the numerator and treated it as a raw
            # percentage (Microsoft scored 11% independent).
            #
            # Two-tier-system patterns also added: German DAX issuers
            # (VW, BMW, Daimler) report a separate Supervisory Board
            # ("Aufsichtsrat") with explicit independence + women-quota
            # disclosures under the German Corporate Governance Code and
            # FüPoG II quota law.
            board_independence_pct = (
                self._first_percent(text, r"(?:board independence|independent directors|independent non-executive directors|independent supervisory board|independent members? of (?:the )?supervisory board)[^\d]{0,40}(\d{1,3}(?:\.\d+)?)\s*%")
                or self._first_percent(text, r"(\d{1,3}(?:\.\d+)?)\s*%\s{0,40}(?:of\s+(?:the\s+)?)?(?:board members|directors|supervisory board members|members of the supervisory board)\s{0,40}(?:are\s+)?independent")
                or self._first_fraction_pct(text, r"(\d{1,2})\s+of\s+(?:our\s+|the\s+)?(\d{1,2})\s+(?:director\s+nominees|directors|board\s+members|nominees|supervisory\s+board\s+members|members\s+of\s+the\s+supervisory\s+board)\s{0,40}(?:are\s+)?independent")
                or self._first_fraction_pct(text, r"(\d{1,2})\s+of\s+(?:the\s+)?(\d{1,2})\s+(?:director\s+nominees|directors|board\s+members|supervisory\s+board\s+members)\s{0,40}qualify\s+as\s+independent")
                or self._first_fraction_pct(text, r"of\s+(?:our|the)\s+(\d{1,2})\s+(?:director\s+nominees|directors|supervisory\s+board\s+members)[^.\n]{0,80}?(\d{1,2})\s+(?:are\s+)?independent")
                # German Corporate Governance Code: "the supervisory board
                # consists of N members, of which K are independent"
                or self._first_fraction_pct(text, r"supervisory\s+board\s+(?:consists?\s+of|comprises?|has)\s+(\d{1,2})\s+members[^.\n]{0,120}?(\d{1,2})\s+(?:are\s+)?(?:considered\s+)?independent")
            )
            # Board gender — bidirectional + X-of-Y fraction handler.
            # Includes EU FüPoG II quota wording ("women's share on the
            # supervisory board", "frauenquote"), broader phrasings, and
            # the German Annual Report convention "X% of the members of
            # the supervisory board are women" (which never says "female"
            # or "directors", so the older patterns missed it).
            board_gender_pct = (
                self._first_percent(text, r"(?:board gender|women on board|female directors|women in the board|gender\s+representation|women['']?s?\s+share\s+(?:on|in)\s+(?:the\s+)?(?:supervisory\s+)?board|female\s+supervisory\s+board\s+members?|frauenquote)[^\d]{0,40}(\d{1,3}(?:\.\d+)?)\s*%")
                or self._first_percent(text, r"(\d{1,3}(?:\.\d+)?)\s*%\s{0,40}(?:of\s+(?:the\s+)?)?(?:directors|board members|nominees|supervisory\s+board\s+members|members\s+of\s+the\s+supervisory\s+board)\s{0,40}(?:are\s+)?(?:women|female)")
                # German FüPoG-style: "in total, 40% of the members of the
                # supervisory board" (the women context is implicit from
                # the surrounding paragraph header).
                or self._first_percent(text, r"(?:in\s+total[, ]+)?(\d{1,3}(?:\.\d+)?)\s*%\s+of\s+the\s+members\s+of\s+the\s+supervisory\s+board")
                or self._first_fraction_pct(text, r"(\d{1,2})\s+of\s+(?:our\s+|the\s+)?(\d{1,2})\s+(?:director\s+nominees|directors|board\s+members|nominees|supervisory\s+board\s+members|members\s+of\s+the\s+supervisory\s+board)\s{0,40}(?:are\s+)?(?:women|female)")
                or self._first_fraction_pct(text, r"of\s+(?:our|the)\s+(\d{1,2})\s+(?:director\s+nominees|directors|supervisory\s+board\s+members)[^.\n]{0,80}?(\d{1,2})\s+(?:are\s+)?(?:women|female)")
                or self._first_fraction_pct(text, r"supervisory\s+board\s+(?:consists?\s+of|comprises?|has)\s+(\d{1,2})\s+members[^.\n]{0,120}?(\d{1,2})\s+(?:are\s+)?(?:women|female)")
            )
            # CEO-to-worker pay ratio — NUMBER:1 format, bidirectional
            ceo_worker_pay_ratio = (
                self._first_number(text, r"(?:ceo(?:-to-worker)?\s+pay\s+ratio|pay\s+ratio|ceo-to-median\s+worker)[^\d]{0,45}(\d{1,4}(?:\.\d+)?)")
                or self._first_number(text, r"(\d{1,4}(?:\.\d+)?)\s*(?:to\s*1|:1|x)\s{0,30}(?:ceo\s+pay|pay\s+ratio|compensation\s+ratio)")
                or self._first_number(text, r"ratio\s+of\s+(?:the\s+)?annual\s+total\s+compensation[^\d]{0,60}(\d{1,4}(?:\.\d+)?)\s*(?:to\s*1|:1)")
            )
            # LTI ESG % — bidirectional
            lti_esg_pct = (
                self._first_percent(text, r"(?:long[-\s]?term\s+incentive|lti|incentive\s+plan)[^\d]{0,40}(\d{1,3}(?:\.\d+)?)\s*%[^\n\r]{0,60}esg")
                or self._first_percent(text, r"esg\s{0,40}(\d{1,3}(?:\.\d+)?)\s*%\s{0,40}(?:of\s+)?(?:lti|long[-\s]?term)")
            )
            # Board size — accepts "board of directors", "supervisory board",
            # and "management board" (the German two-tier system reports both).
            board_size = (
                self._first_number(text, r"(?:supervisory\s+board|board\s+of\s+directors|management\s+board)\s+(?:consists?\s+of|comprises?\s+of?|has)\s+(\d{1,2})\s+(?:directors|members)")
                or self._first_number(text, r"board\s+(?:consists?|comprises?)\s+of\s+(\d{1,2})\s+(?:directors|members)")
            )
            audit_committee_independence = (
                ("audit committee" in text or "prüfungsausschuss" in text)
                and "100" in text and "independent" in text
            )
            # Whistleblower / ethics hotline disclosure — NYSE / Nasdaq /
            # Sarbanes-Oxley §301 require these for listed companies, and
            # the EU Whistleblower Directive (2019/1937) requires them for
            # any EU employer ≥50 staff. German DAX issuers commonly call
            # these "Speak Up", "Hinweisgebersystem", or "BKMS".
            whistleblower_hotline = any(p in text for p in (
                "ethics hotline", "ethics helpline", "whistleblower hotline",
                "whistleblowing system", "whistleblowing hotline",
                "speak up line", "speakup line", "speak-up line", "speakup channel",
                "anonymous reporting", "compliance hotline",
                "hinweisgebersystem", "bkms system",
                "integrity line", "integrity hotline",
            ))
            # Anti-corruption / code of conduct disclosure — broadened to
            # include EU/German anti-corruption frameworks and ISO 37001.
            has_anti_corruption_policy = any(p in text for p in (
                "code of conduct", "anti-corruption", "anti-bribery",
                "fcpa compliance", "uk bribery act", "anti-money laundering",
                "ethics training", "iso 37001", "compliance management system",
                "verhaltenskodex", "antikorruptionsrichtlinie",
            ))
            return {
                "board_independence_pct": board_independence_pct,
                "board_gender_pct": board_gender_pct,
                "ceo_worker_pay_ratio": ceo_worker_pay_ratio,
                "lti_esg_pct": lti_esg_pct,
                "board_size": board_size,
                "audit_committee_independence": audit_committee_independence,
                "whistleblower_hotline": whistleblower_hotline,
                "has_anti_corruption_policy": has_anti_corruption_policy,
            }
        except Exception:
            return {}

    def _extract_board_signals(self, combined_text: str, sec_proxy: Dict[str, Any]) -> Dict[str, Any]:
        board_ind = (
            self._first_percent(combined_text, r"(?:board independence|independent directors|independent non-executive directors|non-executive directors|independent supervisory board|independent members? of (?:the )?supervisory board)[^\d]{0,40}(\d{1,3}(?:\.\d+)?)\s*%")
            or self._first_percent(combined_text, r"(\d{1,3}(?:\.\d+)?)\s*%\s{0,40}(?:of\s+(?:the\s+)?)?(?:board members|directors|supervisory board members)\s{0,40}(?:are\s+)?independent")
            or self._first_fraction_pct(combined_text, r"(\d{1,2})\s+of\s+(?:our\s+|the\s+)?(\d{1,2})\s+(?:directors|board members|supervisory board members)\s{0,40}(?:are\s+)?independent")
        )
        board_gender = (
            self._first_percent(combined_text, r"(?:board gender|women on board|female directors|women['']?s?\s+share\s+(?:on|in)\s+(?:the\s+)?(?:supervisory\s+)?board|frauenquote)[^\d]{0,40}(\d{1,3}(?:\.\d+)?)\s*%")
            or self._first_percent(combined_text, r"(\d{1,3}(?:\.\d+)?)\s*%\s{0,30}women\s{0,30}(?:director|board|supervisory)")
            or self._first_fraction_pct(combined_text, r"(\d{1,2})\s+of\s+(?:our\s+|the\s+)?(\d{1,2})\s+(?:directors|board members|supervisory board members)\s{0,40}(?:are\s+)?(?:women|female)")
        )
        tenure = self._first_number(combined_text, r"(?:director tenure|average tenure)[^\d]{0,30}(\d{1,2}(?:\.\d+)?)")
        interlocks = self._first_number(combined_text, r"serves on[^\d]{0,30}(\d{1,2}) boards")

        for filing in sec_proxy.get("filings", []):
            parsed = filing.get("parsed_metrics", {})
            if board_ind is None and parsed.get("board_independence_pct") is not None:
                board_ind = parsed["board_independence_pct"]
            if board_gender is None and parsed.get("board_gender_pct") is not None:
                board_gender = parsed["board_gender_pct"]

        return {
            "board_independence_pct": board_ind,
            "board_gender_pct": board_gender,
            "max_director_tenure_years": tenure,
            "max_interlocks": interlocks,
        }

    def _extract_compensation_signals(self, combined_text: str, sec_proxy: Dict[str, Any]) -> Dict[str, Any]:
        pay_ratio = (
            self._first_number(combined_text, r"(?:ceo(?:-to-worker)?\s+pay\s+ratio|pay\s+ratio)[^\d]{0,30}(\d{1,4}(?:\.\d+)?)")
            or self._first_number(combined_text, r"(\d{1,4}(?:\.\d+)?)\s*(?:to\s*1|:1)\s{0,30}(?:ceo\s+pay|compensation\s+ratio)")
        )
        lti_esg = (
            self._first_percent(combined_text, r"(?:lti|long[-\s]?term\s+incentive)[^\d]{0,35}(\d{1,3}(?:\.\d+)?)\s*%[^\n\r]{0,40}esg")
            or self._first_percent(combined_text, r"esg\s{0,40}(\d{1,3}(?:\.\d+)?)\s*%\s{0,40}lti")
        )

        for filing in sec_proxy.get("filings", []):
            parsed = filing.get("parsed_metrics", {})
            if pay_ratio is None and parsed.get("ceo_worker_pay_ratio") is not None:
                pay_ratio = parsed["ceo_worker_pay_ratio"]
            if lti_esg is None and parsed.get("lti_esg_pct") is not None:
                lti_esg = parsed["lti_esg_pct"]

        return {
            "ceo_worker_pay_ratio": pay_ratio,
            "lti_esg_pct": lti_esg,
        }

    def _extract_audit_signals(self, combined_text: str) -> Dict[str, Any]:
        non_audit_pct = self._first_percent(combined_text, r"(?:non[- ]audit fees|fees paid to auditor)[^\d]{0,30}(\d{1,3}(?:\.\d+)?)\s*%")
        all_independent = any(term in combined_text for term in ["audit committee is entirely independent", "all independent", "100% independent audit", "audit committee consists solely of independent"])
        big4 = any(name in combined_text for name in ["deloitte", "pwc", "pricewaterhousecoopers", "kpmg", "ernst & young", "ey"])

        return {
            "big4_auditor_mentioned": big4,
            "all_audit_committee_independent": all_independent if "audit committee" in combined_text else None,
            "non_audit_fee_pct": non_audit_pct,
        }

    def _extract_regulatory_legal_signals(self, company: str, combined_text: str) -> Dict[str, Any]:
        sources: List[Dict[str, Any]] = []
        fine_signals = 0

        queries = [
            f'"{company}" SEC enforcement action',
            f'"{company}" DOJ investigation FCPA',
            f'"{company}" competition authority fine',
        ]
        # Build a token set of the company's distinctive name parts so we
        # can filter out off-topic results. DDG sometimes returns wildly
        # unrelated pages (e.g. Kraft Heinz Wikipedia for a "Tesla SEC
        # enforcement" query) — without this filter those leak into
        # Tesla's enforcement section as if they were Tesla evidence.
        import re as _re
        company_tokens = [
            t for t in _re.split(r"[^A-Za-z0-9]+", (company or "").lower())
            if len(t) >= 4 and t not in {"corp", "inc", "ltd", "plc", "group", "company", "limited"}
        ]
        # Companies whose names are short tickers (BP, GE, GM, IBM, SAP) —
        # use the original short token if no long token exists.
        if not company_tokens and company:
            short = (company or "").split()[0].lower()
            if 2 <= len(short) <= 4:
                company_tokens = [short]

        # Stale-record filter: Section 7C was carrying 25-year-old vacated
        # rulings (e.g. the 2000 Microsoft antitrust split, overturned in
        # 2001) alongside genuinely active 2026 cases without any date
        # cue, creating a misleading picture of ongoing legal exposure.
        # We pull the publication year from the URL or title and either
        # drop records older than the cutoff or tag them as HISTORICAL so
        # readers can distinguish current from historical exposure.
        from datetime import datetime as _dt
        _current_year = _dt.utcnow().year
        STALE_CUTOFF_YEARS = 10

        def _detect_year(blob: str) -> Optional[int]:
            for m in _re.finditer(r"(19[89]\d|20[0-3]\d)", blob):
                try:
                    yr = int(m.group(1))
                    if 1990 <= yr <= _current_year:
                        return yr
                except ValueError:
                    continue
            return None

        for q in queries:
            for item in search_duckduckgo(q, max_results=2):
                title = str(item.get("title", "") or "")
                url = str(item.get("url", "") or "")
                snippet = str(item.get("snippet", "") or "")
                hay_for_match = f"{title} {snippet} {url}".lower()

                # Skip results that don't reference the queried company
                # at all. This kills the Kraft Heinz / unrelated-company
                # contamination problem.
                if company_tokens and not any(tok in hay_for_match for tok in company_tokens):
                    continue

                # Extract year. Prefer URL (canonical date paths like
                # /2024/03/ or -2024-) over title (titles get rewritten).
                detected_year = _detect_year(url) or _detect_year(title) or _detect_year(snippet)
                if detected_year is not None and (_current_year - detected_year) > STALE_CUTOFF_YEARS:
                    # Skip records older than cutoff entirely.
                    continue

                sources.append(
                    {
                        "title": title,
                        "url": url,
                        "source": "Regulatory/legal search",
                        "published_year": detected_year,
                    }
                )
                hay = f"{title} {snippet}".lower()
                if any(term in hay for term in ["fine", "enforcement", "violation", "settlement", "investigation"]):
                    fine_signals += 1

        if any(token in combined_text for token in ["sec enforcement", "doj", "fcpa", "antitrust fine", "competition fine"]):
            fine_signals += 1

        return {
            "regulatory_fine_signals": fine_signals,
            "sources": sources,
        }

    def _extract_shareholder_rights(self, combined_text: str) -> Dict[str, Any]:
        return {
            "dual_class_structure": "dual-class" in combined_text or "dual class" in combined_text,
            "poison_pill": "poison pill" in combined_text,
            "staggered_board": "staggered board" in combined_text,
        }

    def _extract_tax_transparency(self, combined_text: str) -> Dict[str, Any]:
        stat = self._first_percent(combined_text, r"statutory tax rate[^\d]{0,20}(\d{1,2}(?:\.\d+)?)\s*%")
        eff = self._first_percent(combined_text, r"effective tax rate[^\d]{0,20}(\d{1,2}(?:\.\d+)?)\s*%")
        delta = None
        if stat is not None and eff is not None:
            delta = abs(stat - eff)

        tax_haven = any(tok in combined_text for tok in ["cayman", "bvi", "luxembourg"])

        return {
            "country_by_country_reporting_disclosed": "country-by-country" in combined_text or "country by country" in combined_text,
            "statutory_tax_rate_pct": stat,
            "effective_tax_rate_pct": eff,
            "effective_tax_rate_delta_pct": delta,
            "tax_haven_subsidiary_signal": tax_haven,
        }

    def _extract_whistleblower_signals(self, combined_text: str) -> Dict[str, Any]:
        hotline = any(term in combined_text for term in ["whistleblower", "speak up", "independent hotline", "grievance mechanism", "confidential reporting"])
        complaints = self._first_number(combined_text, r"(?:esg[- ]related complaints|whistleblower reports|speak up cases)[^\d]{0,40}(\d{1,5})")

        return {
            "independent_hotline_disclosed": hotline,
            "esg_related_complaints": complaints,
        }

    def _first_percent(self, text: str, pattern: str) -> Optional[float]:
        match = re.search(pattern, text)
        if not match:
            return None
        try:
            raw = match.group(1) if match.lastindex and match.lastindex >= 1 else match.group(0)
            # Strip trailing non-numeric chars before float conversion
            numeric = re.search(r"[\d]+\.?\d*", raw)
            return float(numeric.group(0)) if numeric else None
        except (ValueError, IndexError, AttributeError):
            return None

    def _first_fraction_pct(self, text: str, pattern: str) -> Optional[float]:
        """Extract first X-of-Y match and return (X/Y)*100.

        Handles both forms: '(X) of (Y)' and '(Y) of ... (X)'. We sort
        the two captured numbers so the smaller one is X (numerator) and
        the larger one is Y (denominator) — this works for "11 of 12
        directors" and "of our 12 directors, 11 are independent".
        """
        match = re.search(pattern, text)
        if not match or not match.lastindex or match.lastindex < 2:
            return None
        try:
            a = float(match.group(1))
            b = float(match.group(2))
        except (ValueError, IndexError):
            return None
        if a <= 0 or b <= 0:
            return None
        # Order so larger is denominator. Sanity: both ≤ 30 (board size cap).
        if a > 30 or b > 30:
            return None
        x, y = (a, b) if a <= b else (b, a)
        if y == 0:
            return None
        return round((x / y) * 100.0, 1)

    def _first_number(self, text: str, pattern: str) -> Optional[float]:
        match = re.search(pattern, text)
        if not match:
            return None
        try:
            raw = match.group(1) if match.lastindex and match.lastindex >= 1 else match.group(0)
            numeric = re.search(r"[\d]+\.?\d*", raw)
            return float(numeric.group(0)) if numeric else None
        except (ValueError, IndexError, AttributeError):
            return None

    def _risk_level(self, score: float) -> str:
        if score >= 70:
            return "LOW"
        if score >= 45:
            return "MODERATE"
        return "HIGH"
