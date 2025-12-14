# Sales Agent - Multi-Agent Sales Automation

## Tech Stack
- Backend: Python, FastAPI, LangGraph
- Database: Supabase
- LLMs: Anthropic Claude, Groq, Cerebras (NO OpenAI)
- Deployment: RunPod serverless

## Active Skills
- `sales-outreach-skill` - Cold outreach, lead scoring, ICP
- `langgraph-agents-skill` - 6-agent pipeline architecture
- `runpod-deployment-skill` - Model serving

## Agent Pipeline
1. LeadEnricher - Company/contact data
2. ICPScorer - Fit scoring
3. ResearchAgent - Deep company research
4. PersonalizationAgent - Custom messaging
5. SequenceAgent - Multi-touch campaigns
6. ResponseAgent - Reply handling

## Key Files
- `src/agents/` - Agent definitions
- `src/tools/` - Shared tools
- `src/state/` - LangGraph state schemas

---

## Scientia Capital AI Stack

This project is part of the Scientia Capital AI Stack ecosystem.

### Core Infrastructure Repositories
- **lang-core** (Foundation): LangChain/LangGraph middleware, LLM providers, Redis, FastAPI
  - https://github.com/ScientiaCapital/lang-core
- **vlm-ai-core** (Vision): Qwen VL, Gemini Vision, Document AI, OCR
  - https://github.com/ScientiaCapital/vlm-ai-core
- **voice-ai-core** (Voice): Cartesia TTS, Deepgram STT, Twilio integration
  - https://github.com/ScientiaCapital/voice-ai-core

### Integration Pattern
```bash
# Infrastructure from lang-core
python ~/lang-core/scripts/inline_to_project.py /your/project --modules middleware providers

# Vision capabilities from vlm-ai-core
python ~/vlm-ai-core/scripts/inline_to_project.py /your/project --modules providers preprocessing

# Voice capabilities from voice-ai-core
python ~/voice-ai-core/scripts/inline_to_project.py /your/project --modules providers types
```

### Stack Principles
- **NO OpenAI** - Use Anthropic Claude, Google Gemini, DeepSeek, Qwen via OpenRouter
- API keys ONLY in `.env` files, never hardcoded
- Each repo has one domain - no duplication
