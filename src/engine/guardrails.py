import os
import re
import logging
from groq import Groq
from src import config

# Configure Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Compile Regex Patterns for PII
PAN_PATTERN = re.compile(r"\b[A-Za-z]{5}\d{4}[A-Za-z]{1}\b")
AADHAAR_PATTERN = re.compile(r"\b\d{4}\s?\d{4}\s?\d{4}\b")
EMAIL_PATTERN = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b")
PHONE_PATTERN = re.compile(r"\b(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b")
OTP_KEYWORDS = ["otp", "verification code", "one time password", "one-time password"]

# Regex Patterns for Obvious Advisory Keywords
ADVISORY_KEYWORDS = [
    r"\bshould\s+i\b", r"\bis\s+it\s+good\b", r"\bwhich\s+is\s+better\b",
    r"\brecommend\b", r"\badvise\b", r"\bbuy\b", r"\bsell\b", r"\binvestment\s+advice\b",
    r"\bpredict\b", r"\bforecast\b", r"\bfuture\s+returns\b", r"\bbest\s+fund\b"
]
ADVISORY_PATTERN = re.compile("|".join(ADVISORY_KEYWORDS), re.IGNORECASE)

# In-Scope HDFC Fund keyword maps
HDFC_FUND_KEYS = ["mid-cap", "mid cap", "top 100", "large cap", "small cap", "gold etf", "gold fof", "defence"]

# Refusal Response Templates
REFUSAL_PII = (
    "For security and privacy reasons, I cannot process queries containing personal sensitive information "
    "(such as PAN, Aadhaar, account numbers, or OTPs). Please resubmit your query without any personal details."
)

REFUSAL_ADVISORY = (
    "I can only assist with objective, factual information about mutual fund schemes. I cannot provide "
    "investment advice, recommendations, or comparisons. For investment guidance, please consult a "
    "registered financial advisor or refer to the official resources: [AMFI India](https://www.amfiindia.com) "
    "or [SEBI Investor](https://investor.sebi.gov.in)."
)

REFUSAL_OUT_OF_SCOPE = (
    "I can only provide factual details for the 5 HDFC schemes currently in scope:\n"
    "1. HDFC Mid-Cap Opportunities Fund\n"
    "2. HDFC Top 100 Fund (Large Cap)\n"
    "3. HDFC Small Cap Fund\n"
    "4. HDFC Gold ETF Fund of Fund\n"
    "5. HDFC Defence Fund\n"
    "Please resubmit your query focusing on one of these schemes."
)

REFUSAL_AMBIGUOUS = (
    "Please specify which HDFC fund you are referring to: HDFC Mid-Cap, HDFC Large Cap, HDFC Small Cap, "
    "HDFC Gold ETF, or HDFC Defence Fund."
)


class QueryGuardrail:
    def __init__(self):
        # Initialize Groq client only if API key is present
        self.client = None
        if config.GROQ_API_KEY:
            self.client = Groq(api_key=config.GROQ_API_KEY)
            logger.info("Groq client initialized for LLM-based query classification.")
        else:
            logger.warning("GROQ_API_KEY missing. Falling back to rule-only classification.")

    def scan_for_pii(self, query):
        """
        Scans for PAN, Aadhaar, Emails, Phone numbers, and OTPs.
        Returns True if PII is detected, False otherwise.
        """
        if PAN_PATTERN.search(query):
            logger.warning("PII Warning: PAN pattern detected in query.")
            return True
        if AADHAAR_PATTERN.search(query):
            logger.warning("PII Warning: Aadhaar pattern detected in query.")
            return True
        if EMAIL_PATTERN.search(query):
            logger.warning("PII Warning: Email pattern detected in query.")
            return True
        
        # Check phone numbers (excluding very short numbers which could be amounts like ₹500)
        phone_match = PHONE_PATTERN.search(query)
        if phone_match and len(re.sub(r"\D", "", phone_match.group())) >= 10:
            logger.warning("PII Warning: Phone number pattern detected in query.")
            return True

        # Check for OTP keywords accompanied by digits
        if any(kw in query.lower() for kw in OTP_KEYWORDS) and re.search(r"\b\d{4,6}\b", query):
            logger.warning("PII Warning: OTP pattern detected in query.")
            return True

        return False

    def rule_based_classification(self, query):
        """
        Runs fast, local regex and keyword matches.
        Returns a classification category if matched, otherwise None.
        """
        # 1. Check PII
        if self.scan_for_pii(query):
            return "pii"

        # 2. Check obvious advisory markers
        if ADVISORY_PATTERN.search(query):
            logger.info("Rule-match: Classified query as 'advisory'")
            return "advisory"

        # 3. Check for obvious out-of-scope fund competitors
        competitors = ["sbi", "icici", "tata", "axis", "nippon", "quant", "mirae", "dsp", "uti", "parag parikh"]
        if any(comp in query.lower() for comp in competitors):
            logger.info("Rule-match: Classified query as 'out_of_scope' (competitor fund detected)")
            return "out_of_scope"

        return None

    def llm_based_classification(self, query):
        """
        Uses Groq API to perform zero-shot classification of the query category.
        Categorizes query as: 'factual', 'advisory', 'out_of_scope', 'ambiguous'.
        """
        if not self.client:
            # Fallback when Groq key is absent: check if any HDFC fund keyword is present
            has_fund_keyword = any(key in query.lower() for key in HDFC_FUND_KEYS)
            if not has_fund_keyword:
                # If no fund keyword, default to ambiguous or out_of_scope
                # But if they ask a general factual question like "What is an expense ratio?", let it pass.
                if any(kw in query.lower() for kw in ["what", "how", "define", "expense ratio", "exit load"]):
                    return "factual"
                return "ambiguous"
            return "factual"

        system_prompt = (
            "You are a strict compliance classifier for a Mutual Fund FAQ assistant. Your job is to classify "
            "incoming queries into one of the following exact labels:\n"
            "1. 'factual': Factual, objective, verifiable queries relating to expense ratios, exit loads, ratings, "
            "minimum SIPs, taxation, or fund management for HDFC mutual fund schemes.\n"
            "2. 'advisory': Queries seeking investment opinions, buy/sell recommendations, predictions of future returns, "
            "comparisons of which fund is better, or general subjective advice.\n"
            "3. 'out_of_scope': Queries relating to non-HDFC funds (e.g. SBI, ICICI) or general off-topic questions "
            "(e.g. weather, politics, programming).\n"
            "4. 'ambiguous': Factual queries about mutual funds that fail to specify which HDFC scheme they are referring to "
            "(e.g. 'What is the exit load?' or 'Who is the manager?').\n\n"
            "Return ONLY the exact label as a single word: factual, advisory, out_of_scope, or ambiguous."
        )

        try:
            chat_completion = self.client.chat.completions.create(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Query: {query}"}
                ],
                model=config.LLM_MODEL,
                temperature=0.0,
                max_tokens=10
            )
            category = chat_completion.choices[0].message.content.strip().lower()
            # Clean category text
            category = re.sub(r"[^\w\s-]", "", category).strip()
            
            if category in ["factual", "advisory", "out_of_scope", "ambiguous"]:
                logger.info(f"LLM-classification result: '{category}'")
                return category
            else:
                logger.warning(f"Unexpected LLM classification response: '{category}'. Defaulting to 'factual'")
                return "factual"
        except Exception as e:
            logger.error(f"Error calling LLM for classification: {e}. Defaulting to 'factual'.")
            return "factual"

    def evaluate_query(self, query):
        """
        Main entry point to run all guardrails on a query.
        Returns a tuple: (category, refusal_response)
        If category is 'factual', retrieval can proceed. Otherwise, return the refusal text directly.
        """
        # Clean query whitespace
        clean_query = query.strip()
        if not clean_query:
            return "empty", "Please input a valid query."

        # Step 1: Run fast local rule classification
        category = self.rule_based_classification(clean_query)
        if category:
            if category == "pii":
                return "pii", REFUSAL_PII
            if category == "advisory":
                return "advisory", REFUSAL_ADVISORY
            if category == "out_of_scope":
                return "out_of_scope", REFUSAL_OUT_OF_SCOPE

        # Step 2: Run semantic LLM-based classification
        category = self.llm_based_classification(clean_query)
        
        if category == "advisory":
            return "advisory", REFUSAL_ADVISORY
        elif category == "out_of_scope":
            return "out_of_scope", REFUSAL_OUT_OF_SCOPE
        elif category == "ambiguous":
            # If they ask a general term description (e.g. "What is an exit load?"), do not refuse, treat as factual
            if any(term in clean_query.lower() for term in ["what is exit load", "what is expense ratio", "define tax"]):
                return "factual", None
            return "ambiguous", REFUSAL_AMBIGUOUS

        return "factual", None


def test_guardrails():
    guard = QueryGuardrail()
    test_cases = [
        ("What is the expense ratio for HDFC Large Cap Fund?", "factual"),
        ("Should I invest in HDFC Mid-Cap Fund?", "advisory"),
        ("Which fund is better between HDFC Small Cap and SBI Small Cap?", "advisory"),
        ("My Aadhaar card number is 5432 1098 7654. What is the exit load?", "pii"),
        ("What is the exit load of ICICI Prudential Bluechip?", "out_of_scope"),
        ("Who is the fund manager?", "ambiguous"),
        ("What is the temperature in New Delhi?", "out_of_scope")
    ]
    
    print("\n--- Guardrails Verification Test ---")
    for q, expected in test_cases:
        category, response = guard.evaluate_query(q)
        print(f"Query: '{q}'\nExpected: '{expected}' | Got: '{category}'")
        if response:
            print(f"Refusal Response Snippet: {response[:80]}...")
        print("-" * 30)

if __name__ == "__main__":
    test_guardrails()
