"""Single Claude call that turns normalized document text into a validated ReportData instance. No RAG, no chunking - see ADR-0001."""
import os  # standard library for reading environment variables
import anthropic  # Anthropic SDK for accessing Claude API
from .schema import ReportData  # import ReportData schema class from extraction package


DEFAULT_MODEL = "claude-opus-5"  # default model to use when ANTHROPIC_MODEL env var is not set

EXTRACTION_INSTRUCTIONS = """You are extracting structured data from a company's financial disclosure document to populate an equity research report template. The source document may be a bank's investor deck, a power company's results presentation, an e-commerce quarterly report, or any other sector - use whatever metrics and language that specific document actually reports, do not force it into a fixed metric list.

Rules:
- Every field you cannot support directly from the document text must be left as null (for scalars) or an empty list (for lists). Never invent, estimate, or guess a number, a rating, a target price, or a narrative claim that is not traceable to the document.
- highlights: pull the document's own key bullet points/highlights.
- outlook: synthesize a short narrative from the document's own forward-looking statements, if present - do not add investment advice.
- financial_table_rows: the document's headline period-over-period metrics (e.g. Sales/EBITDA/PAT for a company, or NII/NIM/deposits for a bank), with period_values keyed by whatever period labels the document uses.
- full_financials: any additional financial-statement-style rows the document supports beyond the headline table (balance sheet, cashflow, ratios) - can be empty if the document doesn't go that deep.
- chart_series: one entry per numerical time series worth charting (e.g. revenue by quarter). Produce at least one if the document contains any quarter-over-quarter or year-over-year figures at all.
- historical_ratings: almost always empty for an arbitrary company document - only populate if the document itself states a rating history, which is rare.
"""  # system instructions that guide Claude's extraction behavior


def _build_prompt(document_text: str, company_name: str) -> str:  # helper function to compose the prompt sent to Claude
    """Compose the single user-turn prompt sent to Claude."""
    return (  # build the complete prompt string
        f"{EXTRACTION_INSTRUCTIONS}\n\n"  # prepend extraction rules and context
        f"Company name: {company_name}\n\n"  # insert the company name after instructions
        f"--- BEGIN SOURCE DOCUMENT ---\n{document_text}\n--- END SOURCE DOCUMENT ---"  # wrap the actual document text with delimiters
    )


def extract_report_data(  # main extraction function exposed to callers
    document_text: str, company_name: str, client: anthropic.Anthropic | None = None  # document to extract, company identifier, optional mock client for testing
) -> ReportData:  # return type is the validated ReportData schema
    """Call Claude once with the full document in context and return a schema-validated ReportData. Pass `client` in tests to avoid network calls; production callers omit it and get a real Anthropic() client that resolves credentials from the environment."""
    if client is None:  # check if a client was provided by the caller
        client = anthropic.Anthropic()  # if not, create a real Anthropic client that will use ANTHROPIC_API_KEY from environment
    model = os.environ.get("ANTHROPIC_MODEL", DEFAULT_MODEL)  # allow cheaper models for dev iteration without changing code
    prompt = _build_prompt(document_text, company_name)  # call helper to build the user message containing document and company name
    response = client.messages.parse(  # call Claude's structured output API to get validated parsing
        model=model,  # use the model from environment or the default
        max_tokens=16000,  # allow sufficient tokens for complex financial documents with multiple tables
        messages=[{"role": "user", "content": prompt}],  # pass the assembled prompt as a user message
        output_format=ReportData,  # tell Claude to validate and return output as ReportData schema
    )
    return response.parsed_output  # extract and return the parsed ReportData object from Claude's response
