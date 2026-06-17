import os
import re
import logging
from groq import Groq
from src import config
from src.engine.guardrails import QueryGuardrail
from src.engine.retriever import SchemeRetriever

# Configure Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

class AnswerGenerator:
    def __init__(self):
        self.client = None
        if config.GROQ_API_KEY:
            self.client = Groq(api_key=config.GROQ_API_KEY)
            logger.info("Groq client initialized for LLM-based answer generation.")
        else:
            logger.warning("GROQ_API_KEY is missing. Generator will run in Mock-Factual fallback mode.")

    def count_sentences(self, text):
        """
        Splits text into sentences using standard punctuation and counts them.
        """
        # Split on sentence boundaries, ignoring numbers with decimals (e.g., 0.73%)
        # and abbreviation periods (e.g., Mr., Dr., L.A., A.U.M.)
        text_clean = re.sub(r"(?<=\d)\.(?=\d)", "", text) # Temporarily remove decimal points
        text_clean = re.sub(r"\b(?:Mr|Dr|Ms|AUM|NAV|SIP|LTCG|STCG)\.", "", text_clean, flags=re.IGNORECASE)
        sentences = re.split(r"[.!?;\n]+", text_clean)
        # Filter out empty or whitespace-only elements
        sentences = [s.strip() for s in sentences if s.strip()]
        return len(sentences)

    def extract_urls(self, text):
        """
        Extracts all HTTP/HTTPS links present in the text.
        """
        return re.findall(r"https?://[^\s()<>]+(?:\([\w\d]+\)|([^[:punct:]\s]|/))", text)

    def mock_factual_generation(self, query, contexts):
        """
        Mock generator that extracts key facts directly from contexts using regex.
        Used as a fallback when GROQ_API_KEY is not configured.
        """
        if not contexts:
            return "I do not have access to that information. For official details, please consult a financial advisor."
        
        ctx = contexts[0]
        text = ctx["text"]
        url = ctx["source_url"]
        date = ctx["last_updated"]
        scheme = ctx["scheme_name"]

        query_lower = query.lower()
        
        # Simple extraction rules
        if "exit load" in query_lower:
            match = re.search(r"Exit Load:\s*(.*?)\n", text)
            val = match.group(1) if match else "Exit load details are not explicitly present."
            ans = f"For the {scheme}, the exit load is as follows: {val}"
        elif "expense ratio" in query_lower or "charges" in query_lower:
            match = re.search(r"Expense Ratio:\s*(.*?)\n", text)
            val = match.group(1) if match else "not specified"
            ans = f"The expense ratio for the {scheme} is {val}."
        elif "sip" in query_lower or "minimum" in query_lower or "lumpsum" in query_lower:
            match_sip = re.search(r"Minimum SIP:\s*([^,\n]+)", text)
            match_lump = re.search(r"Minimum Lumpsum:\s*([^\n]+)", text)
            sip = match_sip.group(1) if match_sip else "N/A"
            lump = match_lump.group(1) if match_lump else "N/A"
            ans = f"The minimum SIP amount for {scheme} is {sip}, and the minimum lumpsum is {lump}."
        elif "manager" in query_lower or "management" in query_lower or "run" in query_lower or "who is the current" in query_lower:
            manager_section = re.search(r"Fund Managers:\n(.*)", text, re.DOTALL)
            if manager_section:
                mgrs = re.findall(r"-\s*([A-Za-z\s]+)\s*\(Tenure", manager_section.group(1))
                managers = ", ".join(mgrs) if mgrs else "N/A"
            else:
                managers = "N/A"
            ans = f"The current fund manager(s) for the {scheme} is: {managers}."
        elif "benchmark" in query_lower or "index" in query_lower:
            match = re.search(r"Benchmark Index:\s*(.*?)\n", text)
            val = match.group(1) if match else "N/A"
            ans = f"The benchmark index for {scheme} is the {val}."
        elif "tax" in query_lower or "taxation" in query_lower:
            match = re.search(r"Taxation:\s*(.*?)\n", text)
            val = match.group(1) if match else "not specified"
            ans = f"Taxation rules for {scheme}: {val}"
        else:
            match = re.search(r"Investment Objective:\s*(.*?)\n", text)
            val = match.group(1) if match else "Factual details are available on the Groww scheme page."
            ans = f"{scheme} objective: {val}"

        # Standardize formatting
        formatted_response = f"{ans}\nSource: {url}\nLast updated from sources: {date}"
        return formatted_response

    def post_validate_and_correct(self, response_text, contexts):
        """
        Runs programmatic validation on LLM output to enforce formatting and length constraints.
        Returns a cleaned, compliant string.
        """
        if not contexts:
            return response_text

        primary_ctx = contexts[0]
        correct_url = primary_ctx["source_url"]
        correct_date = primary_ctx["last_updated"]

        # 1. PII Redaction
        clean_text = response_text
        clean_text = re.sub(r"\b[A-Za-z]{5}\d{4}[A-Za-z]{1}\b", "[REDACTED PAN]", clean_text)
        clean_text = re.sub(r"\b\d{4}\s?\d{4}\s?\d{4}\b", "[REDACTED AADHAAR]", clean_text)

        # Split into main text, source link, and footer
        lines = [line.strip() for line in clean_text.split("\n") if line.strip()]

        main_sentences = []
        found_source = ""
        found_footer = ""

        for line in lines:
            if "source:" in line.lower() or "http" in line.lower():
                found_source = line
            elif "last updated" in line.lower():
                found_footer = line
            else:
                main_sentences.append(line)

        # Merge main sentences together
        main_body = " ".join(main_sentences)

        # 2. Check Sentence Count (Max 3 sentences)
        sentence_count = self.count_sentences(main_body)
        if sentence_count > 3:
            logger.warning(f"Validation Warning: Sentence count ({sentence_count}) exceeds limit of 3. Truncating.")
            # Programmatically split and slice first 3 sentences
            text_clean = re.sub(r"(?<=\d)\.(?=\d)", "", main_body)
            raw_sentences = re.split(r"(?<=[.!?])\s+", main_body)
            main_body = " ".join(raw_sentences[:3])

        # 3. Citation Check: Ensure exactly one citation link
        if not found_source:
            # Append correct URL
            found_source = f"Source: {correct_url}"
        else:
            # Force the URL in found_source to be the exact correct URL from metadata
            found_source = f"Source: {correct_url}"

        # 4. Footer Date Check
        found_footer = f"Last updated from sources: {correct_date}"

        # Re-assemble compliance formatted answer
        final_answer = f"{main_body.strip()}\n{found_source}\n{found_footer}"
        return final_answer

    def generate_answer(self, query, contexts):
        """
        Sends query + context to Groq to generate a facts-only compliant answer.
        """
        if not contexts:
            return "I do not have access to that information. For details, please consult a financial advisor."

        if not self.client:
            return self.mock_factual_generation(query, contexts)

        # Assemble retrieved context blocks
        context_str = "\n---\n".join([c["text"] for c in contexts])

        system_prompt = (
            "You are a facts-only Mutual Fund FAQ Assistant.\n"
            "Your task is to answer the user's query using ONLY the provided contexts. Do not assume, extrapolate, or recommend.\n\n"
            "Strict Compliance Constraints:\n"
            "1. Limit your answer to a maximum of 3 sentences.\n"
            "2. Under no circumstances provide investment advice, advisory suggestions, or buy/sell recommendations.\n"
            "3. If the context does not contain the answer, state: 'I do not have that information from official sources.'\n"
            "4. Include exactly one citation link at the end of the answer using the exact source URL provided in the matching context.\n"
            "   Format exactly: 'Source: <source_url>'\n"
            "5. Append a footer exactly matching this format: 'Last updated from sources: <date>' where <date> is from the matching context."
        )

        user_content = f"Contexts:\n{context_str}\n\nUser Query: {query}"

        try:
            chat_completion = self.client.chat.completions.create(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content}
                ],
                model=config.LLM_MODEL,
                temperature=0.0, # Lock to temperature zero to minimize hallucination
                max_tokens=250
            )
            raw_response = chat_completion.choices[0].message.content.strip()
            logger.info("LLM generation completed. Running post-validation parser...")
            
            # Programmatic correction wrapper
            validated_response = self.post_validate_and_correct(raw_response, contexts)
            return validated_response

        except Exception as e:
            logger.error(f"Error calling Groq API: {e}. Falling back to mock generator.")
            return self.mock_factual_generation(query, contexts)


class MutualFundFAQAssistant:
    def __init__(self):
        self.guard = QueryGuardrail()
        self.retriever = SchemeRetriever()
        self.generator = AnswerGenerator()

    def process_query(self, query):
        """
        End-to-end pipeline execution block.
        1. Evaluate query using guardrails.
        2. If not factual, return refusal response immediately.
        3. Retrieve scoped context.
        4. Generate validated, facts-only response.
        """
        logger.info(f"Processing user query: '{query}'")
        
        # 1. Guardrail Check
        category, refusal_text = self.guard.evaluate_query(query)
        if category != "factual":
            logger.info(f"Pipeline intercept: Query classified as '{category}'. Serving refusal response.")
            return refusal_text

        # 2. Retrieval
        contexts = self.retriever.retrieve_context(query)
        if not contexts:
            return "I do not have that information from official sources."

        # 3. Generation & Validation
        answer = self.generator.generate_answer(query, contexts)
        return answer


def test_end_to_end():
    assistant = MutualFundFAQAssistant()
    test_queries = [
        "What is the exit load for HDFC Mid-Cap opportunities fund?",
        "Who runs the HDFC Defence Fund?",
        "Should I buy HDFC Small Cap Fund?",
        "What is the lock-in period for HDFC Large Cap?"
    ]
    
    print("\n--- End-to-End Pipeline Test ---")
    for q in test_queries:
        print(f"\nUser: {q}")
        reply = assistant.process_query(q)
        print(f"Assistant:\n{reply}")
        print("=" * 40)

if __name__ == "__main__":
    test_end_to_end()
