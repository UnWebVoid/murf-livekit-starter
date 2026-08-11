"""
Jan Sathi Outbound Phone Call Trigger Script (Day 6).

Initiates an outbound SIP phone call via LiveKit Cloud and Twilio Elastic SIP Trunk.
Uses livekit-api v1.4 CreateSIPParticipantRequest.
"""

import asyncio
import logging
import os
import sys
from dotenv import load_dotenv
import livekit.api as api

logger = logging.getLogger("outbound_call")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

load_dotenv(".env.local")


async def place_outbound_call() -> None:
    livekit_url = os.getenv("LIVEKIT_URL")
    api_key = os.getenv("LIVEKIT_API_KEY")
    api_secret = os.getenv("LIVEKIT_API_SECRET")
    sip_trunk_id = os.getenv("LIVEKIT_SIP_TRUNK_ID")
    recipient_phone = os.getenv("RECIPIENT_PHONE_NUMBER")

    if not livekit_url or not api_key or not api_secret:
        logger.error("LIVEKIT_URL, LIVEKIT_API_KEY, and LIVEKIT_API_SECRET must be configured in .env.local")
        sys.exit(1)

    if not sip_trunk_id or not recipient_phone:
        logger.error(
            "LIVEKIT_SIP_TRUNK_ID and RECIPIENT_PHONE_NUMBER must be set in .env.local to trigger an outbound SIP call.\n"
            "Example:\n"
            "  LIVEKIT_SIP_TRUNK_ID=ST_123456\n"
            "  RECIPIENT_PHONE_NUMBER=+1234567890"
        )
        sys.exit(1)

    # Sanitize phone number for room name
    clean_phone = recipient_phone.replace("+", "").replace(" ", "").replace("-", "")
    room_name = f"jan-sathi-outbound-{clean_phone}"

    logger.info("Initializing LiveKit API client...")
    lkapi = api.LiveKitAPI(
        url=livekit_url,
        api_key=api_key,
        api_secret=api_secret,
    )

    req = api.CreateSIPParticipantRequest(
        sip_trunk_id=sip_trunk_id,
        sip_call_to=recipient_phone,
        room_name=room_name,
        participant_identity=recipient_phone,
        participant_name="Jan Sathi Recipient",
        participant_attributes={
            "call_type": "outbound",
            "topic": "PMJJBY",
        },
        wait_until_answered=False,
    )

    logger.info(
        "Placing outbound call to %s via trunk %s into room '%s'...",
        recipient_phone,
        sip_trunk_id,
        room_name,
    )

    try:
        res = await lkapi.sip.create_sip_participant(req)
        logger.info(
            "Outbound SIP call initiated successfully! Participant ID: %s, Room: %s",
            getattr(res, "participant_id", "N/A"),
            room_name,
        )

        # Explicitly dispatch the Jan Sathi agent worker into the outbound call room
        agent_name = os.getenv("AGENT_NAME", "my-agent")
        logger.info("Dispatching agent worker '%s' into room '%s'...", agent_name, room_name)
        dispatch_req = api.CreateAgentDispatchRequest(
            agent_name=agent_name,
            room=room_name,
        )
        dispatch_res = await lkapi.agent_dispatch.create_dispatch(dispatch_req)
        logger.info(
            "Agent worker '%s' dispatched successfully! Dispatch ID: %s",
            agent_name,
            getattr(dispatch_res, "id", "N/A"),
        )
    except Exception as err:
        logger.error("Failed to place outbound call or dispatch agent: %s", err, exc_info=True)
    finally:
        await lkapi.aclose()



if __name__ == "__main__":
    asyncio.run(place_outbound_call())
