"""
Official Government of India Financial Schemes Dataset (Day 5).

Curated from official Department of Financial Services (DFS) portals:
- Primary DFS portal: https://www.financialservices.gov.in/schemes-and-services
- PMJJBY: https://www.financialservices.gov.in/pmjjby
- PMSBY: https://www.financialservices.gov.in/pmsby
- PMJDY: https://www.financialservices.gov.in/pradhan-mantri-jan-dhan-yojana-pmjdy
- myScheme: https://www.myscheme.gov.in/

Last verified date: 2026-08-10
"""

from typing import Any

LAST_VERIFIED_DATE: str = "2026-08-10"

OFFICIAL_SOURCES: dict[str, str] = {
    "DFS_PORTAL": "https://www.financialservices.gov.in/schemes-and-services",
    "PMJJBY": "https://www.financialservices.gov.in/pmjjby",
    "PMSBY": "https://www.financialservices.gov.in/pmsby",
    "PMJDY": "https://www.financialservices.gov.in/pradhan-mantri-jan-dhan-yojana-pmjdy",
    "MYSCHEME": "https://www.myscheme.gov.in/",
}

SCHEMES_DATA: dict[str, dict[str, Any]] = {
    "PMJJBY": {
        "scheme_code": "PMJJBY",
        "scheme_full_name": "Pradhan Mantri Jeevan Jyoti Bima Yojana",
        "category": "life_insurance",
        "min_age": 18,
        "max_age": 50,
        "requires_bank_or_post_office_account": True,
        "annual_premium": "₹436",
        "coverage": "₹2 lakh life cover (death due to any cause)",
        "account_requirement": "Individual account in participating bank or Post Office with auto-debit consent",
        "official_source": OFFICIAL_SOURCES["PMJJBY"],
        "last_verified": LAST_VERIFIED_DATE,
    },
    "PMSBY": {
        "scheme_code": "PMSBY",
        "scheme_full_name": "Pradhan Mantri Suraksha Bima Yojana",
        "category": "accident_insurance",
        "min_age": 18,
        "max_age": 70,
        "requires_bank_or_post_office_account": True,
        "annual_premium": "₹20",
        "coverage": "₹2 lakh for accidental death or total permanent disability; ₹1 lakh for partial permanent disability",
        "account_requirement": "Individual account in participating bank or Post Office with auto-debit consent",
        "official_source": OFFICIAL_SOURCES["PMSBY"],
        "last_verified": LAST_VERIFIED_DATE,
    },
    "PMJDY": {
        "scheme_code": "PMJDY",
        "scheme_full_name": "Pradhan Mantri Jan Dhan Yojana",
        "category": "basic_banking",
        "requires_unbanked": True,
        "annual_premium": "₹0 (No minimum balance requirement)",
        "coverage": "Basic Savings Bank Deposit (BSBD) Account, free RuPay debit card, accidental insurance cover for RuPay cardholders, ₹10,000 overdraft facility (subject to eligibility conditions)",
        "account_requirement": "Unbanked individual needing a basic savings bank account",
        "official_source": OFFICIAL_SOURCES["PMJDY"],
        "last_verified": LAST_VERIFIED_DATE,
    },
}


def normalize_scheme_input(scheme_name: str | None, category_of_interest: str | None) -> str | None:
    """Map user input string or category to supported scheme code."""
    if scheme_name:
        s_lower = scheme_name.strip().lower()
        if "pmjjby" in s_lower or "jeevan jyoti" in s_lower or "life insurance" in s_lower:
            return "PMJJBY"
        if "pmsby" in s_lower or "suraksha bima" in s_lower or "accident insurance" in s_lower:
            return "PMSBY"
        if "pmjdy" in s_lower or "jan dhan" in s_lower or "basic banking" in s_lower or "savings account" in s_lower:
            return "PMJDY"

    if category_of_interest:
        c_lower = category_of_interest.strip().lower()
        if "life" in c_lower or "jyoti" in c_lower:
            return "PMJJBY"
        if "accident" in c_lower or "suraksha" in c_lower:
            return "PMSBY"
        if "banking" in c_lower or "jandhan" in c_lower or "account" in c_lower or "unbanked" in c_lower:
            return "PMJDY"

    return None


def evaluate_scheme_eligibility(
    scheme_name: str | None = None,
    category_of_interest: str | None = None,
    age: int | None = None,
    has_bank_or_post_office_account: bool | None = None,
    is_unbanked: bool | None = None,
) -> dict[str, Any]:
    """Evaluate eligibility for PMJJBY, PMSBY, or PMJDY based on official DFS criteria.

    Returns structured dictionary with status:
    - potential_match
    - does_not_meet_criteria
    - insufficient_information
    - error (if unhandled input or data issue)
    """
    scheme_code = normalize_scheme_input(scheme_name, category_of_interest)
    if not scheme_code or scheme_code not in SCHEMES_DATA:
        return {
            "status": "insufficient_information",
            "scheme": scheme_name or "unknown",
            "reason": "Please specify one of the supported schemes: PMJJBY (Life Insurance), PMSBY (Accident Insurance), or PMJDY (Basic Banking).",
            "supported_schemes": ["PMJJBY", "PMSBY", "PMJDY"],
            "official_source": OFFICIAL_SOURCES["DFS_PORTAL"],
            "last_verified": LAST_VERIFIED_DATE,
            "disclaimer": (
                "This result is based on a locally curated dataset from official Department of Financial "
                "Services information, last verified on August 10, 2026."
            ),
        }

    scheme_info = SCHEMES_DATA[scheme_code]
    source_url = scheme_info["official_source"]

    # 1. PMJJBY Evaluation
    if scheme_code == "PMJJBY":
        if age is None:
            return {
                "status": "insufficient_information",
                "scheme": scheme_info["scheme_code"],
                "scheme_full_name": scheme_info["scheme_full_name"],
                "reason": "Age is required to check eligibility for PMJJBY (entry age: 18-50 years).",
                "missing_fields": ["age"],
                "official_source": source_url,
                "last_verified": LAST_VERIFIED_DATE,
                "disclaimer": (
                    "This result is based on a locally curated dataset from official Department of Financial "
                    "Services information, last verified on August 10, 2026."
                ),
            }

        if age < 18 or age > 50:
            return {
                "status": "does_not_meet_criteria",
                "scheme": scheme_info["scheme_code"],
                "scheme_full_name": scheme_info["scheme_full_name"],
                "reason": f"Entry age for PMJJBY is 18 to 50 years. Provided age ({age}) is outside this range.",
                "key_details": {
                    "age_range": "18-50 years",
                    "premium": scheme_info["annual_premium"],
                    "cover": scheme_info["coverage"],
                },
                "official_source": source_url,
                "last_verified": LAST_VERIFIED_DATE,
                "disclaimer": (
                    "This result is based on a locally curated dataset from official Department of Financial "
                    "Services information, last verified on August 10, 2026."
                ),
            }

        if has_bank_or_post_office_account is False:
            return {
                "status": "does_not_meet_criteria",
                "scheme": scheme_info["scheme_code"],
                "scheme_full_name": scheme_info["scheme_full_name"],
                "reason": "PMJJBY requires an individual savings account in a participating bank or Post Office with auto-debit consent.",
                "key_details": {
                    "age_range": "18-50 years",
                    "account_requirement": scheme_info["account_requirement"],
                    "premium": scheme_info["annual_premium"],
                    "cover": scheme_info["coverage"],
                },
                "official_source": source_url,
                "last_verified": LAST_VERIFIED_DATE,
                "disclaimer": (
                    "This result is based on a locally curated dataset from official Department of Financial "
                    "Services information, last verified on August 10, 2026."
                ),
            }

        return {
            "status": "potential_match",
            "scheme": scheme_info["scheme_code"],
            "scheme_full_name": scheme_info["scheme_full_name"],
            "reason": "Based on the information provided, you may meet the basic age (18-50) and bank account criteria for PMJJBY.",
            "key_details": {
                "age_range": "18-50 years",
                "premium": scheme_info["annual_premium"],
                "cover": scheme_info["coverage"],
                "account_requirement": scheme_info["account_requirement"],
            },
            "official_source": source_url,
            "last_verified": LAST_VERIFIED_DATE,
            "disclaimer": (
                "This result is based on a locally curated dataset from official Department of Financial "
                "Services information, last verified on August 10, 2026. It is a basic informational check "
                "and not a guaranteed official decision. Please verify exact terms with your bank or the official website before applying."
            ),
        }

    # 2. PMSBY Evaluation
    if scheme_code == "PMSBY":
        if age is None:
            return {
                "status": "insufficient_information",
                "scheme": scheme_info["scheme_code"],
                "scheme_full_name": scheme_info["scheme_full_name"],
                "reason": "Age is required to check eligibility for PMSBY (entry age: 18-70 years).",
                "missing_fields": ["age"],
                "official_source": source_url,
                "last_verified": LAST_VERIFIED_DATE,
                "disclaimer": (
                    "This result is based on a locally curated dataset from official Department of Financial "
                    "Services information, last verified on August 10, 2026."
                ),
            }

        if age < 18 or age > 70:
            return {
                "status": "does_not_meet_criteria",
                "scheme": scheme_info["scheme_code"],
                "scheme_full_name": scheme_info["scheme_full_name"],
                "reason": f"Entry age for PMSBY is 18 to 70 years. Provided age ({age}) is outside this range.",
                "key_details": {
                    "age_range": "18-70 years",
                    "premium": scheme_info["annual_premium"],
                    "cover": scheme_info["coverage"],
                },
                "official_source": source_url,
                "last_verified": LAST_VERIFIED_DATE,
                "disclaimer": (
                    "This result is based on a locally curated dataset from official Department of Financial "
                    "Services information, last verified on August 10, 2026."
                ),
            }

        if has_bank_or_post_office_account is False:
            return {
                "status": "does_not_meet_criteria",
                "scheme": scheme_info["scheme_code"],
                "scheme_full_name": scheme_info["scheme_full_name"],
                "reason": "PMSBY requires an individual savings account in a participating bank or Post Office with auto-debit consent.",
                "key_details": {
                    "age_range": "18-70 years",
                    "account_requirement": scheme_info["account_requirement"],
                    "premium": scheme_info["annual_premium"],
                    "cover": scheme_info["coverage"],
                },
                "official_source": source_url,
                "last_verified": LAST_VERIFIED_DATE,
                "disclaimer": (
                    "This result is based on a locally curated dataset from official Department of Financial "
                    "Services information, last verified on August 10, 2026."
                ),
            }

        return {
            "status": "potential_match",
            "scheme": scheme_info["scheme_code"],
            "scheme_full_name": scheme_info["scheme_full_name"],
            "reason": "Based on the information provided, you may meet the basic age (18-70) and bank account criteria for PMSBY.",
            "key_details": {
                "age_range": "18-70 years",
                "premium": scheme_info["annual_premium"],
                "cover": scheme_info["coverage"],
                "account_requirement": scheme_info["account_requirement"],
            },
            "official_source": source_url,
            "last_verified": LAST_VERIFIED_DATE,
            "disclaimer": (
                "This result is based on a locally curated dataset from official Department of Financial "
                "Services information, last verified on August 10, 2026. It is a basic informational check "
                "and not a guaranteed official decision. Please verify exact terms with your bank or the official website before applying."
            ),
        }

    # 3. PMJDY Evaluation (Unbanked / Financial Inclusion focus)
    if scheme_code == "PMJDY":
        if is_unbanked is False or has_bank_or_post_office_account is True:
            # User already has a bank account; PMJDY is primarily for unbanked individuals seeking basic account
            return {
                "status": "potential_match",
                "scheme": scheme_info["scheme_code"],
                "scheme_full_name": scheme_info["scheme_full_name"],
                "reason": "PMJDY focuses on providing basic savings banking (BSBD) accounts for unbanked individuals. If you already have a bank account, you may already have basic banking facilities, but you can check BSBD terms at your branch.",
                "key_details": {
                    "target_audience": "Unbanked persons seeking basic banking access",
                    "minimum_balance": "₹0 (Zero minimum balance)",
                    "card": "Free RuPay Debit Card with accidental insurance cover",
                    "overdraft": "Up to ₹10,000 overdraft facility subject to eligibility conditions",
                },
                "official_source": source_url,
                "last_verified": LAST_VERIFIED_DATE,
                "disclaimer": (
                    "This result is based on a locally curated dataset from official Department of Financial "
                    "Services information, last verified on August 10, 2026. It is a basic informational check "
                    "and not a guaranteed official decision. Please check official terms before applying."
                ),
            }

        return {
            "status": "potential_match",
            "scheme": scheme_info["scheme_code"],
            "scheme_full_name": scheme_info["scheme_full_name"],
            "reason": "Based on the information provided, you may meet the basic criteria for PMJDY as an unbanked individual seeking access to basic banking services.",
            "key_details": {
                "minimum_balance": "₹0 (Zero minimum balance)",
                "card": "Free RuPay Debit Card with accidental insurance cover",
                "overdraft": "Up to ₹10,000 overdraft facility subject to eligibility conditions",
                "account_type": "Basic Savings Bank Deposit (BSBD) Account",
            },
            "official_source": source_url,
            "last_verified": LAST_VERIFIED_DATE,
            "disclaimer": (
                "This result is based on a locally curated dataset from official Department of Financial "
                "Services information, last verified on August 10, 2026. It is a basic informational check "
                "and not a guaranteed official decision. Please verify exact terms at any bank branch before applying."
            ),
        }

    return {
        "status": "insufficient_information",
        "scheme": scheme_code,
        "reason": "Could not evaluate eligibility with provided inputs.",
        "official_source": OFFICIAL_SOURCES["DFS_PORTAL"],
        "last_verified": LAST_VERIFIED_DATE,
        "disclaimer": (
            "This result is based on a locally curated dataset from official Department of Financial "
            "Services information, last verified on August 10, 2026."
        ),
    }
