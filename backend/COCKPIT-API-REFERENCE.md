# BDR Cockpit API Reference (for Frontend Integration)

Quick reference for TASK-024 (Frontend Developer)

---

## 🔌 Base URL

```
http://localhost:8001/api/v1
```

All endpoints require `Authorization: Bearer <token>` header.

---

## 🤖 Agent Control Endpoints

### Start Agent

```http
POST /agents/{agent_name}/start
Content-Type: application/json
Authorization: Bearer <token>

{
  "config": {
    "limit": 5
  }
}
```

**Response**:
```json
{
  "status": "started",
  "agent_name": "lead_scout",
  "task_id": "abc-123-def-456",
  "message": "Lead Scout started successfully"
}
```

**Valid Agent Names**:
- `lead_scout`
- `morning_report`
- `sales_intel`
- `growth_campaigns`
- `bdr_outreach`
- `icp_checker`
- `prediction_market`
- `morning_briefing`

---

### Stop Agent

```http
POST /agents/{agent_name}/stop
Authorization: Bearer <token>
```

**Response**:
```json
{
  "status": "stopped",
  "agent_name": "lead_scout",
  "message": "Stopped 1 running task(s) for Lead Scout"
}
```

---

### Get All Agent Statuses

```http
GET /agents/status
Authorization: Bearer <token>
```

**Response**:
```json
[
  {
    "name": "lead_scout",
    "status": "running",
    "last_run": "2025-12-06T20:30:00Z",
    "next_run": "2025-12-06T21:00:00Z",
    "runs_today": 12,
    "errors_today": 0,
    "current_task_id": "abc-123"
  },
  {
    "name": "morning_report",
    "status": "idle",
    "last_run": "2025-12-06T14:00:00Z",
    "next_run": "2025-12-07T14:00:00Z",
    "runs_today": 1,
    "errors_today": 0,
    "current_task_id": null
  }
]
```

**Status Values**:
- `running` - Currently executing
- `idle` - Scheduled but not running
- `error` - Failed recently
- `disabled` - Not scheduled

---

### Get Agent History

```http
GET /agents/{agent_name}/history?limit=20
Authorization: Bearer <token>
```

**Response**:
```json
{
  "agent_name": "lead_scout",
  "total_runs": 45,
  "runs": [
    {
      "task_id": "abc-123",
      "agent_name": "lead_scout",
      "status": "SUCCESS",
      "started_at": "2025-12-06T20:30:00Z",
      "completed_at": "2025-12-06T20:31:00Z",
      "duration_ms": 60000,
      "result": {
        "total_scouted": 10,
        "hot_leads": 2
      },
      "error": null
    }
  ]
}
```

---

## 🔔 Alert Endpoints

### Get Alerts (Paginated)

```http
GET /alerts?page=1&page_size=20&acknowledged=false&severity=high
Authorization: Bearer <token>
```

**Query Params**:
- `page` - Page number (default: 1)
- `page_size` - Items per page (default: 20, max: 100)
- `severity` - Filter by severity (low, medium, high, critical)
- `acknowledged` - Filter by acknowledgement status (true/false)

**Response**:
```json
{
  "total": 5,
  "page": 1,
  "page_size": 20,
  "alerts": [
    {
      "id": "alert-123",
      "severity": "high",
      "title": "🔥 HOT Lead Reply",
      "message": "John Smith at Acme Corp replied: interested",
      "lead_id": "lead-456",
      "draft_id": null,
      "created_at": "2025-12-06T20:30:00Z",
      "acknowledged": false,
      "acknowledged_at": null,
      "acknowledged_by": null
    }
  ]
}
```

---

### Acknowledge Alert

```http
POST /alerts/{alert_id}/acknowledge
Content-Type: application/json
Authorization: Bearer <token>

{
  "notes": "Called the lead, left voicemail"
}
```

**Response**:
```json
{
  "status": "acknowledged",
  "alert_id": "alert-123",
  "acknowledged_by": "tim@example.com",
  "acknowledged_at": "2025-12-06T20:35:00Z",
  "notes": "Called the lead, left voicemail"
}
```

---

### Get Unread Count

```http
GET /alerts/unread
Authorization: Bearer <token>
```

**Response**:
```json
{
  "unread_count": 5,
  "critical_count": 1,
  "high_count": 2,
  "medium_count": 1,
  "low_count": 1
}
```

---

## 🌐 WebSocket Connection

### Connect to Cockpit WebSocket

```javascript
const ws = new WebSocket('ws://localhost:8001/api/v1/ws/cockpit');

ws.onopen = () => {
  console.log('Connected to BDR Cockpit');
};

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  handleCockpitEvent(data);
};

ws.onerror = (error) => {
  console.error('WebSocket error:', error);
};

ws.onclose = () => {
  console.log('WebSocket disconnected');
  // Implement auto-reconnect logic here
};
```

---

## 📨 WebSocket Event Types

### Connection Events

**Connected**:
```json
{
  "type": "connected",
  "timestamp": "2025-12-06T20:30:00Z",
  "message": "BDR Cockpit WebSocket connected"
}
```

**Keepalive** (sent every 30s):
```json
{
  "type": "keepalive",
  "timestamp": "2025-12-06T20:31:00Z"
}
```

**Pong** (response to client ping):
```json
{
  "type": "pong",
  "timestamp": "2025-12-06T20:30:05Z"
}
```

---

### Agent Events

**Agent Started**:
```json
{
  "type": "agent_started",
  "agent": "lead_scout",
  "task_id": "abc-123",
  "timestamp": "2025-12-06T20:30:00Z"
}
```

**Agent Completed**:
```json
{
  "type": "agent_completed",
  "agent": "lead_scout",
  "task_id": "abc-123",
  "result": {
    "total_scouted": 10,
    "hot_leads": 2,
    "warm_leads": 5,
    "cold_leads": 3
  },
  "duration_ms": 45000,
  "timestamp": "2025-12-06T20:30:45Z"
}
```

**Agent Failed**:
```json
{
  "type": "agent_failed",
  "agent": "lead_scout",
  "task_id": "abc-123",
  "error": "Database connection timeout",
  "timestamp": "2025-12-06T20:30:30Z"
}
```

---

### Alert Events

**New Alert**:
```json
{
  "type": "alert",
  "severity": "high",
  "title": "🔥 HOT Lead Reply",
  "message": "John Smith at Acme Corp replied: interested",
  "lead_id": "lead-456",
  "draft_id": null,
  "timestamp": "2025-12-06T20:30:00Z"
}
```

---

## 🎯 React Integration Example

```typescript
// hooks/useCockpitWebSocket.ts
import { useEffect, useState } from 'react';

interface CockpitEvent {
  type: string;
  [key: string]: any;
}

export function useCockpitWebSocket() {
  const [connected, setConnected] = useState(false);
  const [events, setEvents] = useState<CockpitEvent[]>([]);

  useEffect(() => {
    const ws = new WebSocket('ws://localhost:8001/api/v1/ws/cockpit');

    ws.onopen = () => {
      console.log('✅ Cockpit WebSocket connected');
      setConnected(true);
    };

    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      console.log('📨 Cockpit event:', data.type, data);

      setEvents((prev) => [...prev, data]);

      // Handle specific event types
      if (data.type === 'agent_completed') {
        // Update agent status in UI
      }

      if (data.type === 'alert') {
        // Show notification toast
      }
    };

    ws.onclose = () => {
      console.log('❌ Cockpit WebSocket disconnected');
      setConnected(false);

      // Auto-reconnect after 5 seconds
      setTimeout(() => {
        // Re-run effect to reconnect
      }, 5000);
    };

    // Send keepalive ping every 20 seconds
    const pingInterval = setInterval(() => {
      if (ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: 'ping' }));
      }
    }, 20000);

    return () => {
      clearInterval(pingInterval);
      ws.close();
    };
  }, []);

  return { connected, events };
}
```

---

## 🛠️ API Client Example

```typescript
// api/agents.ts
import axios from 'axios';

const API_BASE_URL = 'http://localhost:8001/api/v1';

const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Add auth token to all requests
apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem('auth_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

export const agentsAPI = {
  startAgent: async (agentName: string, config?: any) => {
    const response = await apiClient.post(`/agents/${agentName}/start`, { config });
    return response.data;
  },

  stopAgent: async (agentName: string) => {
    const response = await apiClient.post(`/agents/${agentName}/stop`);
    return response.data;
  },

  getAgentStatuses: async () => {
    const response = await apiClient.get('/agents/status');
    return response.data;
  },

  getAgentHistory: async (agentName: string, limit = 20) => {
    const response = await apiClient.get(`/agents/${agentName}/history`, {
      params: { limit },
    });
    return response.data;
  },
};

export const alertsAPI = {
  getAlerts: async (params: {
    page?: number;
    page_size?: number;
    severity?: string;
    acknowledged?: boolean;
  }) => {
    const response = await apiClient.get('/alerts', { params });
    return response.data;
  },

  acknowledgeAlert: async (alertId: string, notes?: string) => {
    const response = await apiClient.post(`/alerts/${alertId}/acknowledge`, { notes });
    return response.data;
  },

  getUnreadCount: async () => {
    const response = await apiClient.get('/alerts/unread');
    return response.data;
  },
};
```

---

## 🧪 Testing Endpoints

```bash
# Install HTTPie (or use curl)
brew install httpie

# Set auth token
export TOKEN="your-jwt-token-here"

# Start agent
http POST localhost:8001/api/v1/agents/lead_scout/start "Authorization:Bearer $TOKEN"

# Get statuses
http GET localhost:8001/api/v1/agents/status "Authorization:Bearer $TOKEN"

# Get alerts
http GET localhost:8001/api/v1/alerts "Authorization:Bearer $TOKEN"

# Test WebSocket (use wscat)
npm install -g wscat
wscat -c ws://localhost:8001/api/v1/ws/cockpit
```

---

## 📊 Full API Documentation

Once the server is running:
- **Swagger UI**: http://localhost:8001/api/v1/docs
- **ReDoc**: http://localhost:8001/api/v1/redoc

---

## 🔒 Authentication

All endpoints require a valid Supabase JWT token in the `Authorization` header:

```
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

If token is missing or invalid, you'll get a 401 Unauthorized response.

---

## ⚡ Rate Limiting

API inherits rate limiting from FastAPI middleware:
- Agent control endpoints: 10 requests/minute per user
- Other endpoints: Standard rate limits apply

---

## 🐛 Error Responses

All errors follow this format:

```json
{
  "error": "ERROR_CODE",
  "message": "Human-readable error message",
  "details": { ... }
}
```

**Common Error Codes**:
- `VALIDATION_ERROR` (422) - Invalid request data
- `UNAUTHORIZED` (401) - Missing or invalid auth token
- `FORBIDDEN` (403) - Insufficient permissions
- `NOT_FOUND` (404) - Resource not found
- `INTERNAL_SERVER_ERROR` (500) - Server error

---

## 🚀 Integration Checklist

- [ ] Set up axios client with auth interceptor
- [ ] Create WebSocket hook (`useCockpitWebSocket`)
- [ ] Implement agent control UI (start/stop buttons)
- [ ] Display agent statuses in real-time
- [ ] Show alerts with severity badges
- [ ] Handle alert acknowledgement
- [ ] Show toast notifications for WebSocket events
- [ ] Implement auto-reconnect for WebSocket
- [ ] Add error handling for API failures
- [ ] Test with multiple agents running simultaneously

---

**Questions?** Check the full OpenAPI spec at `/api/v1/docs` when the server is running.
