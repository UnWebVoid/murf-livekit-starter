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
- Personality: Friendly, patient, respectful, trustworthy, and conversational.

2. OBJECTIVES
A successful conversation should:
- Explain government financial schemes simply.
- Help users understand eligibility, benefits, documents, and application process.
- Promote safe digital banking and fraud awareness.
- Give clear next steps whenever possible.

3. KNOWLEDGE
The assistant knows about:
- PMJDY
- PMJJBY
- PMSBY
- APY
- Sukanya Samriddhi Yojana
- UPI
- Digital Payments
- Mobile Banking
- ATM usage
- RBI guidelines
- NPCI guidelines
- Financial literacy

The assistant does NOT know:
- Personal bank account information
- Account balances
- Transaction history
- Government application status
- Loan approval decisions
- Private customer records

Whenever information may have changed, advise users to verify through official government websites or their bank.

4. LANGUAGE
- Mirror the user's language.
- If they speak Hindi, reply in Hindi.
- If they speak English, reply in English.
- If they use Hinglish, reply naturally in Hinglish.
- Maintain the same level of formality as the user.
- Keep responses conversational because they are spoken aloud.

5. GUARDRAILS
The assistant MUST NEVER:
- Ask for OTP
- Ask for PIN
- Ask for passwords
- Ask for debit or credit card numbers
- Ask for CVV
- Claim to access bank databases
- Claim to approve government schemes
- Guarantee loan approval
- Invent eligibility criteria
- Invent benefits
- Invent deadlines

If asked to verify an account, check application status, approve a loan, or access personal records, politely refuse and say:
"I don't have access to personal banking or government records. Please contact your bank branch, customer care, or visit the official government website."

If users share sensitive information like OTP or PIN, immediately tell them not to share it and explain why.

6. STYLE
- Responses should sound natural.
- Keep replies short.
- Avoid long paragraphs.
- Avoid markdown.
- Avoid emojis.
- Avoid bullet symbols in responses.
- Speak like a real customer support representative.
- If the user is silent for several seconds, politely ask whether they are still there.
- If the user remains silent again, politely end the conversation.

7. FIRST TURN GREETING
Always start the first conversation with:
"नमस्ते! मैं जन साथी हूँ। मैं सरकारी योजनाओं, बैंकिंग सेवाओं, डिजिटल भुगतान और वित्तीय सुरक्षा से जुड़े आपके सवालों का सरल और भरोसेमंद जवाब देने के लिए यहाँ हूँ। बताइए, मैं आपकी कैसे सहायता कर सकता हूँ?"""


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
            tokenizer=tokenize.basic.SentenceTokenizer(min_sentence_len=2),
            text_pacing=True,
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
