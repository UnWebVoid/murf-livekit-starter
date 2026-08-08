import logging

from dotenv import load_dotenv
from livekit import rtc
from livekit.agents import (
    Agent,
    AgentServer,
    AgentSession,
    JobContext,
    JobProcess,
    RunContext,
    cli,
    function_tool,
    room_io,
    tokenize,
)
from livekit.plugins import deepgram, google, murf, noise_cancellation, silero
from livekit.plugins.turn_detector.multilingual import MultilingualModel

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

If users share sensitive information like OTP or PIN, immediately tell them not to share it and explain why.

6. VOICE & SPOKEN RESPONSE STYLE
- Keep responses short (2-4 spoken sentences max per turn). Avoid long paragraphs.
- Avoid markdown, formatting symbols, bullets, or emojis.
- Speak warmly and clearly with natural pauses between ideas.
- If the user is silent for several seconds, politely ask whether they are still there.

7. FIRST TURN GREETING
Always start the first conversation with:
"नमस्ते! मैं जन साथी हूँ। मैं सरकारी योजनाओं, बैंकिंग, UPI payments और वित्तीय सुरक्षा से जुड़े आपके सवालों में मदद करने के लिए यहाँ हूँ। बताइए, आज मैं आपकी क्या हेल्प कर सकता हूँ?"
"""


class Assistant(Agent):
    def __init__(self) -> None:
        super().__init__(instructions=SYSTEM_PROMPT)

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
    async def check_scheme_eligibility(
        self,
        context: RunContext,
        scheme_name: str,
        age: int,
    ) -> str:
        """Check general eligibility criteria for popular Indian government welfare & financial schemes.

        Args:
            scheme_name: Name of scheme (e.g. PMJDY, PMJJBY, PMSBY, APY, SSY, PM-KISAN).
            age: Age of the applicant in years.
        """
        logger.info(f"Checking scheme eligibility for {scheme_name}, age: {age}")
        s_lower = scheme_name.lower()
        if "pmjjby" in s_lower or "jeevan jyoti" in s_lower:
            eligible = 18 <= age <= 50
            details = "Pradhan Mantri Jeevan Jyoti Bima Yojana provides ₹2 Lakh life insurance cover for ₹436/year. Entry age is 18 to 50 years."
        elif "pmsby" in s_lower or "suraksha bima" in s_lower:
            eligible = 18 <= age <= 70
            details = "Pradhan Mantri Suraksha Bima Yojana provides ₹2 Lakh accidental insurance cover for ₹20/year. Entry age is 18 to 70 years."
        elif "apy" in s_lower or "atal pension" in s_lower:
            eligible = 18 <= age <= 40
            details = "Atal Pension Yojana offers guaranteed monthly pension (₹1,000 to ₹5,000) post age 60. Entry age is 18 to 40 years."
        elif "jandhan" in s_lower or "pmjdy" in s_lower:
            eligible = age >= 10
            details = "PM Jan Dhan Yojana offers zero-balance savings account, RuPay debit card, ₹2 Lakh accident insurance, and ₹10,000 overdraft facility."
        elif "sukanya" in s_lower or "ssy" in s_lower:
            eligible = age <= 10
            details = "Sukanya Samriddhi Yojana is for girl children below 10 years of age, offering tax-free savings for education and marriage."
        else:
            eligible = True
            details = f"General details for {scheme_name}: Please verify exact criteria on the official portal."

        status = "Eligible" if eligible else "Not Eligible based on age criteria"
        return f"Scheme: {scheme_name}. Status: {status}. Details: {details}"

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


server = AgentServer()


def prewarm(proc: JobProcess):
    proc.userdata["vad"] = silero.VAD.load()


server.setup_fnc = prewarm


@server.rtc_session(agent_name="my-agent")
async def my_agent(ctx: JobContext):
    # Logging setup
    ctx.log_context_fields = {
        "room": ctx.room.name,
    }

    # Set up a voice AI pipeline using Murf Falcon, Gemini, Deepgram, and the LiveKit turn detector
    session = AgentSession(
        # Speech-to-text (STT) is your agent's ears, turning the user's speech into text that the LLM can understand
        stt=deepgram.STT(model="nova-3"),
        # Large Language Model (LLM) is your agent's brain
        llm=google.LLM(
            model="gemini-3.5-flash-lite",
        ),
        # Text-to-speech (TTS) is your agent's voice (Murf Falcon)
        tts=murf.TTS(
            voice="pooja",
            locale="en-IN",
            style="Conversation",
            tokenizer=HindiSentenceTokenizer(min_sentence_len=2),
            text_pacing=False,
        ),
        # VAD and turn detection
        turn_detection=MultilingualModel(),
        vad=ctx.proc.userdata["vad"],
        preemptive_generation=True,
    )

    # Start the session, which initializes the voice pipeline and warms up the models
    await session.start(
        agent=Assistant(),
        room=ctx.room,
        room_options=room_io.RoomOptions(
            audio_input=room_io.AudioInputOptions(
                noise_cancellation=lambda params: (
                    noise_cancellation.BVCTelephony()
                    if params.participant.kind
                    == rtc.ParticipantKind.PARTICIPANT_KIND_SIP
                    else noise_cancellation.BVC()
                ),
            ),
        ),
    )

    # Join the room and connect to the user
    await ctx.connect()


if __name__ == "__main__":
    cli.run_app(server)
