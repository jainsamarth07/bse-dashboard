"""
AI prompt templates used for financial result analysis.

Kept in one place so they can be tweaked without touching any logic code.
"""

FINANCIAL_ANALYSIS_PROMPT = """
**TASK: EXTRACT, CALCULATE, AND FORMAT FINANCIAL DATA (CONSOLIDATED BASIS)**

You are given the text of a financial results PDF filed to BSE India. Your job is to
extract the key numbers AND compute growth rates and margins.

**STEP 1: AUTO-DETECT THE PERIODS**
The document contains a table with multiple columns for different periods.
Identify the THREE most relevant quarterly periods from the table headers:
  - **Latest Quarter (L.Q.):** The most recent quarter ended date in the document.
  - **Previous Quarter (P.Q.):** The quarter immediately before L.Q.
  - **Same Quarter Last Year (S.Q.L.Y.):** The same quarter from the previous year.

If the document is for Q3 (Dec quarter), use Dec 2025, Sep 2025, Dec 2024.
If Q2 (Sep quarter), use Sep 2025, Jun 2025, Sep 2024.
If Q1 (Jun quarter), use Jun 2025, Mar 2025, Jun 2024.
If Q4 (Mar quarter), use Mar 2025, Dec 2024, Mar 2024.
Use whatever dates are actually present in the PDF — do NOT assume fixed dates.

**BUNDLED-FILING RULE:** Some filings combine more than one reporting period in
a single document — most commonly a delayed/late Annual Audited result (year
ended March) bundled together with the current quarter's regular Unaudited
result, approved by the board on the same day. When the subject line or
document body mentions more than one distinct period, always treat the
CHRONOLOGICALLY MOST RECENT quarter-end date as the Latest Quarter (L.Q.) —
ignore older annual/audited catch-up periods in favor of whichever quarter
end is closest to today, since that is the period most relevant for spotting
fresh trading signals. Extract L.Q./P.Q./S.Q.L.Y. figures from that most
recent quarter's table specifically, not the older bundled period.

**STEP 2: IDENTIFY COMPANY & UNIT**
- **COMPANY NAME:** Extract from letterhead or title.
- **REPORTING UNIT:** Detect the unit (₹ in crores / lakhs / millions).

**STEP 3: DATA EXTRACTION**
Read ONLY the **CONSOLIDATED** data (prefer consolidated over standalone).
If only standalone is available, use standalone.

Extract these line items for all three periods:
1. **Revenue (R):** "Total Revenue from Operations" or "Total Income"
2. **Net Profit (NP):** "Profit for the period (after tax)"
3. **EBITDA (E):** Calculate as:
   EBITDA = Profit before tax + Depreciation + Finance Costs - Other Income

**STEP 4: COMPUTATIONS (round to 1 decimal)**
- Q/Q Growth (%) = ((L.Q. - P.Q.) / |P.Q.|) × 100
- Y/Y Growth (%) = ((L.Q. - S.Q.L.Y.) / |S.Q.L.Y.|) × 100
- EBITDA Margin (%) = (EBITDA / Revenue) × 100
- Net Profit Margin (%) = (Net Profit / Revenue) × 100

**FINAL OUTPUT FORMAT (STRICTLY adhere to this — no commentary, no steps):**

COMPANY NAME: <value>
Unit: <value>
Quarter: <L.Q. period, e.g. "Dec 2025" or "Sep 2025">

GROWTH:

Revenue:
• Q/Q: <value>%
• Y/Y: <value>%

EBITDA:
• Q/Q: <value>%
• Y/Y: <value>%

Net Profit:
• Q/Q: <value>%
• Y/Y: <value>%

ABSOLUTE NUMBERS:

Revenue:
• Latest Quarter: <value>
• Previous Quarter: <value>
• Same Quarter Last Year: <value>

EBITDA:
• Latest Quarter: <value>
• Previous Quarter: <value>
• Same Quarter Last Year: <value>

Net Profit:
• Latest Quarter: <value>
• Previous Quarter: <value>
• Same Quarter Last Year: <value>

MARGINS:

EBITDA Margin:
• Latest Quarter: <value>%
• Previous Quarter: <value>%
• Same Quarter Last Year: <value>%

Net Profit Margin:
• Latest Quarter: <value>%
• Previous Quarter: <value>%
• Same Quarter Last Year: <value>%

Use NA only if a value truly does not exist in the document. Do not add any commentary.

---

**MACHINE-READABLE OUTPUT (MANDATORY — append AFTER the human-readable block above):**

After the human-readable text above, on a new line output EXACTLY:

```
UI_PAYLOAD_START
```

Then output a single valid JSON object (no commentary before or after) with this exact schema:

{
  "scrip_code": "<PLACEHOLDER — will be filled by caller>",
  "company_name": "<extracted company name>",
  "unit": "<reporting unit, e.g. '₹ Crores', '₹ Lakhs', 'Millions', or 'NA'>",
  "quarter": "<e.g. 'Dec 2025'>",
  "raw_analysis": "<PLACEHOLDER — will be filled by caller>",
  "growth": {
    "revenue":    {"qoq": <number|null>, "yoy": <number|null>},
    "ebitda":     {"qoq": <number|null>, "yoy": <number|null>},
    "net_profit": {"qoq": <number|null>, "yoy": <number|null>}
  },
  "absolute_numbers": {
    "revenue":    {"latest": <number|null>, "previous": <number|null>, "sqly": <number|null>},
    "ebitda":     {"latest": <number|null>, "previous": <number|null>, "sqly": <number|null>},
    "net_profit": {"latest": <number|null>, "previous": <number|null>, "sqly": <number|null>}
  },
  "margins": {"ebitda_margin": <number|null>, "net_profit_margin": <number|null>},
  "signal": "<BUY|SELL|HOLD|NEUTRAL>",
  "confidence": <0-100 integer>
}

Rules for the JSON:
- Use plain numbers for growth/margin values (NOT strings with "%").
- Use null (not "NA") for unavailable numeric values.
- signal: Based on growth trajectory and margins — BUY if strong growth + expanding margins, SELL if declining, HOLD if mixed, NEUTRAL if insufficient data.
- confidence: 0-100 integer reflecting data quality and clarity of signal.

Then on a new line output EXACTLY:

```
UI_PAYLOAD_END
```

Do NOT add any text between UI_PAYLOAD_START/END other than the JSON object.
"""

AI_SYSTEM_MESSAGE = (
    "You are a financial analyst expert. Extract and analyze "
    "financial data from corporate result documents accurately. "
    "Follow the output format exactly as specified. "
    "Always include both human-readable analysis AND the machine-readable "
    "UI_PAYLOAD JSON block."
)


def build_period_anchor(subject: str | None, news_date: str | None) -> str:
    """Build a ground-truth preamble anchoring the reporting period.

    Without this, the model has to infer the "latest quarter" purely from
    table content in a long PDF. Observed in testing: some filings genuinely
    bundle two distinct result sets in one document (e.g. a delayed Annual
    Audited result alongside the current quarter's regular Unaudited result,
    approved by the board on the same day) — Gemini and Groq each correctly
    read a different, both-legitimate section of the same STCINDIA filing
    and reported different periods. Neither was wrong about what the PDF
    said; the document itself was ambiguous about which period to lead with.
    BSE's own subject line names the period(s) explicitly (e.g. "RESULTS FOR
    31.03.2026"), so pass it through as ground truth, with an explicit
    tie-breaker toward the most recent period when more than one is present.
    """
    if not subject and not news_date:
        return ""

    parts = []
    if subject:
        parts.append(f'This filing was announced to BSE under the subject: "{subject}".')
    if news_date:
        parts.append(f"BSE recorded this announcement on {news_date}.")
    hint = " ".join(parts)

    return (
        "**GROUND TRUTH — REPORTING PERIOD ANCHOR (read this first):**\n"
        f"{hint}\n"
        "Treat the period(s) stated or implied in this subject line as ground "
        "truth — they take precedence over any other date found inside the PDF "
        "(comparative years, cover-page dates, unrelated tables, etc.). If the "
        "subject line names MORE THAN ONE period (e.g. a bundled Annual Audited "
        "+ current-quarter Unaudited filing), use the CHRONOLOGICALLY MOST "
        "RECENT one as the Latest Quarter (L.Q.) — see the BUNDLED-FILING RULE "
        "below. If the subject line does not explicitly state a period, fall "
        "back to inferring L.Q. from the table headers as described below.\n\n"
    )
