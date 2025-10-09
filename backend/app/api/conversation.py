"""
Conversation Intelligence API endpoints

Real-time conversation analysis with WebSocket streaming support.
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Optional, Dict, Any
import logging
import json
import asyncio

from app.models.database import get_db
from app.models.conversation_models import Conversation, ConversationTurn, SpeakerRole
from app.services.transcription_service import get_transcription_service
from app.services.audio_processor import get_audio_processor_manager
from app.services.sentiment_analyzer import get_sentiment_analyzer
from app.services.suggestion_engine import get_suggestion_engine
from app.services.battle_card_service import BattleCardService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/conversation", tags=["conversation"])


@router.post("/start")
async def start_conversation(
    lead_id: Optional[int] = None,
    db: Session = Depends(get_db),
):
    """
    Start a new conversation session.

    Returns:
        Conversation ID and metadata
    """
    try:
        # Create new conversation
        conversation = Conversation(
            lead_id=lead_id,
            status="active",
        )

        db.add(conversation)
        db.commit()
        db.refresh(conversation)

        logger.info(f"Started conversation {conversation.id} for lead {lead_id}")

        return {
            "conversation_id": conversation.id,
            "lead_id": lead_id,
            "status": "active",
            "started_at": conversation.started_at.isoformat(),
        }

    except Exception as e:
        logger.error(f"Failed to start conversation: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.websocket("/stream/{conversation_id}")
async def conversation_stream(
    websocket: WebSocket,
    conversation_id: str,
    db: Session = Depends(get_db),
):
    """
    WebSocket endpoint for real-time conversation intelligence.

    Accepts audio chunks and returns transcription, sentiment analysis,
    suggestions, and battle card triggers in real-time.

    Message format (client → server):
    {
        "type": "audio_chunk",
        "data": <base64_audio_data>,
        "format": "webm",
        "speaker": "prospect"
    }

    Message format (server → client):
    {
        "type": "transcription" | "analysis" | "suggestion" | "battle_card",
        "data": {...}
    }
    """
    await websocket.accept()

    try:
        # Verify conversation exists
        conversation = db.query(Conversation).filter(
            Conversation.id == conversation_id
        ).first()

        if not conversation:
            await websocket.send_json({
                "type": "error",
                "message": f"Conversation {conversation_id} not found"
            })
            await websocket.close()
            return

        # Initialize services
        transcription_service = get_transcription_service()
        sentiment_analyzer = get_sentiment_analyzer()
        suggestion_engine = get_suggestion_engine()
        battle_card_service = BattleCardService(db)

        # Create audio processor with callback
        async def on_transcription(transcription_result: Dict[str, Any]):
            """Callback when transcription completes."""
            try:
                # Send transcription to client
                await websocket.send_json({
                    "type": "transcription",
                    "data": transcription_result
                })

                # Get conversation history for context
                recent_turns = db.query(ConversationTurn).filter(
                    ConversationTurn.conversation_id == conversation_id
                ).order_by(ConversationTurn.turn_number.desc()).limit(10).all()

                conversation_history = [
                    {"speaker": turn.speaker.value, "text": turn.text}
                    for turn in reversed(recent_turns)
                ]

                # Run sentiment analysis and suggestions in parallel
                sentiment_task = sentiment_analyzer.analyze_sentiment(
                    text=transcription_result["text"],
                    speaker="prospect",  # TODO: detect speaker
                    context=[h["text"] for h in conversation_history[-3:]],
                )

                suggestion_task = suggestion_engine.generate_suggestions(
                    current_text=transcription_result["text"],
                    speaker="prospect",
                    conversation_history=conversation_history,
                    lead_data={"lead_id": conversation.lead_id} if conversation.lead_id else None,
                )

                sentiment_result, suggestion_result = await asyncio.gather(
                    sentiment_task, suggestion_task
                )

                # Send sentiment analysis
                await websocket.send_json({
                    "type": "sentiment",
                    "data": sentiment_result
                })

                # Send suggestions
                await websocket.send_json({
                    "type": "suggestions",
                    "data": suggestion_result
                })

                # Check for battle card triggers
                if suggestion_result.get("battle_card_triggers"):
                    matching_templates = battle_card_service.find_matching_templates(
                        text=transcription_result["text"],
                        detected_topics=suggestion_result.get("detected_topics", []),
                        trigger_keywords=suggestion_result["battle_card_triggers"],
                    )

                    for template in matching_templates:
                        battle_card = battle_card_service.create_conversation_battle_card(
                            conversation_id=conversation_id,
                            template=template,
                            trigger_keyword=suggestion_result["battle_card_triggers"][0] if suggestion_result["battle_card_triggers"] else None,
                        )

                        await websocket.send_json({
                            "type": "battle_card",
                            "data": {
                                "id": battle_card.id,
                                "card_type": battle_card.card_type.value,
                                "title": battle_card.title,
                                "content": battle_card.content,
                                "talking_points": battle_card.talking_points,
                                "response_template": battle_card.response_template,
                            }
                        })

                # Save conversation turn to database
                turn = ConversationTurn(
                    conversation_id=conversation_id,
                    turn_number=conversation.total_turns + 1,
                    speaker=SpeakerRole.PROSPECT,  # TODO: detect speaker
                    text=transcription_result["text"],
                    transcription_confidence=transcription_result.get("confidence"),
                    audio_duration_ms=transcription_result.get("duration_seconds", 0) * 1000 if transcription_result.get("duration_seconds") else None,
                    sentiment=sentiment_result.get("sentiment"),
                    sentiment_score=sentiment_result.get("score"),
                    sentiment_confidence=sentiment_result.get("confidence"),
                    detected_emotions=sentiment_result.get("emotions"),
                    detected_topics=suggestion_result.get("detected_topics"),
                    is_objection=sentiment_result.get("is_objection", False),
                    is_question=sentiment_result.get("is_question", False),
                    is_commitment=sentiment_result.get("is_commitment", False),
                    suggestions=suggestion_result.get("suggestions"),
                    transcription_latency_ms=transcription_result.get("latency_ms"),
                    sentiment_analysis_latency_ms=sentiment_result.get("latency_ms"),
                    suggestion_generation_latency_ms=suggestion_result.get("latency_ms"),
                    total_latency_ms=transcription_result.get("latency_ms", 0) + sentiment_result.get("latency_ms", 0) + suggestion_result.get("latency_ms", 0),
                )

                db.add(turn)
                conversation.total_turns += 1
                db.commit()

            except Exception as e:
                logger.error(f"Error processing transcription callback: {e}")
                await websocket.send_json({
                    "type": "error",
                    "message": f"Processing error: {str(e)}"
                })

        # Get or create audio processor
        audio_manager = get_audio_processor_manager(transcription_service)
        audio_processor = audio_manager.create_processor(
            conversation_id=conversation_id,
            on_transcription_callback=on_transcription,
        )

        # Send ready signal
        await websocket.send_json({
            "type": "ready",
            "conversation_id": conversation_id
        })

        # Listen for audio chunks
        while True:
            try:
                message = await websocket.receive_json()

                if message.get("type") == "audio_chunk":
                    # Decode base64 audio data
                    import base64
                    audio_data = base64.b64decode(message.get("data", ""))
                    audio_format = message.get("format", "webm")

                    # Process audio chunk
                    await audio_processor.process_audio_chunk(
                        audio_data=audio_data,
                        audio_format=audio_format,
                    )

                elif message.get("type") == "end_conversation":
                    # Flush remaining audio
                    await audio_processor.flush()
                    break

            except WebSocketDisconnect:
                logger.info(f"WebSocket disconnected for conversation {conversation_id}")
                break

    except Exception as e:
        logger.error(f"WebSocket error for conversation {conversation_id}: {e}")
        try:
            await websocket.send_json({
                "type": "error",
                "message": str(e)
            })
        except:
            pass

    finally:
        # Cleanup
        await audio_manager.remove_processor(conversation_id)

        # Update conversation status
        conversation.status = "completed"
        db.commit()

        try:
            await websocket.close()
        except:
            pass


@router.get("/{conversation_id}")
async def get_conversation(
    conversation_id: str,
    db: Session = Depends(get_db),
):
    """Get conversation details with all turns."""
    conversation = db.query(Conversation).filter(
        Conversation.id == conversation_id
    ).first()

    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    turns = db.query(ConversationTurn).filter(
        ConversationTurn.conversation_id == conversation_id
    ).order_by(ConversationTurn.turn_number).all()

    return {
        "id": conversation.id,
        "lead_id": conversation.lead_id,
        "status": conversation.status,
        "started_at": conversation.started_at.isoformat() if conversation.started_at else None,
        "ended_at": conversation.ended_at.isoformat() if conversation.ended_at else None,
        "total_turns": conversation.total_turns,
        "overall_sentiment": conversation.overall_sentiment,
        "turns": [
            {
                "turn_number": turn.turn_number,
                "speaker": turn.speaker.value,
                "text": turn.text,
                "sentiment": turn.sentiment.value if turn.sentiment else None,
                "sentiment_score": turn.sentiment_score,
                "suggestions": turn.suggestions,
            }
            for turn in turns
        ],
    }


@router.get("/{conversation_id}/battle-cards")
async def get_conversation_battle_cards(
    conversation_id: str,
    db: Session = Depends(get_db),
):
    """Get all battle cards for a conversation."""
    battle_card_service = BattleCardService(db)

    battle_cards = battle_card_service.get_conversation_battle_cards(conversation_id)

    return {
        "conversation_id": conversation_id,
        "battle_cards": [
            {
                "id": bc.id,
                "card_type": bc.card_type.value,
                "title": bc.title,
                "content": bc.content,
                "talking_points": bc.talking_points,
                "suggested_at": bc.suggested_at.isoformat(),
                "viewed_at": bc.viewed_at.isoformat() if bc.viewed_at else None,
                "used_at": bc.used_at.isoformat() if bc.used_at else None,
            }
            for bc in battle_cards
        ],
        "stats": battle_card_service.get_battle_card_stats(conversation_id),
    }
