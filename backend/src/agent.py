import json
import logging
import uuid

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
    llm,
    tokenize,
)
from livekit.agents.voice.agent_session import SessionConnectOptions
from livekit.plugins import deepgram, google, murf, silero
from livekit.plugins.turn_detector.multilingual import MultilingualModel

from memory import (
    db_create_escalation,
    db_delete_user,
    db_end_call,
    db_lookup_user,
    db_mark_call_success,
    db_save_user,
    db_start_call,
)
from prompt import SCHEME_SPECIALIST_SYSTEM_PROMPT as BASE_SCHEME_SPECIALIST_PROMPT
from schemes_data import (
    LAST_VERIFIED_DATE,
    OFFICIAL_SOURCES,
    SCHEMES_DATA,
    evaluate_scheme_eligibility,
    normalize_scheme_input,
)

logger = logging.getLogger("agent")

load_dotenv(".env.local")

SYSTEM_PROMPT = """1. IDENTITY
- Name: Jan Sathi (जन साथी)
- Role: AI voice assistant for Indian financial awareness.
- Purpose: Help users understand banking, digital payments, financial literacy, loan calculations, cyber safety, and general financial awareness.
- Personality: Warm, friendly, patient, respectful, trustworthy, and conversational.

2. OBJECTIVES
A successful conversation should:
- Explain general banking, digital payments (UPI, ATM, Mobile Banking), credit scores, and financial literacy clearly.
- Calculate loan EMIs and fixed deposit returns accurately.
- Promote safe digital banking and cyber fraud awareness.
- Hand off detailed government scheme questions to the specialized Government Scheme Specialist.
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
- For detailed scheme questions, you can also transfer to the Government Scheme Specialist using transfer_to_scheme_specialist.

10. DAY 7 HUMAN HELP / ESCALATION RULES (create_escalation)

WHEN ESCALATION IS APPROPRIATE:
Recognize when human help is appropriate in either of these two situations:
1. Suspected Financial Fraud / Scam: User reports possible financial fraud, unauthorized transactions, fake calls, scam attempts, or suspicious UPI deductions.
2. Complex Financial Review: User requires a financial decision, official dispute handling, or assistance that Jan Sathi cannot or should not make independently and requires human review.

MANDATORY PERMISSION FLOW (STRICT REQUIREMENT):
Before creating an escalation, you MUST:
1. Explain clearly that you want to share a short summary with a human helper.
2. Ask for explicit user permission.

Example (Hindi): "मैं इस मामले का एक संक्षिप्त विवरण हमारे मानव सहायक (human helper) के साथ साझा करने के लिए help request बना सकता हूँ। क्या आपकी अनुमति है कि मैं यह request create करूँ?"
Example (English): "I can create a short summary of this issue to share with a human helper. Do I have your permission to create this escalation request?"

- If user says YES → Call `create_escalation` function tool with `user_confirmed=True`.
- If user says NO → Do NOT call `create_escalation`. Continue helping safely where possible (e.g. guide to 1930 Cyber Crime Helpline or bank card blocking). Say: "कोई बात नहीं, मैं आपकी मदद यहाँ बिना request बनाए जारी रखूँगा।"

AFTER SUCCESSFUL CREATION:
Once `create_escalation` completes and returns a Reference ID:
1. State clearly that the request has been created.
2. State the exact Reference ID returned by the tool (e.g. "आपका Reference ID है: ESC-20260812-7A9B").
3. Explain that a human helper can review the request.
4. Provide an honest next step (e.g. advise calling 1930 Cyber Crime Helpline or visiting bank branch if active fraud is suspected).
5. DO NOT promise an immediate response or a specific response time.

11. DAY 9 MULTI-AGENT HANDOFF TO GOVERNMENT SCHEME SPECIALIST (transfer_to_scheme_specialist)

WHEN TO HAND OFF:
- When the user asks detailed, in-depth questions about government welfare or financial schemes (e.g. detailed scheme rules, scheme eligibility evaluations for PMJJBY, PMSBY, PMJDY, APY, Sukanya Samriddhi, PM-KISAN, required application documents, or in-depth benefits).

MANDATORY ANNOUNCEMENT BEFORE HANDOFF:
Before or when calling `transfer_to_scheme_specialist`, you MUST clearly inform the caller:
- Hindi (Devanagari): "मैं आपको हमारे सरकारी योजना विशेषज्ञ (Government Scheme Specialist) से कनेक्ट कर रहा हूँ। वे आपको इस योजना की पूरी जानकारी और पात्रता विस्तार से समझाएंगे।"
- English: "I am connecting you to our Government Scheme Specialist. They will explain the scheme details and eligibility in depth."

WHEN NOT TO HAND OFF:
- Stay with Jan Sathi for general banking, digital payments (UPI, ATM, mobile banking), loan EMI calculations, FD return calculations, fraud/cyber security advice, memory management, and escalations.
"""

OUTBOUND_SYSTEM_PROMPT = """

12. OUTBOUND CALL INSTRUCTIONS (DAY 6 — PMJJBY SCHEME INFORMATION & REMINDER CALL)
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

SCHEME_SPECIALIST_SYSTEM_PROMPT = BASE_SCHEME_SPECIALIST_PROMPT


class GovernmentSchemeSpecialist(Agent):
    """Dedicated Government Scheme Specialist voice agent (Day 9).

    Specializes in in-depth government scheme information, eligibility evaluations,
    document requirements, and application procedures for Indian welfare & financial schemes.
    """

    def __init__(
        self,
        chat_ctx: llm.ChatContext | None = None,
        user_id: str | None = None,
        prewarmed_memory: dict | None = None,
        room: rtc.Room | None = None,
        call_id: str | None = None,
        is_outbound: bool = False,
    ) -> None:
        super().__init__(
            instructions=SCHEME_SPECIALIST_SYSTEM_PROMPT,
            chat_ctx=chat_ctx if chat_ctx is not None else None,
        )
        self._user_id: str | None = user_id
        self._prewarmed_memory: dict | None = prewarmed_memory
        self._room: rtc.Room | None = room
        self._call_id: str | None = call_id
        self._is_outbound: bool = is_outbound
        self._update_instructions_with_memory()

    def set_call_id(self, call_id: str) -> None:
        """Store unique session call_id for Day 8 call analytics tracking."""
        self._call_id = call_id

    def set_room(self, room: rtc.Room) -> None:
        """Store the LiveKit room instance for session control."""
        self._room = room

    async def set_user_id(self, user_id: str) -> None:
        """Inject the LiveKit participant identity as the memory key."""
        self._user_id = user_id
        self._prewarmed_memory = db_lookup_user(user_id)
        self._update_instructions_with_memory()
        await self.update_instructions(self._instructions)

    def _update_instructions_with_memory(self) -> None:
        """Update system instructions with caller memory context."""
        base_inst = SCHEME_SPECIALIST_SYSTEM_PROMPT
        if self._prewarmed_memory:
            memory_summary = (
                f"\n\nCURRENT USER MEMORY CONTEXT:\n"
                f"- Found existing record: Yes\n"
                f"- User Name: {self._prewarmed_memory.get('name')}\n"
                f"- Preferred Language: {self._prewarmed_memory.get('language_pref')}\n"
                f"- Saved Facts: {json.dumps(self._prewarmed_memory.get('facts', {}), ensure_ascii=False)}\n"
                f"- Last interaction: {self._prewarmed_memory.get('last_interaction')}\n"
            )
        else:
            memory_summary = "\n\nCURRENT USER MEMORY CONTEXT:\n- Found existing record: No (new caller).\n"
        self._instructions = base_inst + memory_summary

    async def on_enter(self) -> None:
        """Called when handoff to Government Scheme Specialist completes.

        Immediately generates speech so the specialist introduces itself and answers
        the pending scheme inquiry without forcing the user to repeat themselves.
        """
        logger.info(
            "GovernmentSchemeSpecialist.on_enter: Handoff complete (user_id=%.8s..., call_id=%s). Activating specialist voice response.",
            self._user_id or "unknown",
            self._call_id or "unknown",
        )
        try:
            # Trigger immediate LLM generation and spoken response from the specialist
            self.session.generate_reply()
            logger.info("GovernmentSchemeSpecialist.on_enter: session.generate_reply() queued successfully.")
        except Exception as err:
            logger.error("GovernmentSchemeSpecialist.on_enter failed to trigger generate_reply: %s", err, exc_info=True)

    # ------------------------------------------------------------------
    # SCHEME SPECIALIST TOOLS (Day 5, 7, 8, 9)
    # ------------------------------------------------------------------

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

        Args:
            scheme_name: Name of scheme if requested (e.g. "PMJJBY", "PMSBY", "PMJDY").
            category_of_interest: Category of interest if scheme name is omitted (e.g. "life_insurance", "accident_insurance", "basic_banking").
            age: Age of applicant in years (required for PMJJBY/PMSBY).
            has_bank_or_post_office_account: Whether the user holds an individual savings account in a participating bank or Post Office.
            is_unbanked: Whether the user is currently unbanked (relevant for PMJDY).
            simulate_failure: Internal backend test flag to trigger failure path testing.
        """
        logger.info(
            "GovernmentSchemeSpecialist.check_financial_scheme_eligibility: scheme=%s, category=%s, age=%s, account=%s, unbanked=%s, simulate_failure=%s",
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
            if res_dict.get("status") != "error" and self._call_id:
                db_mark_call_success(self._call_id, "eligibility_check")
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
    async def get_scheme_or_document_info(
        self,
        context: RunContext,
        scheme_name: str,
    ) -> str:
        """Get official government scheme details and required documents when a user explicitly requests scheme or document information (e.g. PMJJBY, PMSBY, PMJDY, APY, Sukanya Samriddhi).

        Args:
            scheme_name: Name or code of the requested scheme (e.g. "PMJJBY", "PMSBY", "PMJDY").
        """
        logger.info("GovernmentSchemeSpecialist.get_scheme_or_document_info requested for scheme: %s", scheme_name)
        norm_code = normalize_scheme_input(scheme_name, None) or scheme_name.upper().strip()
        data = SCHEMES_DATA.get(norm_code)

        if self._call_id:
            db_mark_call_success(self._call_id, "scheme_or_doc_info")

        if data:
            return json.dumps(
                {
                    "status": "success",
                    "scheme": data["scheme_full_name"],
                    "annual_premium": data.get("annual_premium", "N/A"),
                    "coverage": data.get("coverage", "N/A"),
                    "account_requirement": data.get("account_requirement", "N/A"),
                    "official_source": data.get("official_source", OFFICIAL_SOURCES.get("DFS_PORTAL")),
                    "last_verified": LAST_VERIFIED_DATE,
                },
                ensure_ascii=False,
            )
        else:
            return json.dumps(
                {
                    "status": "success",
                    "scheme": scheme_name,
                    "info": f"Official details for {scheme_name} can be verified on official Government portals.",
                    "official_source": OFFICIAL_SOURCES.get("DFS_PORTAL"),
                    "last_verified": LAST_VERIFIED_DATE,
                },
                ensure_ascii=False,
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
        """Save or update memory for the current caller from the Specialist."""
        if not user_confirmed:
            return "Save cancelled: explicit user confirmation is required."
        if not self._user_id:
            return "Cannot save: user identity is not available for this session."

        existing = db_lookup_user(self._user_id)
        existing_facts: dict = existing["facts"] if existing else {}

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

        db_save_user(
            user_id=self._user_id,
            name=resolved_name,
            language_pref=resolved_lang,
            facts=merged_facts,
        )
        self._prewarmed_memory = db_lookup_user(self._user_id)
        return "Memory saved successfully."

    @function_tool
    async def create_escalation(
        self,
        context: RunContext,
        user_confirmed: bool,
        what_happened: str,
        what_checked: str,
        urgency: str = "high",
        language: str = "hi",
        preferred_follow_up: str = "not specified",
    ) -> str:
        """Create a human help / escalation request record when user explicitly permits."""
        if not user_confirmed:
            return json.dumps(
                {
                    "status": "refused",
                    "reason": "Escalation cancelled: explicit user permission was not granted.",
                },
                ensure_ascii=False,
            )

        caller_name = (
            self._prewarmed_memory.get("name")
            if self._prewarmed_memory and self._prewarmed_memory.get("name")
            else "Anonymous Caller"
        )
        effective_user_id = self._user_id or "unknown_caller"

        try:
            res = db_create_escalation(
                user_id=effective_user_id,
                what_happened=what_happened,
                what_checked=what_checked,
                who_needs_help=caller_name,
                urgency=urgency,
                language=language,
                follow_up_pref=preferred_follow_up,
            )
            if res.get("reference_id") and self._call_id:
                db_mark_call_success(self._call_id, "escalation_created")
            return json.dumps(res, ensure_ascii=False)
        except Exception as err:
            logger.error("GovernmentSchemeSpecialist create_escalation error: %s", err, exc_info=True)
            return json.dumps(
                {
                    "status": "error",
                    "reason": "Could not save escalation request to database.",
                },
                ensure_ascii=False,
            )

    @function_tool
    async def transfer_to_jan_sathi(
        self,
        context: RunContext,
        reason: str = "general inquiry",
    ) -> Agent:
        """Transfer the caller back to the main Jan Sathi assistant for general banking, loan calculators, digital payments, or non-scheme questions.

        Args:
            reason: Reason for transferring back (e.g. 'loan EMI calculation', 'UPI inquiry').
        """
        logger.info("transfer_to_jan_sathi: Transferring back to main Assistant (reason=%s)", reason)
        history = (
            context.session.history.copy()
            if context and hasattr(context, "session") and context.session
            else (self.chat_ctx.copy() if hasattr(self, "chat_ctx") else None)
        )
        main_agent = Assistant(chat_ctx=history)
        main_agent._user_id = self._user_id
        main_agent._prewarmed_memory = self._prewarmed_memory
        main_agent._room = self._room
        main_agent._call_id = self._call_id
        main_agent._is_outbound = self._is_outbound
        main_agent._is_handoff_destination = True
        main_agent._update_instructions_with_memory()
        return main_agent


class Assistant(Agent):
    """Jan Sathi voice agent with persistent memory (Day 4) and multi-agent handoff (Day 9).

    The user_id is NEVER accepted from the LLM. It is derived exclusively from
    the LiveKit participant identity and injected via set_user_id() after the
    room connection is established (safeguard 3).
    """

    def __init__(self, chat_ctx: llm.ChatContext | None = None) -> None:
        super().__init__(
            instructions=SYSTEM_PROMPT,
            chat_ctx=chat_ctx if chat_ctx is not None else None,
        )
        # Set by my_agent() after ctx.connect() from LiveKit context — not from LLM.
        self._user_id: str | None = None
        self._prewarmed_memory: dict | None = None
        self._room: rtc.Room | None = None
        self._is_outbound: bool = False
        self._call_id: str | None = None
        self._is_handoff_destination: bool = False

    def set_call_id(self, call_id: str) -> None:
        """Store unique session call_id for Day 8 call analytics tracking."""
        self._call_id = call_id

    def set_room(self, room: rtc.Room) -> None:
        """Store the LiveKit room instance for session control (e.g. clean disconnect on opt-out)."""
        self._room = room

    async def enable_outbound_mode(self) -> None:
        """Enable Day 6 outbound prompt rules for phone call sessions."""
        self._is_outbound = True
        self._update_instructions_with_memory()
        await self.update_instructions(self._instructions)

    def _update_instructions_with_memory(self) -> None:
        """Update system instructions with caller memory context."""
        base_inst = SYSTEM_PROMPT + OUTBOUND_SYSTEM_PROMPT if self._is_outbound else SYSTEM_PROMPT
        if self._prewarmed_memory:
            memory_summary = (
                f"\n\n10. CURRENT USER MEMORY CONTEXT:\n"
                f"- Found existing record: Yes\n"
                f"- User Name: {self._prewarmed_memory.get('name')}\n"
                f"- Preferred Language: {self._prewarmed_memory.get('language_pref')}\n"
                f"- Saved Facts: {json.dumps(self._prewarmed_memory.get('facts', {}), ensure_ascii=False)}\n"
                f"- Last interaction: {self._prewarmed_memory.get('last_interaction')}\n"
            )
        else:
            memory_summary = (
                "\n\n10. CURRENT USER MEMORY CONTEXT:\n"
                "- Found existing record: No (new caller).\n"
            )
        self._instructions = base_inst + memory_summary

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
        else:
            logger.info("Memory context: participant identity set (%.8s...), no existing record", user_id)
        self._update_instructions_with_memory()
        await self.update_instructions(self._instructions)

    async def on_enter(self) -> None:
        """Called when entering Assistant."""
        logger.info("Assistant.on_enter: user_id=%.8s..., is_handoff=%s", self._user_id or "unknown", self._is_handoff_destination)
        if self._is_handoff_destination:
            try:
                self.session.generate_reply()
                logger.info("Assistant.on_enter: generate_reply triggered after handoff back.")
            except Exception as err:
                logger.error("Assistant.on_enter generate_reply error: %s", err)

    # ------------------------------------------------------------------
    # DAY 9 MULTI-AGENT HANDOFF TOOL
    # ------------------------------------------------------------------

    @function_tool
    async def transfer_to_scheme_specialist(
        self,
        context: RunContext,
        reason_or_query: str,
    ) -> Agent:
        """Connect the caller to the Government Scheme Specialist for in-depth government scheme queries, detailed eligibility evaluation, documentation requirements, and scheme benefits.

        CALL THIS TOOL when the user asks detailed questions about government schemes (e.g. PMJJBY, PMSBY, PMJDY, APY, Sukanya Samriddhi) or requests an eligibility check.

        Before calling this tool, inform the user clearly that you are connecting them to the Government Scheme Specialist.

        Args:
            reason_or_query: The specific scheme or question the user asked about (e.g. 'PMJJBY eligibility check', 'Sukanya Samriddhi documents').
        """
        logger.info(
            "transfer_to_scheme_specialist invoked: reason_or_query='%s' (user_id=%.8s..., call_id=%s)",
            reason_or_query,
            self._user_id or "unknown",
            self._call_id or "unknown",
        )
        history = (
            context.session.history.copy()
            if context and hasattr(context, "session") and context.session
            else (self.chat_ctx.copy() if hasattr(self, "chat_ctx") else None)
        )
        specialist = GovernmentSchemeSpecialist(
            chat_ctx=history,
            user_id=self._user_id,
            prewarmed_memory=self._prewarmed_memory,
            room=self._room,
            call_id=self._call_id,
            is_outbound=self._is_outbound,
        )
        logger.info(
            "transfer_to_scheme_specialist: Successfully instantiated %s with %d conversation history items.",
            specialist.id,
            len(history.items) if history else 0,
        )
        return specialist

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
        if not user_confirmed:
            logger.info("save_user_memory: refused — user_confirmed=False")
            return (
                "Save cancelled: the user has not explicitly confirmed. "
                "Do NOT save any information without consent."
            )

        if not self._user_id:
            logger.warning("save_user_memory: user_id not set")
            return "Cannot save: user identity is not available for this session."

        existing = db_lookup_user(self._user_id)
        existing_facts: dict = existing["facts"] if existing else {}

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
    # EXISTING FINANCIAL TOOLS (Days 1-3)
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
            if res_dict.get("status") != "error" and self._call_id:
                db_mark_call_success(self._call_id, "eligibility_check")
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

            task = asyncio.create_task(_disconnect_room())
            _ = task

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

    @function_tool
    async def create_escalation(
        self,
        context: RunContext,
        user_confirmed: bool,
        what_happened: str,
        what_checked: str,
        urgency: str = "high",
        language: str = "hi",
        preferred_follow_up: str = "not specified",
    ) -> str:
        """Create a human help / escalation request record when user explicitly permits (Day 7).

        Args:
            user_confirmed: MUST be True. The caller has explicitly consented to creating an escalation request.
            what_happened: Sanitized description of the fraud, scam, or complex issue needing human review.
            what_checked: Sanitized summary of what Jan Sathi checked or explained (e.g. 1930 Helpline info, card block steps).
            urgency: Urgency level ('low', 'medium', 'high', 'emergency'). Default is 'high'.
            language: Caller's language ('hi', 'en', 'hinglish'). Default is 'hi'.
            preferred_follow_up: Preferred follow-up method (e.g. 'phone call', 'SMS', 'bank visit', 'not specified').
        """
        if not user_confirmed:
            logger.info("create_escalation refused — user_confirmed=False")
            return json.dumps(
                {
                    "status": "refused",
                    "reason": "Escalation cancelled: explicit user permission was not granted.",
                },
                ensure_ascii=False,
            )

        caller_name = (
            self._prewarmed_memory.get("name")
            if self._prewarmed_memory and self._prewarmed_memory.get("name")
            else "Anonymous Caller"
        )
        effective_user_id = self._user_id or "unknown_caller"

        try:
            res = db_create_escalation(
                user_id=effective_user_id,
                what_happened=what_happened,
                what_checked=what_checked,
                who_needs_help=caller_name,
                urgency=urgency,
                language=language,
                follow_up_pref=preferred_follow_up,
            )
            if res.get("reference_id") and self._call_id:
                db_mark_call_success(self._call_id, "escalation_created")
            logger.info("create_escalation tool succeeded: ref_id=%s", res["reference_id"])
            return json.dumps(res, ensure_ascii=False)
        except Exception as err:
            logger.error("create_escalation tool error: %s", err, exc_info=True)
            return json.dumps(
                {
                    "status": "error",
                    "reason": "Could not save escalation request to database.",
                },
                ensure_ascii=False,
            )

    @function_tool
    async def get_scheme_or_document_info(
        self,
        context: RunContext,
        scheme_name: str,
    ) -> str:
        """Get official government scheme details and required documents when a user explicitly requests scheme or document information (e.g. PMJJBY, PMSBY, PMJDY, APY, Sukanya Samriddhi).

        Args:
            scheme_name: Name or code of the requested scheme (e.g. "PMJJBY", "PMSBY", "PMJDY").
        """
        logger.info("get_scheme_or_document_info requested for scheme: %s", scheme_name)
        norm_code = normalize_scheme_input(scheme_name, None) or scheme_name.upper().strip()
        data = SCHEMES_DATA.get(norm_code)

        if self._call_id:
            db_mark_call_success(self._call_id, "scheme_or_doc_info")

        if data:
            return json.dumps(
                {
                    "status": "success",
                    "scheme": data["scheme_full_name"],
                    "annual_premium": data.get("annual_premium", "N/A"),
                    "coverage": data.get("coverage", "N/A"),
                    "account_requirement": data.get("account_requirement", "N/A"),
                    "official_source": data.get("official_source", OFFICIAL_SOURCES.get("DFS_PORTAL")),
                    "last_verified": LAST_VERIFIED_DATE,
                },
                ensure_ascii=False,
            )
        else:
            return json.dumps(
                {
                    "status": "success",
                    "scheme": scheme_name,
                    "info": f"Official details for {scheme_name} can be verified on official Government portals.",
                    "official_source": OFFICIAL_SOURCES.get("DFS_PORTAL"),
                    "last_verified": LAST_VERIFIED_DATE,
                },
                ensure_ascii=False,
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

    call_id = f"call_{uuid.uuid4().hex}"
    assistant = Assistant()
    assistant.set_room(ctx.room)
    assistant.set_call_id(call_id)

    # Set up a voice AI pipeline using Murf Falcon, Gemini, Deepgram, and the LiveKit turn detector
    session = AgentSession(
        stt=deepgram.STT(model="nova-3"),
        llm=google.LLM(
            model="gemini-3.5-flash-lite",
            temperature=0,
        ),
        tts=murf.TTS(
            voice="pooja",
            locale="en-IN",
            style="Conversation",
            tokenizer=HindiSentenceTokenizer(min_sentence_len=2),
            text_pacing=True,
            min_buffer_size=5,
        ),
        turn_detection=MultilingualModel(),
        vad=ctx.proc.userdata["vad"],
        preemptive_generation=False,
        allow_interruptions=True,
        min_endpointing_delay=0.3,
        max_endpointing_delay=3.0,
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

    try:
        # Start the session, initializing the voice pipeline with standard WebRTC audio
        await session.start(
            agent=assistant,
            room=ctx.room,
        )

        # Join the room and connect to the user
        await ctx.connect()

        # ── Safeguard 3: Derive user_id from LiveKit participant identity ─────────
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

        # ── Day 8: Record call start in SQLite ────────────────────────────────
        channel = "SIP Outbound" if is_outbound else "Browser"
        db_start_call(
            call_id=call_id,
            room_name=ctx.room.name,
            user_id=user_id or "anonymous",
            channel=channel,
        )

        if is_outbound:
            logger.info("Outbound call session detected (room=%s) — enabling Day 6 outbound prompt & greeting", ctx.room.name)
            await assistant.enable_outbound_mode()
            await session.generate_reply()
    finally:
        db_end_call(call_id)


if __name__ == "__main__":
    cli.run_app(server)
