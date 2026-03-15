"""
Utils Package
Data sources, web search, and source tracking utilities

Modules:
- free_data_sources: 22+ free APIs for ESG data collection
- indian_data_sources: Indian-specific ESG data sources
- enterprise_data_sources: Enterprise-grade data APIs
- web_search: Web search utilities
- source_tracker: Source usage tracking
- company_report_fetcher: Fetch PDF reports from company websites
- indian_financial_data: Indian company revenue and financial data
"""

from .free_data_sources import FreeDataAggregator, free_data_aggregator
from .indian_data_sources import IndianDataAggregator, get_indian_data_aggregator
from .source_tracker import source_tracker
from .company_report_fetcher import CompanyReportFetcher, get_report_fetcher
from .indian_financial_data import IndianFinancialData, get_indian_financial_data

__all__ = [
    'FreeDataAggregator',
    'free_data_aggregator',
    'IndianDataAggregator',
    'get_indian_data_aggregator',
    'source_tracker',
    'CompanyReportFetcher',
    'get_report_fetcher',
    'IndianFinancialData',
    'get_indian_financial_data'
]