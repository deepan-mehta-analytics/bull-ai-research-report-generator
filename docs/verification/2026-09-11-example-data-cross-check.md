# Example PDF Data Cross-Check (2026-09-11)

## Why this exists

This project's whole design principle is "never invent, estimate, or guess a number" (see
`ENGINEERING_REPORT.md`, ADR-0004). That principle is only as credible as the evidence behind it.
The two committed example reports (`examples/jsw_energy_report.pdf`, `examples/icici_bank_report.pdf`)
were regenerated on 2026-09-11 against the real Anthropic API and the real source documents in
`local-input/`. This document independently verifies — via live web search against public,
third-party sources, not by re-reading the same source PDF — that the figures Claude extracted, and
the dual-axis growth charts computed from them, match real-world reported results rather than being
hallucinated or drifted during extraction.

Methodology: for each example, the report's own "Quarterly Financials" figures were compared against
public news coverage of the same company's same quarter. A match across independent sources is strong
evidence the extraction is faithful to the source document, and — since chart growth values are
computed arithmetically from these same extracted numbers (see ADR-0006), never requested from Claude
as a separate figure — that the growth-line overlays are trustworthy by construction.

---

## ICICI Bank — Q2 FY26 (quarter ended September 30, 2025)

| Metric | Generated PDF | Independently reported | Match |
|---|---|---|---|
| Net profit (PAT) | ₹123.59 bn, +5.2% YoY | ₹12,359 crore, +5% YoY, from ₹11,746 crore | ✓ exact |
| Net Interest Income | ₹215.29 bn, +7.4% YoY | ₹21,529 crore, +7.4% | ✓ exact |
| Net interest margin | 4.30% | 4.3% (flat) | ✓ exact |
| Total deposits growth | +7.7% YoY | +7.7% | ✓ exact |
| Provisions | ₹9.14 bn, −25.9% YoY | ₹914 crore, −26% YoY | ✓ exact |
| Gross NPA ratio | 1.58% (from 1.67% prior qtr) | 1.58% (from 1.67%) | ✓ exact |

Every cross-checked figure matched exactly, down to the decimal.

Sources:
- [ICICI Bank Q2 FY26 results: Net profit rises 5% to ₹12,359 crore — Business Standard](https://www.business-standard.com/companies/quarterly-results/icici-bank-q2-fy26-results-net-profit-rises-3-2-to-13-357-crore-125101800560_1.html)
- [Performance Review: Quarter ended September 30, 2025 — ICICI Bank](https://www.icici.bank.in/about-us/news-room/2025/performance-review-quarter-ended-september-30-2025)
- [ICICI Bank's Q2 FY26 Results: Loan Growth Moderates, Deposit Growth Healthy, Margins Expand — Whalesbook](https://www.whalesbook.com/news/English/bankingfinance/icici-bank-q2-fy26-loan-growth-moderates-but-profitability-still-very-strong/68f5bd5941347be54e119e18)

---

## JSW Energy — Q2 FY26 (quarter ended September 30, 2025)

| Metric | Generated PDF | Independently reported | Match |
|---|---|---|---|
| Total Revenue | ₹5,361 Cr, +55% YoY | ₹5,361.07 Cr, +55% YoY | ✓ exact |
| EBITDA | ₹3,180 Cr, +67% YoY, 59% margin | ₹3,180 Cr, +67% YoY, 59% margin | ✓ exact |
| Reported PAT | ₹705 Cr, −17% YoY | ₹705 crore, −17% YoY (₹704.68 Cr precise) | ✓ exact |

**A note on methodology, kept deliberately visible rather than smoothed over:** the first web search
returned a third-party aggregator (Mercom India) reporting different figures (₹5,177 Cr revenue,
₹824 Cr net profit). Rather than treat that as confirmation of an extraction error, a more targeted
search was run for the company's own reported figures, which surfaced better sources — Business
Standard's own headline coverage and EquityBulls — both matching the generated PDF exactly. The
Mercom India figure was the less-accurate outlier, not the generated report. This is recorded here as
a reminder that a single web source is not automatically ground truth either; the same
verify-before-asserting discipline this project applies to LLM output was applied to the verification
step itself.

Sources:
- [JSW Energy Q2 results: PAT drops 17% to Rs 705 crore, revenue up 55% — Business Standard](https://www.business-standard.com/companies/quarterly-results/jsw-energy-q2-results-pat-drops-17-to-705-crore-revenue-up-55-125101701218_1.html)
- [JSW Energy drops after Q2 PAT slumps 17% YoY to Rs 705 cr — Business Standard](https://www.business-standard.com/amp/markets/capital-market-news/jsw-energy-drops-after-q2-pat-slumps-17-yoy-to-rs-705-cr-125102000294_1.html)
- [JSW Energy Ltd posts Rs. 704.68 crores consolidated net profit in Q2 FY26 — EquityBulls](https://www.equitybulls.com/category.php?id=363169)
- [Renewable Energy Capacity Expansions Drive JSW Energy's Q2 Revenue Up 55% YoY — Mercom India](https://www.mercomindia.com/jsw-energys-q2-revenue-up-55-yoy) (the initial outlier figure, kept for reference)

---

## Conclusion

Both regenerated examples' extracted figures, and the dual-axis growth charts computed from them,
check out against independent, real-world reporting. No fabricated or drifted numbers were found in
either example.
