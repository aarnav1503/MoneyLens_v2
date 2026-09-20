"""
Bank Statement Processing Service.
Parses PDF / CSV statements, classifies transactions into 12 standard categories,
computes essential vs discretionary, detects weekend spikes and micro-transactions,
and deletes raw statements immediately if save_raw is False.

Supports common Indian bank formats:
- HDFC Bank CSV: Date, Narration, Value Dt, Debit Amount, Credit Amount, Chq/Ref Number, Closing Balance
- SBI CSV: Txn Date, Value Date, Description, Ref No./Cheque No., Debit, Credit, Balance
- ICICI Bank CSV: Transaction Date, Transaction Remarks, Withdrawal Amount (INR ), Deposit Amount (INR ), Balance (INR )
- Axis Bank CSV: Tran Date, PARTICULARS, CHQNO, VALUEDATE, WITHDRAWAL AMT, DEPOSIT AMT, BALANCE AMT
- Generic: date, description/narration, debit/credit/amount columns
"""

import io
import csv
import re
import uuid
import statistics
from typing import Optional, List, Dict, Any, Tuple
from app.repositories.postgres_statement_repo import PostgresStatementRepository
from app.repositories.postgres_profile_repo import PostgresProfileRepository
from app.schemas.profile import FinancialProfileUpdate
from app.schemas.statements import StatementAnalysisSummary, StatementTransactionItem
from app.schemas.spending import STANDARD_SPENDING_CATEGORIES


CATEGORY_KEYWORDS = {
    "Subscriptions": ["subscription", "netflix", "spotify", "prime video", "hotstar", "apple.com", "google play",
                      "patreon", "medium", "chatgpt", "cloud", "aws", "github", "zee5", "sonyliv", "jiocinema",
                      "youtube premium", "linkedin", "adobe", "microsoft 365", "office365"],
    "Entertainment": ["cinema", "pvr", "inox", "movie", "bookmyshow", "game", "steam", "playstation",
                      "xbox", "concert", "theatre", "amusement"],
    "Food Delivery": ["swiggy", "zomato", "eats", "deliveroo", "foodpanda", "dunzo food"],
    "Restaurants": ["restaurant", "cafe", "diner", "bistro", "starbucks", "barbeque", "mcdonalds",
                    "kfc", "burger king", "dominos", "pizza hut", "subway", "chaayos", "chai point",
                    "coffee day", "ccd", "barista"],
    "Food": ["supermarket", "grocery", "groceries", "bigbasket", "blinkit", "zepto", "dmart", "spencer",
             "milk", "vegetables", "reliance fresh", "nature's basket", "more", "spar", "easyday"],
    "Shopping": ["amazon", "flipkart", "myntra", "ajio", "zara", "h&m", "retail", "croma", "reliancedigital",
                 "mall", "nykaa", "meesho", "snapdeal", "tatacliq", "westside", "shoppers stop",
                 "pantaloons", "lifestyle"],
    "Transport": ["uber", "ola", "rapido", "petrol", "fuel", "hpcl", "bpcl", "ioc", "metro", "irctc",
                  "flight", "indigo", "air india", "vistara", "spicejet", "toll", "fastag", "parking",
                  "bus", "railway", "train", "rickshaw", "auto"],
    "Utilities": ["electricity", "bescom", "tpddl", "msedcl", "airtel", "jio", "vodafone", "vi", "bsnl",
                  "broadband", "water", "gas", "piped gas", "wifi", "maintenance", "society", "recharge",
                  "prepaid", "postpaid", "mobile bill"],
    "Healthcare": ["pharmacy", "apollo", "medplus", "hospital", "clinic", "doctor", "diagnostic",
                   "1mg", "practo", "dentist", "netmeds", "pharmeasy", "health", "lab", "scan", "test",
                   "insurance premium", "mediclaim", "star health", "hdfc ergo"],
    "Education": ["coursera", "udemy", "school", "college", "tuition", "books", "edtech", "upgrad",
                  "byju", "unacademy", "vedantu", "fees", "admission", "institution", "university"],
    "Travel": ["airbnb", "hotel", "resort", "makemytrip", "goibibo", "booking.com", "agoda",
               "cleartrip", "oyo", "treebo", "yatra", "thomas cook", "holiday"],
    "Investments": ["sip", "mutual fund", "mf", "nps", "ppf", "rd", "fd", "fixed deposit",
                    "recurring deposit", "groww", "zerodha", "upstox", "angel", "hdfc securities",
                    "icici direct", "kotak securities", "motilal"],
    "EMI/Loan": ["emi", "loan", "installment", "home loan", "car loan", "personal loan",
                 "education loan", "bajaj finserv", "hdfc ltd", "lic housing"],
}

ESSENTIAL_CATEGORIES = {"Food", "Utilities", "Healthcare", "Education", "Transport"}

# Column header aliases for common Indian bank CSV exports
_DATE_ALIASES = {"date", "txn date", "tran date", "transaction date", "value dt", "value date",
                 "posting date", "trans date", "trans. date", "posting dt"}
_DESC_ALIASES = {"narration", "description", "particulars", "transaction remarks", "details",
                 "remark", "desc", "merchant", "transaction narration", "trans description"}
_DEBIT_ALIASES = {"debit", "debit amount", "withdrawal", "withdrawal amt", "withdrawal amount",
                  "dr", "dr amount", "dr amt", "debit (inr)", "withdrawal amount (inr )"}
_CREDIT_ALIASES = {"credit", "credit amount", "deposit", "deposit amt", "deposit amount",
                   "cr", "cr amount", "cr amt", "credit (inr)", "deposit amount (inr )"}
_AMOUNT_ALIASES = {"amount", "amt", "value", "transaction amount"}
_TYPE_ALIASES = {"type", "cr/dr", "dr/cr", "txn type", "transaction type"}


class StatementService:
    def __init__(
        self,
        statement_repo: Optional[PostgresStatementRepository] = None,
        profile_repo: Optional[PostgresProfileRepository] = None,
    ):
        self.statement_repo = statement_repo or PostgresStatementRepository()
        self.profile_repo = profile_repo or PostgresProfileRepository()

    def _categorize(self, description: str) -> str:
        desc_lower = description.lower()
        for cat, keywords in CATEGORY_KEYWORDS.items():
            if any(kw in desc_lower for kw in keywords):
                return cat
        return "Other"

    def _clean_amount(self, raw: str) -> float:
        """Parse an Indian-formatted amount string to float."""
        if not raw:
            return 0.0
        cleaned = re.sub(r"[₹$\s,]", "", raw.strip())
        # Remove trailing Dr/Cr suffix
        cleaned = re.sub(r"(?i)(dr|cr)$", "", cleaned).strip()
        try:
            return abs(float(cleaned))
        except ValueError:
            return 0.0

    def _is_credit_suffix(self, raw: str) -> bool:
        """Detect credit by Cr suffix common in Indian bank statements."""
        raw_lower = raw.strip().lower()
        return raw_lower.endswith("cr") or raw_lower.endswith(" cr")

    def _is_debit_suffix(self, raw: str) -> bool:
        """Detect debit by Dr suffix common in Indian bank statements."""
        raw_lower = raw.strip().lower()
        return raw_lower.endswith("dr") or raw_lower.endswith(" dr")

    def _match_header(self, header: str, aliases: set) -> bool:
        """Check if a CSV header matches any alias (case-insensitive, stripped)."""
        return header.strip().lower() in aliases

    def parse_csv_content(self, content_str: str) -> List[Dict[str, Any]]:
        """Parses CSV string into raw transaction dicts, supporting major Indian bank formats."""
        lines = [l for l in content_str.strip().splitlines() if l.strip()]
        if not lines:
            return []

        # Detect delimiter
        delimiter = ","
        if "\t" in lines[0]:
            delimiter = "\t"
        elif ";" in lines[0]:
            delimiter = ";"

        reader = csv.reader(lines, delimiter=delimiter)
        raw_headers = next(reader, [])
        headers = [h.strip().lower() for h in raw_headers]

        # Map column indices
        date_idx = desc_idx = amount_idx = type_idx = debit_idx = credit_idx = -1

        for i, h in enumerate(headers):
            if date_idx < 0 and self._match_header(h, _DATE_ALIASES):
                date_idx = i
            elif desc_idx < 0 and self._match_header(h, _DESC_ALIASES):
                desc_idx = i
            elif debit_idx < 0 and self._match_header(h, _DEBIT_ALIASES):
                debit_idx = i
            elif credit_idx < 0 and self._match_header(h, _CREDIT_ALIASES):
                credit_idx = i
            elif amount_idx < 0 and self._match_header(h, _AMOUNT_ALIASES):
                amount_idx = i
            elif type_idx < 0 and self._match_header(h, _TYPE_ALIASES):
                type_idx = i

        # Fallback: if no desc found, use second non-date column
        if desc_idx < 0 and len(headers) >= 2:
            desc_idx = 1 if date_idx != 1 else 2

        raw_txs = []
        for row in reader:
            if not row or len(row) < 2:
                continue
            if all(c.strip() == "" for c in row):
                continue

            date_val = row[date_idx].strip() if 0 <= date_idx < len(row) else ""
            desc_val = row[desc_idx].strip() if 0 <= desc_idx < len(row) else "Transaction"
            if not desc_val:
                desc_val = "Transaction"

            amt = 0.0
            tx_type = "debit"

            if debit_idx >= 0 and credit_idx >= 0:
                # Separate debit/credit columns (most common Indian format)
                dr_raw = row[debit_idx].strip() if debit_idx < len(row) else ""
                cr_raw = row[credit_idx].strip() if credit_idx < len(row) else ""
                dr_val = self._clean_amount(dr_raw)
                cr_val = self._clean_amount(cr_raw)

                if dr_val > 0:
                    amt = dr_val
                    tx_type = "debit"
                elif cr_val > 0:
                    amt = cr_val
                    tx_type = "credit"

            elif amount_idx >= 0:
                raw_amt_str = row[amount_idx].strip() if amount_idx < len(row) else ""
                # Check for Dr/Cr suffix in the amount field itself
                if self._is_credit_suffix(raw_amt_str):
                    tx_type = "credit"
                elif self._is_debit_suffix(raw_amt_str):
                    tx_type = "debit"
                elif type_idx >= 0 and type_idx < len(row):
                    t_str = row[type_idx].lower()
                    if "cr" in t_str or "credit" in t_str or "deposit" in t_str:
                        tx_type = "credit"
                    else:
                        tx_type = "debit"
                amt = self._clean_amount(raw_amt_str)

            # Also scan description for Dr/Cr keywords if still ambiguous
            desc_lower = desc_val.lower()
            if "salary" in desc_lower or "sal/" in desc_lower or " sal " in desc_lower:
                tx_type = "credit"
            elif "refund" in desc_lower or "reversal" in desc_lower or "cashback" in desc_lower:
                tx_type = "credit"

            if amt > 0 and date_val:
                raw_txs.append({
                    "date": date_val,
                    "description": desc_val,
                    "amount": amt,
                    "type": tx_type,
                })

        return raw_txs

    def _parse_text_lines(self, full_text: str) -> List[Dict[str, Any]]:
        """Parses extracted text lines to find transactions."""
        raw_txs: List[Dict[str, Any]] = []
        try:

            date_pattern = re.compile(
                r'(\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b|\b\d{4}[/-]\d{2}[/-]\d{2}\b|\b\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{2,4}\b)',
                re.IGNORECASE
            )
            # Amount pattern — handles ₹, INR, Rs., and plain numbers with Indian comma formatting
            amount_pattern = re.compile(
                r'(?:₹\s*|INR\s*|Rs\.?\s*)?([0-9]{1,3}(?:,[0-9]{2,3})*(?:\.[0-9]{1,2})?|[0-9]+(?:\.[0-9]{1,2})?)(?:\s*(Cr|Dr))?',
                re.IGNORECASE
            )

            lines = full_text.splitlines()
            for line in lines:
                line_str = line.strip()
                if not line_str or len(line_str) < 5:
                    continue

                date_match = date_pattern.search(line_str)
                if not date_match:
                    continue

                date_val = date_match.group(1)
                line_lower = line_str.lower()

                # Find amounts in the line
                valid_amounts = []
                last_cr_dr = None
                for m in amount_pattern.finditer(line_str):
                    val_raw = m.group(1).replace(",", "")
                    try:
                        val_float = float(val_raw)
                        # Exclude year-like numbers
                        if val_float <= 0 or (2020 <= val_float <= 2030 and "." not in m.group(1)):
                            continue
                        suffix = (m.group(2) or "").lower()
                        valid_amounts.append((val_float, suffix))
                        if suffix in ("cr", "dr"):
                            last_cr_dr = suffix
                    except ValueError:
                        pass

                if not valid_amounts:
                    continue

                # Determine transaction amount — prefer the first non-balance amount
                # Many Indian statements have: date, desc, debit, credit, balance
                # We take the first meaningful amount
                amt, suffix = valid_amounts[0]

                # Determine credit/debit
                tx_type = "debit"
                if suffix == "cr":
                    tx_type = "credit"
                elif suffix == "dr":
                    tx_type = "debit"
                elif last_cr_dr == "cr" and len(valid_amounts) >= 2:
                    # Last column has Cr → it's a credit
                    tx_type = "credit"
                    amt = valid_amounts[-2][0] if len(valid_amounts) >= 2 else valid_amounts[0][0]
                elif " cr" in line_lower or "credit" in line_lower or "deposit" in line_lower \
                        or "salary" in line_lower or "refund" in line_lower or "cashback" in line_lower:
                    tx_type = "credit"
                elif " dr" in line_lower or "debit" in line_lower or "withdrawal" in line_lower:
                    tx_type = "debit"

                # Build clean description
                desc = line_str.replace(date_val, "").strip()
                desc = re.sub(r'[₹$]', '', desc)
                desc = re.sub(r'(?:INR|Rs\.?)\s*', '', desc, flags=re.IGNORECASE)
                desc = re.sub(r'\b[0-9]{1,3}(?:,[0-9]{2,3})*(?:\.[0-9]{1,2})?\s*(?:Cr|Dr)?\b', '', desc, flags=re.IGNORECASE)
                desc = re.sub(r'\s+', ' ', desc).strip()
                if not desc or len(desc) < 2:
                    desc = "Bank Statement Transaction"

                raw_txs.append({
                    "date": date_val,
                    "description": desc[:80],
                    "amount": amt,
                    "type": tx_type
                })

        except Exception as e:
            print(f"Error parsing text lines: {e}")

        return raw_txs

    def parse_pdf_content(self, content_bytes: bytes) -> List[Dict[str, Any]]:
        """Parses PDF binary stream and extracts structured transaction records from Indian bank statements."""
        from app.services.ocr_service import OcrService
        ocr = OcrService()
        
        text, source = ocr.extract_text_from_pdf(content_bytes)
        if not text:
            return []
            
        return ocr.extract_transactions_with_confidence(text, source)

    def _detect_salary_income(self, txs: List[Dict[str, Any]]) -> Optional[float]:
        """
        Tries to identify the user's monthly income/salary from credit transactions.
        Returns the best estimated monthly income figure, or None if not determinable.

        Logic:
        - Collect all credit amounts.
        - If any credit has 'salary'/'sal' in description → use it directly.
        - Otherwise, find the largest single credit ≥ 10x the median debit → treat as salary.
        - If multiple large similar credits → average them (recurring payroll).
        """
        credits = [t for t in txs if t["type"] == "credit"]
        debits = [t for t in txs if t["type"] == "debit"]

        if not credits:
            return None

        # Direct salary match
        salary_credits = [
            t["amount"] for t in credits
            if any(k in t["description"].lower() for k in ["salary", "sal/", " sal ", "payroll", "pay roll", "stipend", "wages"])
        ]
        if salary_credits:
            return max(salary_credits)  # Take the largest salary credit

        # Heuristic: large recurring credit ≥ 10× median debit
        if debits:
            debit_amounts = [t["amount"] for t in debits]
            try:
                median_debit = statistics.median(debit_amounts)
            except Exception:
                median_debit = sum(debit_amounts) / len(debit_amounts)
            large_credits = [t["amount"] for t in credits if t["amount"] >= max(10 * median_debit, 10000)]
            if large_credits:
                return max(large_credits)

        return None

    def _detect_emi_payments(self, txs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return [t for t in txs if t["type"] == "debit" and self._categorize(t["description"]) == "EMI/Loan"]

    def _detect_investments(self, txs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return [t for t in txs if t["type"] == "debit" and self._categorize(t["description"]) == "Investments"]

    def _detect_recurring_payments(self, txs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        # For statement-based detection, we just look at Subscriptions/Utilities that we already categorized
        return [t for t in txs if t["type"] == "debit" and self._categorize(t["description"]) in {"Subscriptions", "Utilities"}]

    def process_statement(
        self,
        user_id: str,
        filename: str,
        content_bytes: bytes,
        save_raw: bool,
    ) -> Tuple[StatementAnalysisSummary, List[StatementTransactionItem]]:
        """Processes uploaded statement, categorizes transactions, and generates summary."""
        raw_txs: List[Dict[str, Any]] = []

        if filename.lower().endswith(".pdf") or content_bytes[:4] == b"%PDF":
            raw_txs = self.parse_pdf_content(content_bytes)
        else:
            content_str = ""
            try:
                content_str = content_bytes.decode("utf-8", errors="ignore")
            except Exception:
                content_str = ""
            # Try utf-8, fallback to latin-1 for some bank exports
            if not content_str.strip():
                try:
                    content_str = content_bytes.decode("latin-1", errors="ignore")
                except Exception:
                    pass
            raw_txs = self.parse_csv_content(content_str)

        parsed_items: List[StatementTransactionItem] = []
        category_totals: Dict[str, float] = {c: 0.0 for c in STANDARD_SPENDING_CATEGORIES}
        total_credits = 0.0
        total_debits = 0.0
        essential_spending = 0.0
        discretionary_spending = 0.0
        recurring_spending = 0.0

        for tx in raw_txs:
            amt = float(tx["amount"])
            tx_type = tx["type"]
            cat = self._categorize(tx["description"])
            is_ess = cat in ESSENTIAL_CATEGORIES
            is_rec = cat in {"Subscriptions", "Utilities"}

            if tx_type == "credit":
                total_credits += amt
            else:
                total_debits += amt
                category_totals[cat] = category_totals.get(cat, 0.0) + amt
                if is_ess:
                    essential_spending += amt
                else:
                    discretionary_spending += amt
                if is_rec:
                    recurring_spending += amt

            parsed_items.append(
                StatementTransactionItem(
                    id=f"tx_{uuid.uuid4().hex[:8]}",
                    date=tx["date"],
                    description=tx["description"],
                    amount=amt,
                    type=tx_type,
                    category=cat,
                    is_recurring=is_rec,
                    is_essential=is_ess,
                )
            )

        stmt_id = f"stmt_{uuid.uuid4().hex[:8]}"
        
        # --- Run detection heuristics for pending observations ---
        detected_income = self._detect_salary_income(raw_txs)
        detected_emis = self._detect_emi_payments(raw_txs)
        detected_invs = self._detect_investments(raw_txs)
        detected_recurring = self._detect_recurring_payments(raw_txs)

        from app.schemas.statements import PendingObservation
        current_profile = self.profile_repo.get_profile(user_id)
        current_prof_dict = current_profile.model_dump() if current_profile else {}
        pending_obs: List[PendingObservation] = []

        if detected_income and detected_income > 0:
            pending_obs.append(PendingObservation(
                type="salary_detected",
                field="monthly_income",
                amount=detected_income,
                description="Salary / Income Deposit",
                confidence=0.9,
                current_value=current_prof_dict.get("monthly_income", 0.0)
            ))
            
        if detected_emis:
            total_emi = sum(t["amount"] for t in detected_emis)
            pending_obs.append(PendingObservation(
                type="emi_detected",
                field="active_emis",
                amount=total_emi,
                description=f"EMI Payments ({len(detected_emis)} found)",
                confidence=0.85,
                current_value=current_prof_dict.get("active_emis", 0.0)
            ))
            
        if detected_invs:
            total_inv = sum(t["amount"] for t in detected_invs)
            pending_obs.append(PendingObservation(
                type="investment_detected",
                field="monthly_investments",
                amount=total_inv,
                description=f"Investments & SIPs ({len(detected_invs)} found)",
                confidence=0.85,
                current_value=current_prof_dict.get("monthly_investments", 0.0)
            ))
            
        if detected_recurring:
            total_rec = sum(t["amount"] for t in detected_recurring)
            pending_obs.append(PendingObservation(
                type="recurring_detected",
                field="other_recurring_expenses",
                amount=total_rec,
                description=f"Recurring Payments ({len(detected_recurring)} found)",
                confidence=0.8,
                current_value=current_prof_dict.get("other_recurring_expenses", 0.0)
            ))

        extraction_source = raw_txs[0].get("source", "text") if raw_txs else "text"

        summary = StatementAnalysisSummary(
            statement_id=stmt_id,
            filename=filename,
            save_raw=save_raw,
            total_credits=total_credits,
            total_debits=total_debits,
            net_cashflow=total_credits - total_debits,
            transaction_count=len(parsed_items),
            date_range_start=parsed_items[0].date if parsed_items else None,
            date_range_end=parsed_items[-1].date if parsed_items else None,
            category_breakdown=category_totals,
            essential_spending=essential_spending,
            discretionary_spending=discretionary_spending,
            recurring_spending=recurring_spending,
            extraction_source=extraction_source,
            detected_salary=detected_income,
            detected_emis=detected_emis,
            detected_investments=detected_invs,
            detected_recurring=detected_recurring,
            pending_observations=pending_obs,
            observations=[
                f"Processed {len(parsed_items)} statement transactions totaling ₹{total_debits:,.0f} in outflows and ₹{total_credits:,.0f} in inflows.",
                f"Essential expenses represent {round((essential_spending / total_debits * 100), 1) if total_debits > 0 else 0}% of debits.",
                f"Recurring subscriptions and utility bills totaled ₹{recurring_spending:,.0f}.",
            ] if parsed_items else [
                "No readable transaction records were identified in the uploaded document. Please check the file formatting."
            ],
        )

        # Store in repository
        if parsed_items:
            self.statement_repo.save_statement_summary(user_id, summary, parsed_items, filename=filename)

        # Ephemeral processing compliance
        if not save_raw:
            del content_bytes

        return summary, parsed_items
