import json
import logging

from dotenv import load_dotenv
from livekit import rtc
from livekit.agents import (
    Agent,
    AgentServer,
    AgentSession,
    APIConnectOptions,
    JobContext,
    JobProcess,
    RunContext,
    cli,
    function_tool,
    room_io,
    tokenize,
)
from livekit.agents.voice.agent_session import SessionConnectOptions
from livekit.plugins import deepgram, google, murf, noise_cancellation, silero
from livekit.plugins.turn_detector.multilingual import MultilingualModel

from memory import db_delete_user, db_lookup_user, db_save_user
from schemes_data import LAST_VERIFIED_DATE, evaluate_scheme_eligibility

logger = logging.getLogger("agent")

load_dotenv(".env.local")

SYSTEM_PROMPT = """1. IDENTITY
- Name: Jan Sathi (जन साथी)
- Role: AI voice assistant for Indian financial awareness.
- Purpose: Help users understand government schemes, banking, digital payments, financial literacy, and cyber safety.
- Personality: Warm, friendly, patient, respectful, trustworthy, and conversational.

2. OBJECTIVES
A successful conversation should:
- Explain government financial schemes simply and clearly.
- Help users understand eligibility, benefits, documents, and application process.
- Promote safe digital banking and fraud awareness.
- Give clear, practical next steps whenever possible.

3. KNOWLEDGE
The assistant knows about:
- PMJDY (Pradhan Mantri Jan Dhan Yojana)
- PMJJBY (Pradhan Mantri Jeevan Jyoti Bima Yojana)
- PMSBY (Pradhan Mantri Suraksha Bima Yojana)
- APY (Atal Pension Yojana)
- Sukanya Samriddhi Yojana
- UPI, Digital Payments, Mobile Banking, ATM usage
- RBI & NPCI guidelines, Financial literacy, Credit scores, Loan EMIs, Fixed Deposits

The assistant does NOT know:
- Personal bank account details, balances, or transaction history
- Government application status or loan approval decisions
- Private customer records

Whenever information may have changed, advise users to verify through official government websites or their bank.

4. CRITICAL — DEVANAGARI SCRIPT & CONVERSATIONAL HINDI (APPLIES TO ALL TURNS)
This is a voice agent. The TTS performs best when Hindi words are written in DEVANAGARI SCRIPT.

- MANDATORY DEVANAGARI SCRIPT RULE:
  * ALWAYS write all Hindi words in Devanagari script (हिंदी लिपि).
  * NEVER write Hindi words in Romanized/Latin characters (e.g. NEVER write "aap kaise hain", "aapki financial history", "mujhe bataiye", "kya aap...").
  * Common English financial terms can remain in English script or phonetic script when natural (e.g. loan, EMI, credit score, bank, interest, savings, investment, insurance, UPI, SIP, summary, manage).

- EXPLICIT EXAMPLES:
  * BAD (Romanized Hindi - FORBIDDEN):
    "Credit score basically aapki financial history ka ek summary hota hai."
  * BAD (Overly Formal/Literary Hindi - FORBIDDEN):
    "क्रेडिट स्कोर आपके वित्तीय इतिहास का एक महत्वपूर्ण संकेतक है।"
  * GOOD (Natural Conversational Hindi in Devanagari with English terms):
    "क्रेडिट स्कोर आपकी फाइनेंशियल हिस्ट्री का एक तरह का summary होता है। इससे banks को अंदाज़ा मिलता है कि आपने अपने loan और credit card को कितनी अच्छी तरह manage किया है।"

  * BAD (Formal/Literary Hindi):
    "ऋण लेने से पूर्व ब्याज दर एवं मासिक किस्त की समीक्षा करना आवश्यक है।"
  * GOOD (Natural Spoken Hindi):
    "Loan लेने से पहले interest rate और EMI दोनों अच्छी तरह check कर लें।"

  * BAD (Formal/Literary Hindi):
    "यदि आप नियमित रूप से अपनी मासिक किस्तों का समय पर भुगतान करते हैं, तो आपकी ऋण पात्रता में सुधार हो सकता है।"
  * GOOD (Natural Spoken Hindi):
    "अगर आप regularly अपनी EMI टाइम पर pay करते हैं, तो आपका credit score बेहतर हो सकता है।"

- CONSISTENCY ON EVERY TURN:
  * Apply this Devanagari script rule on EVERY turn (1st, 2nd, 3rd, 4th, and all subsequent responses).
  * NEVER switch to Romanized Hindi or formal bookish Hindi on later turns.
  * Before generating every response, verify: Are all Hindi words written in Devanagari? Is the sentence short (2-4 sentences max) and natural for TTS speech?

5. GUARDRAILS
The assistant MUST NEVER:
- Ask for OTP, PIN, passwords, CVV, or debit/credit card numbers
- Claim to access bank databases or guarantee loan approvals
- Invent eligibility criteria, benefits, or deadlines

If asked to verify an account, check application status, approve a loan, or access personal records, politely refuse and say:
"मैं आपके व्यक्तिगत बैंक खातों या सरकारी रिकॉर्ड्स को एक्सेस नहीं कर सकता। कृपया अपनी बैंक ब्रांच, कस्टमर केयर या आधिकारिक सरकारी पोर्टल से संपर्क करें।"

If users share sensitive information like OTP or PIN, immediately tell them not to share it and explain why:
"कृपया अपना OTP, PIN, CVV, या कोई भी गोपनीय जानकारी किसी के साथ share न करें — यहाँ तक कि मेरे साथ भी नहीं। असली bank या सरकारी agent कभी यह नहीं माँगते।"

6. VOICE & SPOKEN RESPONSE STYLE
- Keep responses short (2-4 spoken sentences max per turn). Avoid long paragraphs.
- Avoid markdown, formatting symbols, bullets, or emojis.
- Speak warmly and clearly with natural pauses between ideas.
- If the user is silent for several seconds, politely ask whether they are still there.

7. FIRST TURN GREETING — MEMORY-AWARE (DAY 4)
Check the CURRENT USER MEMORY CONTEXT section at the end of these instructions:

  If existing record is Found (returning caller):
    Greet them warmly by name and naturally mention relevant past topics.
    Example: "नमस्ते राहुल! आपको फिर से सुनकर अच्छा लगा। पिछली बार हमने PM-KISAN की eligibility के बारे में बात की थी। क्या आप वहीं से आगे बढ़ना चाहेंगे, या कोई नया सवाल है?"
    DO NOT say: "I found your database record" or "According to my records".
    Speak as if you simply remember from your last conversation.

  If no record is found (new caller):
    Greet as a new user and ask their name:
    "नमस्ते! मैं जन साथी हूँ। मैं सरकारी योजनाओं, बैंकिंग, UPI payments और वित्तीय सुरक्षा से जुड़े आपके सवालों में मदद करने के लिए यहाँ हूँ। आपका नाम क्या है?"

8. MEMORY RULES (MANDATORY — DAY 4)

LOOKUP:
  Memory is automatically loaded at connection time from the participant identity into system instructions.

PERMISSION BEFORE SAVING — HARD REQUIREMENT:
  Before calling save_user_memory, you MUST:
  1. Tell the user specifically what you want to remember.
  2. Ask for explicit permission.

  Example:
  "मैं आपका नाम 'राहुल' और यह जानकारी कि आपने PM-KISAN की eligibility check की थी, अगली बातचीत के लिए याद रख सकता हूँ। क्या आप चाहते हैं कि मैं इसे save करूँ?"

  - If YES → call save_user_memory with user_confirmed=True
  - If NO → do NOT call save_user_memory. Do not ask again for the same information.
  - If unclear → ask once more politely, then respect their answer.

WHAT TO SAVE (approved fields only):
  - Name
  - Language preference
  - Government schemes the user asked about (e.g., PM-KISAN, PMJDY, APY)
  - Eligibility questions and answers
  - Financial topics discussed

WHAT TO NEVER SAVE OR REQUEST:
  - OTP, PIN, UPI PIN, CVV, card numbers
  - Bank account numbers, IFSC codes
  - Aadhaar number, PAN number
  - Passwords, passcodes, security answers
  If a user volunteers any of the above, warn them immediately and do not save anything.

FORGET REQUEST:
  If the user explicitly asks Jan Sathi to forget them or delete their information,
  ask for confirmation, then call delete_user_memory with user_confirmed=True.

9. DAY 5 SCHEME ELIGIBILITY TOOL RULES (check_financial_scheme_eligibility)

WHEN TO CALL:
- Call check_financial_scheme_eligibility ONLY when the user asks whether they qualify for, fit the basic criteria for, or should consider one of the supported financial schemes (PMJJBY, PMSBY, PMJDY).
- Examples requiring the tool:
  * "I'm 25 years old and have a bank account. Could I be eligible for PMJJBY?"
  * "Can I get PMSBY accident insurance if I am 60 years old?"
  * "Am I eligible for Jan Dhan Yojana if I don't have a bank account?"
- Examples NOT requiring the tool:
  * "What is insurance?"
  * "What is PMJJBY?"
  * "What is UPI?"
  * Answer generic informational questions directly without invoking check_financial_scheme_eligibility unless an eligibility check is explicitly requested.

CONVERSATIONAL INPUT COLLECTION:
- The tool requires basic inputs (e.g. age for PMJJBY/PMSBY, bank account status).
- If required information (like age) is missing, ask for it naturally before calling the tool.
- If age or bank account status was already provided in the current conversation or from approved Day 4 memory, use it directly without re-asking.
- NEVER ask for sensitive financial credentials (Aadhaar, PAN, account numbers, PIN, OTP, passwords).

NATURAL SPOKEN RESPONSE FORMATTING:
- NEVER read raw JSON or dict outputs to the user.
- Explain the returned result naturally and concisely.
- For potential matches, state: "Based on the information provided, you appear to meet the basic criteria for..." (never state it as a guaranteed official decision).
- MANDATORY TRANSPARENCY: Always mention the verification date and local dataset source in natural phrasing:
  "This result is based on a locally curated dataset from official Department of Financial Services information, last verified on August 10, 2026."
- Recommend checking with their bank branch or official website before applying.

FAILURE PATH HANDLING:
- If the tool returns a status of "error", do NOT guess or hallucinate eligibility.
- Say clearly: "I'm sorry, I couldn't access the scheme eligibility information right now, so I don't want to guess. Please try again shortly or check the official government source."
"""

OUTBOUND_SYSTEM_PROMPT = """

11. OUTBOUND CALL INSTRUCTIONS (DAY 6 — PMJJBY SCHEME INFORMATION & REMINDER CALL)
You are placing an outbound phone call to a recipient regarding government financial/insurance schemes.

MANDATORY FIRST TURN OPENING (APPLIES IMMEDIATELY WHEN CALL CONNECTS):
Your VERY FIRST turn MUST state:
1. Who is calling: "Hello! This is Jan Sathi, an automated financial-services assistant."
2. Why you are calling: "I'm calling to follow up on information you previously checked about a government insurance scheme such as PMJJBY."
3. How to opt out: "If you don't want to receive calls like this, just say 'stop' and I'll end the call."

Combine these 3 mandatory elements smoothly into your initial spoken greeting.

STRICT INFORMATION & REMINDER RULES:
- Do NOT claim that the recipient is definitely enrolled, definitely eligible, or that their renewal is due unless explicitly present in approved Day 4 memory.
- Provide general PMJJBY information from the dataset:
  * Premium: ₹436 annual premium
  * Coverage: ₹2 lakh life cover (death due to any cause)
  * Account requirement: Individual savings account in a participating bank or Post Office with auto-debit consent
  * How to enroll: Visit an appropriate participating bank branch or official portal to verify terms and apply.
- Do NOT invent personalized renewal status or fake account decisions.

OPT-OUT PROCEDURE:
- When the recipient says "stop", "don't call me", "opt out", "end call", or "रोकें":
  1. Immediately invoke the end_call_and_opt_out function tool.
  2. Say: "Understood. I won't continue this call. Thank you, and have a good day."
  3. The tool will disconnect the call cleanly.
"""




class Assistant(Agent):
    """Jan Sathi voice agent with persistent memory (Day 4).

    The user_id is NEVER accepted from the LLM. It is derived exclusively from
    the LiveKit participant identity and injected via set_user_id() after the
    room connection is established (safeguard 3).
    """

    def __init__(self) -> None:
        super().__init__(instructions=SYSTEM_PROMPT)
        # Set by my_agent() after ctx.connect() from LiveKit context — not from LLM.
        self._user_id: str | None = None
        self._prewarmed_memory: dict | None = None
        self._room: rtc.Room | None = None
        self._is_outbound: bool = False

    def set_room(self, room: rtc.Room) -> None:
        """Store the LiveKit room instance for session control (e.g. clean disconnect on opt-out)."""
        self._room = room

    async def enable_outbound_mode(self) -> None:
        """Enable Day 6 outbound prompt rules for phone call sessions."""
        self._is_outbound = True
        base_inst = self._instructions if hasattr(self, "_instructions") else SYSTEM_PROMPT
        await self.update_instructions(base_inst + OUTBOUND_SYSTEM_PROMPT)


    async def set_user_id(self, user_id: str) -> None:
        """Inject the LiveKit participant identity as the memory key.

        Called by my_agent() after ctx.connect(). The value comes from
        ctx.room.remote_participants — never from any LLM-controlled input.
        Pre-warms the user memory from SQLite and updates instructions directly.
        """
        self._user_id = user_id
        self._prewarmed_memory = db_lookup_user(user_id)
        if self._prewarmed_memory:
            logger.info("Memory pre-warmed for user_id=%.8s... (name='%s')", user_id, self._prewarmed_memory.get("name"))
            memory_summary = (
                f"\n\n10. CURRENT USER MEMORY CONTEXT:\n"
                f"- Found existing record: Yes\n"
                f"- User Name: {self._prewarmed_memory.get('name')}\n"
                f"- Preferred Language: {self._prewarmed_memory.get('language_pref')}\n"
                f"- Saved Facts: {json.dumps(self._prewarmed_memory.get('facts', {}), ensure_ascii=False)}\n"
                f"- Last interaction: {self._prewarmed_memory.get('last_interaction')}\n"
            )
        else:
            logger.info("Memory context: participant identity set (%.8s...), no existing record", user_id)
            memory_summary = (
                f"\n\n10. CURRENT USER MEMORY CONTEXT:\n"
                f"- Found existing record: No (new caller).\n"
            )
        
        base_inst = SYSTEM_PROMPT + OUTBOUND_SYSTEM_PROMPT if self._is_outbound else SYSTEM_PROMPT
        await self.update_instructions(base_inst + memory_summary)


    # ------------------------------------------------------------------
    # MEMORY TOOLS (Day 4)
    # ------------------------------------------------------------------

    @function_tool
    async def lookup_user_memory(self, context: RunContext) -> str:
        """Look up memory for the current caller from the persistent database.

        Call this at the very start of every conversation to check whether the
        caller is known. Returns whether the user exists, their name, language
        preference, saved financial facts, and when they last called.

        The user_id is derived from the LiveKit participant identity — it is NOT
        supplied by the LLM (safeguard 3).
        """
        if not self._user_id:
            logger.warning("lookup_user_memory: user_id not set — treating as new user")
            return json.dumps({"found": False, "reason": "user identity not available"})

        record = self._prewarmed_memory if self._prewarmed_memory is not None else db_lookup_user(self._user_id)

        if record is None:
            logger.info("lookup_user_memory: new user (%.8s...)", self._user_id)
            return json.dumps({"found": False})

        logger.info("lookup_user_memory: returning user (%.8s...)", self._user_id)
        return json.dumps(
            {
                "found": True,
                "name": record["name"],
                "language_preference": record["language_pref"],
                "facts": record["facts"],
                "last_interaction": record["last_interaction"],
            }
        )

    @function_tool
    async def save_user_memory(
        self,
        context: RunContext,
        user_confirmed: bool,
        name: str | None = None,
        language_preference: str | None = None,
        schemes_checked: list[str] | None = None,
        eligibility_answers: dict[str, str] | None = None,
        topics_asked: list[str] | None = None,
    ) -> str:
        """Save or update memory for the current caller.

        SAFEGUARD 1 — EXPLICIT CONSENT REQUIRED:
        This function will REFUSE to save if user_confirmed is not True.
        Only call this after the user has explicitly agreed (said yes) to saving.
        If user said no or is unclear, pass user_confirmed=False (or do not call).

        SAFEGUARD 2 — ALLOWLIST FIELDS ONLY:
        Only the parameters listed below are stored. Any sensitive data
        (OTP, PIN, CVV, Aadhaar, PAN, card/account numbers, passwords) is
        rejected at the storage layer regardless of what is passed here.

        SAFEGUARD 3 — user_id from LiveKit:
        The user_id is derived from the LiveKit participant identity, not from
        any parameter supplied by the LLM.

        Args:
            user_confirmed: MUST be True. User has explicitly agreed to save.
                            If False, this function refuses and returns an error.
            name: User's first name (e.g. "Rahul"). Never an ID number.
            language_preference: Preferred language code: 'hi', 'en', 'hinglish'.
            schemes_checked: Government schemes the user asked about this session
                             (e.g. ["PM-KISAN", "PMJDY"]).
            eligibility_answers: Key-value pairs from eligibility questions
                                 (e.g. {"age": "35", "has_bank_account": "yes"}).
            topics_asked: Financial topics discussed (e.g. ["credit score", "EMI"]).
        """
        # ── Safeguard 1: explicit consent required at function level ──────────
        if not user_confirmed:
            logger.info("save_user_memory: refused — user_confirmed=False")
            return (
                "Save cancelled: the user has not explicitly confirmed. "
                "Do NOT save any information without consent."
            )

        # ── Safeguard 3: user_id from LiveKit context only ────────────────────
        if not self._user_id:
            logger.warning("save_user_memory: user_id not set")
            return "Cannot save: user identity is not available for this session."

        # ── Load existing record to merge facts ───────────────────────────────
        existing = db_lookup_user(self._user_id)
        existing_facts: dict = existing["facts"] if existing else {}

        # ── Merge only approved fact keys (safeguard 2 enforced in memory.py) ─
        merged_facts: dict = {
            "schemes_checked": list(existing_facts.get("schemes_checked", [])),
            "eligibility_answers": dict(existing_facts.get("eligibility_answers", {})),
            "topics_asked": list(existing_facts.get("topics_asked", [])),
        }

        if schemes_checked:
            merged_facts["schemes_checked"] = list(
                set(merged_facts["schemes_checked"]) | set(schemes_checked)
            )
        if eligibility_answers:
            merged_facts["eligibility_answers"].update(eligibility_answers)
        if topics_asked:
            merged_facts["topics_asked"] = list(
                set(merged_facts["topics_asked"]) | set(topics_asked)
            )

        resolved_name = name or (existing["name"] if existing else None)
        resolved_lang = language_preference or (existing["language_pref"] if existing else "hi")

        # ── Persist (storage layer strips any non-approved keys) ─────────────
        db_save_user(
            user_id=self._user_id,
            name=resolved_name,
            language_pref=resolved_lang,
            facts=merged_facts,
        )
        self._prewarmed_memory = db_lookup_user(self._user_id)

        saved_parts = []
        if resolved_name:
            saved_parts.append(f"name='{resolved_name}'")
        if language_preference:
            saved_parts.append(f"language='{resolved_lang}'")
        if schemes_checked:
            saved_parts.append(f"schemes={schemes_checked}")
        if eligibility_answers:
            saved_parts.append(f"eligibility_answers={list(eligibility_answers.keys())}")
        if topics_asked:
            saved_parts.append(f"topics={topics_asked}")

        summary = ", ".join(saved_parts) if saved_parts else "no new fields"
        logger.info("save_user_memory: saved for %.8s... (%s)", self._user_id, summary)
        return f"Memory saved successfully. Stored: {summary}."

    @function_tool
    async def delete_user_memory(self, context: RunContext, user_confirmed: bool) -> str:
        """Permanently delete all saved memory for the current caller.

        Call this ONLY when the user explicitly asks Jan Sathi to forget them
        or delete their saved information.

        Args:
            user_confirmed: MUST be True. The user has explicitly confirmed deletion.
        """
        if not user_confirmed:
            return "Deletion cancelled: explicit user confirmation is required."

        if not self._user_id:
            return "Cannot delete: user identity is not available for this session."

        db_delete_user(self._user_id)
        self._prewarmed_memory = None
        logger.info("delete_user_memory: deleted record for %.8s...", self._user_id)
        return (
            "All saved information has been permanently deleted. "
            "I no longer have any memory of you — the next call will start fresh."
        )

    # ------------------------------------------------------------------
    # EXISTING FINANCIAL TOOLS (Days 1–3 — unchanged)
    # ------------------------------------------------------------------

    @function_tool
    async def calculate_loan_emi(
        self,
        context: RunContext,
        loan_amount: float,
        annual_interest_rate: float,
        tenure_years: int,
    ) -> str:
        """Calculate Loan EMI (Equated Monthly Installment), total interest, and total amount payable.

        Args:
            loan_amount: Total principal loan amount in INR (e.g. 500000 for 5 Lakhs).
            annual_interest_rate: Annual interest rate as a percentage (e.g. 8.5 for 8.5%).
            tenure_years: Loan duration in years (e.g. 5 for 5 years).
        """
        logger.info(
            f"Calculating EMI for amount: {loan_amount}, rate: {annual_interest_rate}%, tenure: {tenure_years} years"
        )
        monthly_rate = annual_interest_rate / (12 * 100)
        months = tenure_years * 12
        if monthly_rate == 0:
            emi = loan_amount / months
        else:
            emi = (loan_amount * monthly_rate * ((1 + monthly_rate) ** months)) / (
                ((1 + monthly_rate) ** months) - 1
            )
        total_payment = emi * months
        total_interest = total_payment - loan_amount
        return (
            f"For a loan of ₹{loan_amount:,.2f} at {annual_interest_rate}% interest for {tenure_years} years: "
            f"Monthly EMI is ₹{emi:,.2f}, total interest payable is ₹{total_interest:,.2f}, and total payment is ₹{total_payment:,.2f}."
        )

    @function_tool
    async def calculate_fd_returns(
        self,
        context: RunContext,
        principal: float,
        annual_interest_rate: float,
        tenure_years: float,
    ) -> str:
        """Calculate Fixed Deposit (FD) returns and interest earned.

        Args:
            principal: Investment principal amount in INR (e.g. 100000).
            annual_interest_rate: Annual interest rate percentage (e.g. 7.0 for 7%).
            tenure_years: Duration of FD in years (e.g. 1 or 2.5).
        """
        logger.info(
            f"Calculating FD for principal: {principal}, rate: {annual_interest_rate}%, tenure: {tenure_years} years"
        )
        n = 4
        rate_decimal = annual_interest_rate / 100
        maturity_amount = principal * ((1 + rate_decimal / n) ** (n * tenure_years))
        interest_earned = maturity_amount - principal
        return (
            f"For a Fixed Deposit of ₹{principal:,.2f} at {annual_interest_rate}% per annum for {tenure_years} years: "
            f"Estimated Maturity Amount is ₹{maturity_amount:,.2f} with total interest earned of ₹{interest_earned:,.2f}."
        )

    @function_tool
    async def check_financial_scheme_eligibility(
        self,
        context: RunContext,
        scheme_name: str | None = None,
        category_of_interest: str | None = None,
        age: int | None = None,
        has_bank_or_post_office_account: bool | None = None,
        is_unbanked: bool | None = None,
        simulate_failure: bool = False,
    ) -> str:
        """Check potential basic eligibility for Indian government financial schemes (PMJJBY, PMSBY, PMJDY).

        CALL THIS TOOL ONLY when the user explicitly asks whether they qualify for, fit basic criteria for,
        or should consider a supported scheme (PMJJBY life insurance, PMSBY accident insurance, PMJDY basic banking).

        DO NOT call this tool for generic informational questions like 'What is PMJJBY?', 'What is insurance?', or 'What is UPI?'.

        Args:
            scheme_name: Name of scheme if requested (e.g. "PMJJBY", "PMSBY", "PMJDY").
            category_of_interest: Category of interest if scheme name is omitted (e.g. "life_insurance", "accident_insurance", "basic_banking").
            age: Age of applicant in years (required for PMJJBY/PMSBY).
            has_bank_or_post_office_account: Whether the user holds an individual savings account in a participating bank or Post Office.
            is_unbanked: Whether the user is currently unbanked (relevant for PMJDY).
            simulate_failure: Internal backend test flag to trigger failure path testing.
        """
        logger.info(
            "check_financial_scheme_eligibility: scheme=%s, category=%s, age=%s, account=%s, unbanked=%s, simulate_failure=%s",
            scheme_name,
            category_of_interest,
            age,
            has_bank_or_post_office_account,
            is_unbanked,
            simulate_failure,
        )

        try:
            if simulate_failure:
                raise RuntimeError("Simulated dataset access failure for testing error path")

            res_dict = evaluate_scheme_eligibility(
                scheme_name=scheme_name,
                category_of_interest=category_of_interest,
                age=age,
                has_bank_or_post_office_account=has_bank_or_post_office_account,
                is_unbanked=is_unbanked,
            )
            return json.dumps(res_dict, ensure_ascii=False)

        except Exception as err:
            logger.error("check_financial_scheme_eligibility failed: %s", err, exc_info=True)
            failure_dict = {
                "status": "error",
                "scheme": scheme_name or category_of_interest or "unknown",
                "reason": "Unable to access scheme eligibility dataset at this time.",
                "official_source": "https://www.financialservices.gov.in/schemes-and-services",
                "last_verified": LAST_VERIFIED_DATE,
                "disclaimer": "This system could not verify eligibility right now. Please check official government portals directly.",
            }
            return json.dumps(failure_dict, ensure_ascii=False)

    @function_tool
    async def end_call_and_opt_out(self, context: RunContext) -> str:
        """End the current phone call immediately when the recipient asks to stop, opt out, or end the call.

        Call this tool when the user says 'stop', 'don't call me', 'opt out', or 'रोकें'.
        """
        logger.info("end_call_and_opt_out: Opt-out requested by user. Scheduling call disconnect.")
        if self._room:
            import asyncio

            async def _disconnect_room():
                await asyncio.sleep(4.0)
                try:
                    await self._room.disconnect()
                    logger.info("Room disconnected cleanly following user opt-out.")
                except Exception as err:
                    logger.warning("Error disconnecting room: %s", err)

            asyncio.create_task(_disconnect_room())

        return "Understood. I won't continue this call. Thank you, and have a good day."



    @function_tool
    async def report_fraud_guidance(
        self,
        context: RunContext,
        fraud_type: str,
    ) -> str:
        """Get immediate step-by-step instructions and emergency helpline numbers for financial or cyber fraud.

        Args:
            fraud_type: Type of fraud (e.g. unexpected UPI payment request, OTP scam, unauthorized card charge, fake loan app).
        """
        logger.info(f"Providing fraud guidance for {fraud_type}")
        return (
            "Emergency Action for Financial Fraud:\n"
            "1. Immediately call National Cyber Crime Helpline at 1930 or visit cybercrime.gov.in.\n"
            "2. Block your bank card, UPI account, or mobile SIM immediately via bank customer care.\n"
            "3. Notify your bank branch within 3 days — under RBI guidelines, zero customer liability applies for timely reported unauthorized transactions.\n"
            "4. Never share OTP, UPI PIN, CVV, or passwords with anyone."
        )


class HindiSentenceTokenizer(tokenize.basic.SentenceTokenizer):
    """SentenceTokenizer extended to handle Devanagari Purna Viram ('।') sentence boundaries."""

    def stream(self, *, language: str | None = None) -> tokenize.tokenizer.SentenceStream:
        import functools

        def _split_and_clean(text: str, min_sentence_len: int = 2, retain_format: bool = False):
            modified_text = text.replace("।", "।.").replace("॥", "॥.")
            results = tokenize._basic_sent.split_sentences(
                modified_text,
                min_sentence_len=min_sentence_len,
                retain_format=retain_format,
            )
            cleaned = []
            for sent, start, end in results:
                cleaned.append((sent.replace("।.", "।").replace("॥.", "॥"), start, end))
            return cleaned

        return tokenize.token_stream.BufferedSentenceStream(
            tokenizer=functools.partial(
                _split_and_clean,
                min_sentence_len=self._config.min_sentence_len,
                retain_format=self._config.retain_format,
            ),
            min_token_len=self._config.min_sentence_len,
            min_ctx_len=self._config.stream_context_len,
        )


server = AgentServer(num_idle_processes=1)


def prewarm(proc: JobProcess):
    proc.userdata["vad"] = silero.VAD.load()


server.setup_fnc = prewarm


@server.rtc_session(agent_name="my-agent")
async def my_agent(ctx: JobContext):
    # Logging setup
    ctx.log_context_fields = {
        "room": ctx.room.name,
    }

    # Create the assistant instance before session.start() so we can set the
    # user_id after ctx.connect() (safeguard 3: user_id from LiveKit context).
    assistant = Assistant()
    assistant.set_room(ctx.room)

    # Set up a voice AI pipeline using Murf Falcon, Gemini, Deepgram, and the LiveKit turn detector
    session = AgentSession(
        # Speech-to-text (STT) is your agent's ears
        stt=deepgram.STT(model="nova-3"),
        # Large Language Model (LLM) using active gemini-3.5-flash-lite
        llm=google.LLM(
            model="gemini-3.5-flash-lite",
            temperature=0,
        ),
        # Text-to-speech (TTS) is your agent's voice (Murf Falcon)
        tts=murf.TTS(
            voice="pooja",
            locale="en-IN",
            style="Conversation",
            tokenizer=HindiSentenceTokenizer(min_sentence_len=2),
            text_pacing=True,
            min_buffer_size=5,
        ),
        # VAD and turn detection
        turn_detection=MultilingualModel(),
        vad=ctx.proc.userdata["vad"],
        preemptive_generation=False,
        # Allow agent to retry TTS and LLM more aggressively on transient failures
        allow_interruptions=True,
        # Faster turn detection (snappier response start after user stops speaking)
        min_endpointing_delay=0.3,
        max_endpointing_delay=3.0,
        # Retry failed LLM/TTS/STT calls quickly instead of default 2s wait
        conn_options=SessionConnectOptions(
            llm_conn_options=APIConnectOptions(
                max_retry=5,
                retry_interval=0.5,
                timeout=15.0,
            ),
            tts_conn_options=APIConnectOptions(
                max_retry=5,
                retry_interval=0.5,
                timeout=15.0,
            ),
            stt_conn_options=APIConnectOptions(
                max_retry=5,
                retry_interval=0.5,
                timeout=15.0,
            ),
        ),
    )

    # Start the session, initializing the voice pipeline with standard WebRTC audio
    await session.start(
        agent=assistant,
        room=ctx.room,
    )

    # Join the room and connect to the user
    await ctx.connect()

    # ── Safeguard 3: Derive user_id from LiveKit participant identity ─────────
    # The user joined before the agent was dispatched, so remote_participants
    # should already contain the caller's entry at this point.
    user_id: str | None = next(
        (p.identity for p in ctx.room.remote_participants.values() if p.identity),
        None,
    )

    if user_id:
        logger.info(
            "LiveKit participant identity will be used as memory key (%.8s...)", user_id
        )
        await assistant.set_user_id(user_id)
    else:
        logger.warning(
            "No remote participant identity found — memory tools inactive for this session"
        )

    # ── Day 6: Outbound Session Detection & Auto-Greeting ────────────────────
    is_outbound = any(
        p.kind == rtc.ParticipantKind.PARTICIPANT_KIND_SIP
        or p.attributes.get("call_type") == "outbound"
        for p in ctx.room.remote_participants.values()
    ) or "outbound" in ctx.room.name.lower()

    if is_outbound:
        logger.info("Outbound call session detected (room=%s) — enabling Day 6 outbound prompt & greeting", ctx.room.name)
        await assistant.enable_outbound_mode()
        await session.generate_reply()



if __name__ == "__main__":
    cli.run_app(server)
