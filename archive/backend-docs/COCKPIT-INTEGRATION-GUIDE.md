# BDR Cockpit Integration Guide

How to integrate the Cockpit API with existing Celery tasks.

---

## 🎯 Goal

Publish real-time events to the BDR Cockpit as agents execute.

---

## 📡 Publishing Events from Celery Tasks

### Step 1: Import Helper Functions

```python
# In app/tasks/agent_tasks.py
from app.api.cockpit_websocket import publish_agent_event
from app.api.alerts import create_alert
```

---

### Step 2: Publish Events at Key Points

#### Agent Started (at beginning of task)

```python
@celery_app.task(name="run_lead_scout", bind=True, max_retries=2)
def run_lead_scout_task(self, limit=10):
    import asyncio

    # Publish start event
    asyncio.run(publish_agent_event(
        event_type="agent_started",
        agent_name="lead_scout",
        task_id=self.request.id
    ))

    try:
        # ... existing agent logic ...
        result = scout_leads(limit)

        # Publish completion event
        asyncio.run(publish_agent_event(
            event_type="agent_completed",
            agent_name="lead_scout",
            task_id=self.request.id,
            result={
                "total_scouted": result.total_scouted,
                "hot_leads": result.hot_leads,
                "warm_leads": result.warm_leads,
                "cold_leads": result.cold_leads
            },
            duration_ms=result.duration_ms
        ))

        return result

    except Exception as e:
        # Publish error event
        asyncio.run(publish_agent_event(
            event_type="agent_failed",
            agent_name="lead_scout",
            task_id=self.request.id,
            error=str(e)
        ))
        raise
```

---

### Step 3: Create Alerts for Important Events

```python
# Example: Create alert when HOT lead found
if result.hot_leads > 0:
    asyncio.run(create_alert(
        severity="high",
        title=f"🔥 {result.hot_leads} HOT Lead(s) Discovered!",
        message=f"Lead Scout found {result.hot_leads} HOT leads in this run",
        broadcast=True
    ))
```

---

## 📋 Full Example: Enhanced Lead Scout Task

```python
@celery_app.task(name="run_lead_scout", bind=True, max_retries=2, soft_time_limit=600)
def run_lead_scout_task(self, limit=10, require_domain=True, icp_tier=None):
    """
    Autonomous lead discovery task with Cockpit integration.
    """
    import asyncio
    from app.services.langgraph.agents.lead_scout_agent import LeadScoutAgent
    from app.api.cockpit_websocket import publish_agent_event
    from app.api.alerts import create_alert
    import time

    logger.info(f"Starting Lead Scout task: limit={limit}, require_domain={require_domain}")

    # 📡 PUBLISH START EVENT
    asyncio.run(publish_agent_event(
        event_type="agent_started",
        agent_name="lead_scout",
        task_id=self.request.id
    ))

    start_time = time.time()

    try:
        # Run the agent
        async def _scout():
            scout = LeadScoutAgent(provider='cerebras')
            return await scout.scout(
                limit=limit,
                require_domain=require_domain,
                icp_tier=icp_tier
            )

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(_scout())
        finally:
            loop.close()

        # Calculate duration
        duration_ms = int((time.time() - start_time) * 1000)

        # 📡 PUBLISH COMPLETION EVENT
        asyncio.run(publish_agent_event(
            event_type="agent_completed",
            agent_name="lead_scout",
            task_id=self.request.id,
            result={
                "total_scouted": result.total_scouted,
                "hot_leads": result.hot_leads,
                "warm_leads": result.warm_leads,
                "cold_leads": result.cold_leads,
                "errors": len(result.errors)
            },
            duration_ms=duration_ms
        ))

        # 🔔 CREATE ALERT IF HOT LEADS FOUND
        if result.hot_leads > 0:
            asyncio.run(create_alert(
                severity="high",
                title=f"🔥 {result.hot_leads} HOT Lead(s) Discovered!",
                message=f"Lead Scout found {result.hot_leads} HOT leads (out of {result.total_scouted} scouted)",
                broadcast=True
            ))

        logger.info(
            f"Lead Scout completed: {result.total_scouted} scouted, "
            f"{result.hot_leads} HOT in {duration_ms}ms"
        )

        return {
            "status": "success",
            "total_scouted": result.total_scouted,
            "hot_leads": result.hot_leads,
            "warm_leads": result.warm_leads,
            "cold_leads": result.cold_leads,
            "errors": result.errors,
            "duration_ms": duration_ms
        }

    except SoftTimeLimitExceeded:
        logger.warning("Lead Scout soft time limit exceeded (10 minutes)")

        # 📡 PUBLISH ERROR EVENT
        asyncio.run(publish_agent_event(
            event_type="agent_failed",
            agent_name="lead_scout",
            task_id=self.request.id,
            error="Task timeout (10 minutes)"
        ))

        raise

    except Exception as exc:
        logger.error(f"Error in Lead Scout task: {exc}", exc_info=True)

        # 📡 PUBLISH ERROR EVENT
        asyncio.run(publish_agent_event(
            event_type="agent_failed",
            agent_name="lead_scout",
            task_id=self.request.id,
            error=str(exc)
        ))

        countdown = 60 * (2 ** self.request.retries)
        raise self.retry(exc=exc, countdown=countdown)
```

---

## 🔔 Alert Examples for Each Agent

### Lead Scout

```python
# HOT leads found
await create_alert(
    severity="high",
    title=f"🔥 {hot_count} HOT Lead(s) Discovered",
    message=f"Lead Scout found {hot_count} HOT leads with direct phone numbers",
    broadcast=True
)
```

---

### Morning Report

```python
# Report generated
await create_alert(
    severity="medium",
    title="📊 Morning Report Ready",
    message=f"Your daily report is ready with {top_leads_count} outreach drafts",
    broadcast=True
)
```

---

### BDR Outreach

```python
# New draft ready for approval
await create_alert(
    severity="medium",
    title="✉️ New Draft Ready",
    message=f"BDR Agent created email draft for {company_name}",
    draft_id=draft_id,
    lead_id=lead_id,
    broadcast=True
)

# Draft approved
await create_alert(
    severity="low",
    title="✅ Email Sent",
    message=f"Email to {company_name} approved and sent",
    lead_id=lead_id,
    broadcast=True
)
```

---

### Growth Campaigns

```python
# Campaign goal met
await create_alert(
    severity="high",
    title="🎯 Campaign Goal Met!",
    message=f"Growth campaign for {company_name} successfully booked a meeting",
    lead_id=lead_id,
    broadcast=True
)
```

---

## 🧪 Testing Integration

### 1. Start Redis (for pub/sub)

```bash
docker-compose up -d redis
```

---

### 2. Start Celery Worker

```bash
cd backend
source ../venv/bin/activate
celery -A app.celery_app worker --loglevel=info
```

---

### 3. Start FastAPI Server

```bash
cd backend
source ../venv/bin/activate
python start_server.py
```

---

### 4. Connect WebSocket Client

```javascript
// In browser console or Node.js
const ws = new WebSocket('ws://localhost:8001/api/v1/ws/cockpit');

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log('📨', data.type, data);
};
```

---

### 5. Trigger Agent via API

```bash
curl -X POST http://localhost:8001/api/v1/agents/lead_scout/start \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"config": {"limit": 5}}'
```

---

### 6. Watch WebSocket Output

You should see:

```
📨 agent_started { type: 'agent_started', agent: 'lead_scout', task_id: '...' }
📨 agent_completed { type: 'agent_completed', agent: 'lead_scout', result: {...} }
📨 alert { type: 'alert', severity: 'high', title: '🔥 2 HOT Lead(s) Discovered!' }
```

---

## 🔄 Event Flow Diagram

```
┌─────────────────┐
│  User clicks    │
│  "Start Agent"  │
│   in Cockpit    │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  POST /agents/  │
│  lead_scout/    │
│     start       │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Celery enqueues │
│      task       │
└────────┬────────┘
         │
         ▼
┌─────────────────────────────────────────┐
│           CELERY WORKER                 │
│                                         │
│  1. publish_agent_event("started")      │
│     └─> Redis pub/sub                   │
│         └─> WebSocket broadcasts        │
│             └─> Cockpit UI updates      │
│                                         │
│  2. Run agent logic                     │
│                                         │
│  3. publish_agent_event("completed")    │
│     └─> Redis pub/sub                   │
│         └─> WebSocket broadcasts        │
│             └─> Cockpit UI updates      │
│                                         │
│  4. create_alert() [if needed]          │
│     └─> Redis pub/sub                   │
│         └─> WebSocket broadcasts        │
│             └─> Toast notification      │
│                                         │
└─────────────────────────────────────────┘
```

---

## 📝 Checklist for Each Agent

For each agent task in `app/tasks/agent_tasks.py`, add:

- [ ] `publish_agent_event("agent_started")` at task start
- [ ] `publish_agent_event("agent_completed")` on success
- [ ] `publish_agent_event("agent_failed")` on error
- [ ] `create_alert()` for important events (HOT leads, goals met, etc.)
- [ ] Include `task_id=self.request.id` in all events
- [ ] Include `duration_ms` in completion events
- [ ] Include meaningful result summary in completion events

---

## 🚀 Rollout Plan

### Phase 1: Lead Scout (Testing)
- [ ] Add events to `run_lead_scout_task`
- [ ] Test WebSocket broadcasting
- [ ] Verify UI updates in real-time

### Phase 2: All Autonomous Agents
- [ ] Morning Report
- [ ] Sales Intel
- [ ] Growth Campaigns
- [ ] ICP Checker
- [ ] Prediction Market
- [ ] Morning Briefing

### Phase 3: BDR Agent (Human-in-Loop)
- [ ] Draft creation alerts
- [ ] Approval notifications
- [ ] Send confirmations

---

## 🐛 Troubleshooting

### WebSocket not receiving events

1. Check Redis is running: `redis-cli ping`
2. Check Celery worker is running: `celery -A app.celery_app inspect active`
3. Check WebSocket connection: Browser DevTools → Network → WS
4. Check Redis pub/sub: `redis-cli subscribe cockpit:events`

### Events not publishing

1. Verify imports: `from app.api.cockpit_websocket import publish_agent_event`
2. Check Redis connection: `REDIS_URL` env var set correctly
3. Check logs: Look for "Published event to cockpit:events" messages
4. Test manually: `redis-cli PUBLISH cockpit:events '{"type":"test"}'`

---

## 📚 References

- **Cockpit API Reference**: `COCKPIT-API-REFERENCE.md`
- **Task Summary**: `TASK-025-SUMMARY.md`
- **FastAPI WebSocket Docs**: https://fastapi.tiangolo.com/advanced/websockets/
- **Redis Pub/Sub Docs**: https://redis.io/docs/manual/pubsub/

---

**Next Steps**: Integrate events into all 8 agents listed in AGENT_TASKS mapping.
