import os
import json
import logging
import re
from bs4 import BeautifulSoup

# Configure Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
RAW_HTML_DIR = os.path.join(BASE_DIR, "data", "raw")
OUTPUT_JSON_DIR = os.path.join(BASE_DIR, "data", "parsed")
SOURCES_FILE = os.path.join(os.path.dirname(__file__), "sources.json")
MANIFEST_FILE = os.path.join(RAW_HTML_DIR, "manifest.json")

def slugify(text):
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[-\s]+", "_", text)
    return text

class GrowwFundParser:
    def __init__(self, raw_html_dir, output_json_dir):
        self.raw_html_dir = raw_html_dir
        self.output_json_dir = output_json_dir

    def extract_field_from_list(self, lines, label):
        """
        Helper to find a label in lines and return the immediate next non-tooltip line.
        """
        for i, line in enumerate(lines):
            if label.lower() == line.lower() or label.lower() in line.lower():
                # Check next few lines for values (ignoring tooltips and icons)
                for offset in range(1, 4):
                    if i + offset < len(lines):
                        val = lines[i + offset].strip()
                        if val not in ["?", "i", "info", ""] and len(val) < 150:
                            # Clean leading/trailing punctuation if it got appended
                            val = val.strip(" ;:,")
                            if val:
                                return val
        return "N/A"

    def parse_html_file(self, file_path, source_meta):
        if not os.path.exists(file_path):
            logger.error(f"File not found: {file_path}")
            return None

        with open(file_path, "r", encoding="utf-8") as f:
            html_content = f.read()
            
        soup = BeautifulSoup(html_content, "html.parser")

        # Get all text lines to extract tabular items sequentially
        raw_text = soup.get_text(separator="\n")
        lines = [line.strip() for line in raw_text.split("\n") if line.strip()]

        scheme_name = source_meta.get("scheme_name")
        amc_name = source_meta.get("amc_name", "HDFC Mutual Fund")

        # --- EXTRACT SECTIONS ---

        # Find the About paragraph first (used for fallback matching)
        about_text = ""
        for line in lines:
            if "mutual fund scheme" in line.lower() and "launched by" in line.lower():
                about_text = line.strip()
                break

        # 1. Overview
        nav_date = "N/A"
        nav_value = "N/A"
        for i, line in enumerate(lines):
            if "NAV:" in line:
                nav_date = line.replace("NAV:", "").strip()
                if i + 1 < len(lines):
                    nav_value = lines[i + 1].strip()
                break

        fund_size = self.extract_field_from_list(lines, "Fund size (AUM)")
        
        # Risk classification
        risk_level = "N/A"
        for line in lines:
            if line.lower() in ["low risk", "moderately low risk", "moderate risk", "moderately high risk", "high risk", "very high risk"]:
                risk_level = line.strip()
                break
        if risk_level == "N/A":
            for line in lines:
                if "very high" in line.lower():
                    risk_level = "Very High Risk"
                    break
                elif "high" in line.lower():
                    risk_level = "High Risk"
                    break
                elif "moderate" in line.lower():
                    risk_level = "Moderate Risk"
                    break

        rating = self.extract_field_from_list(lines, "Rating")

        overview_section = {
            "scheme_name": scheme_name,
            "latest_nav": nav_value,
            "nav_date": nav_date,
            "fund_size_aum": fund_size,
            "risk_classification": risk_level,
            "rating": rating,
            "about_summary": about_text
        }

        # 2. Expense Ratio
        expense_ratio_val = self.extract_field_from_list(lines, "Expense ratio")
        # Find if there are terms/glossary definitions for Expense ratio
        expense_ratio_terms = ""
        for i, line in enumerate(lines):
            if line.lower() == "expense ratio" and i + 1 < len(lines):
                if "fee payable to" in lines[i + 1].lower() or "total percentage" in lines[i + 1].lower():
                    expense_ratio_terms = lines[i + 1].strip()
                    break
        expense_ratio_section = {
            "value": expense_ratio_val,
            "description": expense_ratio_terms
        }

        # 3. Exit Load
        exit_load_val = "N/A"
        exit_load_terms = ""
        for i, line in enumerate(lines):
            if line.lower() == "exit load" and i + 1 < len(lines):
                val = lines[i + 1]
                # Skip glossary definitions
                if "fee payable to" in val.lower() or "exiting a fund" in val.lower():
                    exit_load_terms = val.strip()
                    continue
                # Look for specific load terms
                if "exit load of" in val.lower() or "redeemed" in val.lower() or "nil" in val.lower() or "%" in val.lower():
                    exit_load_val = val.strip()
                    break
                # Check secondary lines
                if i + 2 < len(lines) and ("exit load of" in lines[i + 2].lower() or "redeemed" in lines[i + 2].lower() or "nil" in lines[i + 2].lower() or "%" in lines[i + 2].lower()):
                    exit_load_val = lines[i + 2].strip()
                    break

        exit_load_section = {
            "value": exit_load_val,
            "description": exit_load_terms
        }

        # 4. Minimum Investment
        min_sip = self.extract_field_from_list(lines, "Min. for SIP")
        if min_sip == "N/A":
            min_sip = self.extract_field_from_list(lines, "Min. for SIP")
            
        # Try "Min. for 1st investment" (Lumpsum)
        min_lumpsum = self.extract_field_from_list(lines, "Min. for 1st investment")
        if min_lumpsum == "N/A" or min_lumpsum in [";", ""]:
            min_lumpsum = self.extract_field_from_list(lines, "Minimum lumpsum")
            
        # Fallback to about_text parsing for lumpsum and SIP
        if about_text:
            if min_lumpsum == "N/A" or min_lumpsum in [";", ""]:
                match_lump = re.search(r"minimum lumpsum(?: investment)? is(?: set to)?\s*₹?\s*([\d,]+)", about_text, re.IGNORECASE)
                if match_lump:
                    min_lumpsum = f"₹{match_lump.group(1)}"
            if min_sip == "N/A" or min_sip in [";", ""]:
                match_sip = re.search(r"minimum sip(?: investment)? is(?: set to)?\s*₹?\s*([\d,]+)", about_text, re.IGNORECASE)
                if match_sip:
                    min_sip = f"₹{match_sip.group(1)}"

        # Strip remaining noisy characters
        if min_sip != "N/A":
            min_sip = min_sip.strip(" ;:,")
        if min_lumpsum != "N/A":
            min_lumpsum = min_lumpsum.strip(" ;:,")

        minimum_investment_section = {
            "minimum_sip": min_sip,
            "minimum_lumpsum": min_lumpsum
        }

        # 5. Benchmark
        benchmark_val = self.extract_field_from_list(lines, "Fund benchmark")
        benchmark_section = {
            "benchmark_index": benchmark_val
        }

        # 6. Tax
        tax_val = "N/A"
        tax_terms = ""
        for i, line in enumerate(lines):
            if "tax implication" in line.lower() and i + 1 < len(lines):
                tax_val = lines[i + 1].strip()
                break
            if line.lower() == "tax" and i + 1 < len(lines):
                if "percentage of your capital gains" in lines[i + 1].lower():
                    tax_terms = lines[i + 1].strip()
        
        tax_section = {
            "tax_implication": tax_val,
            "description": tax_terms
        }

        # 7. Fund Management
        managers = []
        for i, line in enumerate(lines):
            if line.lower() == "fund management":
                idx = i + 1
                while idx < len(lines) and lines[idx].lower() != "about" and lines[idx].lower() != "compare":
                    # Check if line looks like initials and next line is a name
                    if len(lines[idx]) == 2 and lines[idx].isupper() and idx + 1 < len(lines):
                        manager_name = lines[idx + 1].strip()
                        tenure = "N/A"
                        education = "N/A"
                        experience = "N/A"
                        
                        # Look ahead for details
                        detail_idx = idx + 2
                        while detail_idx < len(lines) and len(lines[detail_idx]) > 2:
                            text_block = lines[detail_idx]
                            if re.search(r"[A-Za-z]{3}\s+\d{4}", text_block) or "present" in text_block.lower():
                                tenure = text_block
                                if detail_idx + 1 < len(lines) and "present" in lines[detail_idx + 1].lower():
                                    tenure = f"{tenure} {lines[detail_idx + 1]}"
                            elif "education" in text_block.lower() and detail_idx + 1 < len(lines):
                                education = lines[detail_idx + 1].strip()
                            elif "experience" in text_block.lower() and detail_idx + 1 < len(lines):
                                experience = lines[detail_idx + 1].strip()
                            elif "manages these schemes" in text_block.lower():
                                break
                            detail_idx += 1
                        
                        managers.append({
                            "name": manager_name,
                            "tenure": tenure.strip(" ;:,"),
                            "education": education.strip(" ;:,"),
                            "experience": experience.strip(" ;:,")
                        })
                    idx += 1
                break

        if not managers and about_text:
            match = re.search(r"([A-Za-z\s]+) is the current fund manager", about_text, re.IGNORECASE)
            if match:
                managers.append({
                    "name": match.group(1).strip(),
                    "tenure": "N/A",
                    "education": "N/A",
                    "experience": "N/A"
                })

        fund_management_section = {
            "managers": managers
        }

        # 8. Investment Objective
        obj_val = "N/A"
        for i, line in enumerate(lines):
            if "investment objective" in line.lower() and i + 1 < len(lines):
                obj_val = lines[i + 1].strip()
                break
        
        investment_objective_section = {
            "objective": obj_val
        }

        # 9. Fund House
        fund_house_val = amc_name
        fund_house_details = {}
        for i, line in enumerate(lines):
            if "fund house" in line.lower() and i + 1 < len(lines):
                candidate_house = lines[i + 1].strip()
                if "know about" not in candidate_house.lower() and len(candidate_house) < 50:
                    fund_house_val = candidate_house
                
                # Extract details
                idx = i + 2
                while idx < len(lines) and idx < i + 15:
                    if "rank" in lines[idx].lower() and idx + 1 < len(lines):
                        fund_house_details["rank"] = lines[idx + 1].strip()
                    elif "total aum" in lines[idx].lower() and idx + 1 < len(lines):
                        fund_house_details["total_aum"] = lines[idx + 1].strip()
                    elif "date of incorporation" in lines[idx].lower() and idx + 1 < len(lines):
                        fund_house_details["incorporation_date"] = lines[idx + 1].strip()
                    idx += 1
                break

        fund_house_section = {
            "name": fund_house_val,
            "details": fund_house_details
        }

        # --- COMPILE SYNTHESIS TEXT ---
        managers_summary = ""
        for m in managers:
            managers_summary += f"- {m['name']} (Tenure: {m['tenure']}). Education: {m['education']}. Experience: {m['experience']}\n"
        
        summary_text = (
            f"Scheme Name: {scheme_name}\n"
            f"Fund House: {fund_house_val}\n"
            f"Latest NAV: {nav_value} (as of {nav_date})\n"
            f"Fund Size (AUM): {fund_size}\n"
            f"Risk Classification: {risk_level}\n"
            f"Rating: {rating}\n"
            f"Investment Objective: {obj_val}\n"
            f"Minimum SIP: {min_sip}, Minimum Lumpsum: {min_lumpsum}\n"
            f"Expense Ratio: {expense_ratio_val}\n"
            f"Exit Load: {exit_load_val}\n"
            f"Taxation: {tax_val}\n"
            f"Benchmark Index: {benchmark_val}\n"
            f"Fund Managers:\n{managers_summary if managers_summary else 'N/A'}"
        )

        parsed_data = {
            "scheme_name": scheme_name,
            "amc_name": amc_name,
            "source_url": source_meta.get("url"),
            "fetch_timestamp": source_meta.get("fetch_timestamp", "N/A"),
            "last_updated": nav_date,
            "sections": {
                "overview": overview_section,
                "expense_ratio": expense_ratio_section,
                "exit_load": exit_load_section,
                "minimum_investment": minimum_investment_section,
                "benchmark": benchmark_section,
                "tax": tax_section,
                "fund_management": fund_management_section,
                "investment_objective": investment_objective_section,
                "fund_house": fund_house_section
            },
            "summary_text": summary_text
        }
        return parsed_data

    def run(self):
        if not os.path.exists(MANIFEST_FILE):
            logger.error(f"Manifest file not found at: {MANIFEST_FILE}")
            return

        with open(MANIFEST_FILE, "r") as fm:
            manifest = json.load(fm)

        os.makedirs(self.output_json_dir, exist_ok=True)
        
        for slug, meta in manifest.items():
            filename = meta.get("filename")
            file_path = os.path.join(self.raw_html_dir, filename)
            
            logger.info(f"Parsing raw HTML for scheme: {meta.get('scheme_name')}")
            parsed_data = self.parse_html_file(file_path, meta)
            
            if parsed_data:
                output_filename = f"{slug}.json"
                output_path = os.path.join(self.output_json_dir, output_filename)
                with open(output_path, "w", encoding="utf-8") as f_out:
                    json.dump(parsed_data, f_out, indent=2)
                logger.info(f"Successfully saved parsed data to: {output_path}")

def main():
    parser = GrowwFundParser(RAW_HTML_DIR, OUTPUT_JSON_DIR)
    parser.run()

if __name__ == "__main__":
    main()
