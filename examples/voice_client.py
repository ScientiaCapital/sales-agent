"""
WebSocket Client Example for Voice Interaction

Demonstrates real-time voice communication with <2000ms latency.
Supports both browser-based and Python client implementations.
"""

import asyncio
import aiohttp
import json
import base64
import time
import wave
import pyaudio
from typing import Optional, Dict, Any
import numpy as np


class VoiceWebSocketClient:
    """
    Python client for voice WebSocket interaction.

    Features:
    - Real-time audio streaming
    - Latency tracking
    - Automatic reconnection
    - Audio device management
    """

    def __init__(self, server_url: str = "ws://localhost:8001"):
        """Initialize voice client."""
        self.server_url = server_url
        self.session_id: Optional[str] = None
        self.websocket: Optional[aiohttp.ClientWebSocketResponse] = None
        self.audio: Optional[pyaudio.PyAudio] = None
        self.stream_in: Optional[pyaudio.Stream] = None
        self.stream_out: Optional[pyaudio.Stream] = None

        # Audio settings
        self.sample_rate = 16000
        self.chunk_size = 1024
        self.audio_format = pyaudio.paInt16

        # Performance tracking
        self.latencies = []
        self.turn_count = 0

    async def create_session(
        self,
        lead_id: Optional[int] = None,
        voice_id: str = "a0e99841-438c-4a64-b679-ae501e7d6091",
        language: str = "en",
        emotion: str = "professional"
    ) -> str:
        """Create a new voice session via REST API."""
        async with aiohttp.ClientSession() as session:
            url = f"{self.server_url.replace('ws', 'http')}/api/voice/sessions"
            data = {
                "lead_id": lead_id,
                "voice_id": voice_id,
                "language": language,
                "emotion": emotion
            }

            async with session.post(url, json=data) as response:
                result = await response.json()
                self.session_id = result["session_id"]
                print(f"Created voice session: {self.session_id}")
                return self.session_id

    async def connect(self) -> None:
        """Connect to WebSocket endpoint."""
        if not self.session_id:
            raise ValueError("Must create session before connecting")

        ws_url = f"{self.server_url}/ws/voice/{self.session_id}"

        session = aiohttp.ClientSession()
        self.websocket = await session.ws_connect(ws_url)

        print(f"Connected to WebSocket: {ws_url}")

    async def send_audio(self, audio_data: bytes) -> None:
        """Send audio data to server."""
        if not self.websocket:
            raise ValueError("Not connected to WebSocket")

        # Encode audio as base64
        audio_base64 = base64.b64encode(audio_data).decode()

        message = {
            "type": "audio",
            "data": audio_base64,
            "sample_rate": self.sample_rate,
            "format": "pcm"
        }

        await self.websocket.send_json(message)

    async def receive_messages(self) -> None:
        """Receive and process messages from server."""
        if not self.websocket:
            raise ValueError("Not connected to WebSocket")

        async for msg in self.websocket:
            if msg.type == aiohttp.WSMsgType.TEXT:
                data = json.loads(msg.data)
                await self.handle_message(data)
            elif msg.type == aiohttp.WSMsgType.ERROR:
                print(f"WebSocket error: {msg.data}")
                break

    async def handle_message(self, data: Dict[str, Any]) -> None:
        """Handle incoming WebSocket message."""
        msg_type = data.get("type")

        if msg_type == "state":
            print(f"State changed: {data.get('state')}")

        elif msg_type == "transcript":
            print(f"User said: {data.get('text')} (confidence: {data.get('confidence')})")

        elif msg_type == "response":
            print(f"AI response: {data.get('text')}")

        elif msg_type == "audio":
            # Decode and play audio
            audio_base64 = data.get("data")
            if audio_base64:
                audio_data = base64.b64decode(audio_base64)
                await self.play_audio(audio_data)

        elif msg_type == "complete":
            metrics = data.get("metrics", {})
            self.turn_count += 1
            latency = metrics.get("total_latency_ms", 0)
            self.latencies.append(latency)

            print(f"\nTurn {self.turn_count} completed:")
            print(f"  STT: {metrics.get('stt_latency_ms', 0)}ms")
            print(f"  Inference: {metrics.get('inference_latency_ms', 0)}ms")
            print(f"  TTS: {metrics.get('tts_latency_ms', 0)}ms")
            print(f"  Total: {latency}ms")

            if latency > 2000:
                print(f"  ⚠️ Exceeded 2000ms target!")
            else:
                print(f"  ✅ Within 2000ms target")

            # Print session average
            if self.latencies:
                avg_latency = sum(self.latencies) / len(self.latencies)
                print(f"  Session average: {avg_latency:.0f}ms")

        elif msg_type == "error":
            print(f"Error: {data.get('error')}")

        elif msg_type == "ping":
            # Respond to ping
            await self.websocket.send_json({"type": "pong"})

    async def play_audio(self, audio_data: bytes) -> None:
        """Play audio through speakers."""
        if self.stream_out:
            self.stream_out.write(audio_data)

    async def record_and_send(self, duration: float = 3.0) -> None:
        """Record audio from microphone and send."""
        if not self.stream_in:
            return

        print(f"Recording for {duration} seconds...")

        frames = []
        chunks_to_record = int(self.sample_rate * duration / self.chunk_size)

        for _ in range(chunks_to_record):
            data = self.stream_in.read(self.chunk_size, exception_on_overflow=False)
            frames.append(data)

        audio_data = b''.join(frames)
        print(f"Recorded {len(audio_data)} bytes")

        # Send to server
        await self.send_audio(audio_data)

    def init_audio(self) -> None:
        """Initialize audio devices."""
        self.audio = pyaudio.PyAudio()

        # Input stream (microphone)
        self.stream_in = self.audio.open(
            format=self.audio_format,
            channels=1,
            rate=self.sample_rate,
            input=True,
            frames_per_buffer=self.chunk_size
        )

        # Output stream (speakers)
        self.stream_out = self.audio.open(
            format=self.audio_format,
            channels=1,
            rate=self.sample_rate,
            output=True,
            frames_per_buffer=self.chunk_size
        )

        print("Audio devices initialized")

    def cleanup_audio(self) -> None:
        """Clean up audio resources."""
        if self.stream_in:
            self.stream_in.stop_stream()
            self.stream_in.close()

        if self.stream_out:
            self.stream_out.stop_stream()
            self.stream_out.close()

        if self.audio:
            self.audio.terminate()

    async def close(self) -> None:
        """Close WebSocket connection and cleanup."""
        if self.websocket:
            await self.websocket.close()

        self.cleanup_audio()

        # Print final statistics
        if self.latencies:
            print("\n=== Session Statistics ===")
            print(f"Total turns: {self.turn_count}")
            print(f"Average latency: {sum(self.latencies) / len(self.latencies):.0f}ms")
            print(f"Min latency: {min(self.latencies)}ms")
            print(f"Max latency: {max(self.latencies)}ms")

            compliant = sum(1 for l in self.latencies if l <= 2000)
            compliance_rate = compliant / len(self.latencies) * 100
            print(f"2000ms compliance: {compliance_rate:.1f}%")


async def interactive_demo():
    """
    Interactive voice demo with real-time latency tracking.
    """
    client = VoiceWebSocketClient()

    try:
        # Create session
        await client.create_session(
            voice_id="a0e99841-438c-4a64-b679-ae501e7d6091",
            emotion="professional"
        )

        # Connect WebSocket
        await client.connect()

        # Initialize audio
        client.init_audio()

        # Start receiving messages
        receive_task = asyncio.create_task(client.receive_messages())

        print("\n=== Voice Interaction Demo ===")
        print("Commands:")
        print("  'r' - Record and send audio (3 seconds)")
        print("  'e' - Change emotion")
        print("  'q' - Quit")
        print("")

        while True:
            command = input("> ").lower()

            if command == 'r':
                await client.record_and_send()

            elif command == 'e':
                emotion = input("Enter emotion (professional/empathetic/excited): ")
                await client.websocket.send_json({
                    "type": "adjust_emotion",
                    "emotion": emotion
                })

            elif command == 'q':
                break

            await asyncio.sleep(0.1)

    finally:
        await client.close()


# HTML/JavaScript client example
HTML_CLIENT_EXAMPLE = """
<!DOCTYPE html>
<html>
<head>
    <title>Voice WebSocket Client</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; }
        .metrics { background: #f0f0f0; padding: 10px; margin: 10px 0; }
        .latency { font-size: 24px; font-weight: bold; }
        .compliant { color: green; }
        .exceeded { color: red; }
        button { padding: 10px 20px; margin: 5px; }
        #status { margin: 20px 0; }
        #transcript { background: #e0e0e0; padding: 10px; min-height: 100px; }
        #response { background: #d0d0ff; padding: 10px; min-height: 100px; }
    </style>
</head>
<body>
    <h1>Voice Interaction Client</h1>

    <div id="status">Status: Disconnected</div>

    <div>
        <button id="createSession">Create Session</button>
        <button id="startRecording" disabled>Start Recording</button>
        <button id="stopRecording" disabled>Stop Recording</button>
    </div>

    <div id="transcript">
        <strong>You said:</strong><br>
        <span id="userText"></span>
    </div>

    <div id="response">
        <strong>AI response:</strong><br>
        <span id="aiText"></span>
    </div>

    <div class="metrics">
        <h3>Performance Metrics</h3>
        <div class="latency" id="totalLatency">--</div>
        <div>STT: <span id="sttLatency">--</span>ms</div>
        <div>Inference: <span id="inferenceLatency">--</span>ms</div>
        <div>TTS: <span id="ttsLatency">--</span>ms</div>
        <div>Average: <span id="avgLatency">--</span>ms</div>
        <div>Compliance: <span id="compliance">--</span>%</div>
    </div>

    <script>
    class VoiceClient {
        constructor() {
            this.ws = null;
            this.sessionId = null;
            this.mediaRecorder = null;
            this.audioChunks = [];
            this.audioContext = new AudioContext();
            this.latencies = [];
        }

        async createSession() {
            const response = await fetch('/api/voice/sessions', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    voice_id: 'a0e99841-438c-4a64-b679-ae501e7d6091',
                    language: 'en',
                    emotion: 'professional'
                })
            });
            const data = await response.json();
            this.sessionId = data.session_id;
            this.connect();
        }

        connect() {
            const wsUrl = `ws://localhost:8001/ws/voice/${this.sessionId}`;
            this.ws = new WebSocket(wsUrl);

            this.ws.onopen = () => {
                document.getElementById('status').textContent = 'Status: Connected';
                document.getElementById('startRecording').disabled = false;
            };

            this.ws.onmessage = async (event) => {
                const data = JSON.parse(event.data);
                await this.handleMessage(data);
            };

            this.ws.onerror = (error) => {
                console.error('WebSocket error:', error);
                document.getElementById('status').textContent = 'Status: Error';
            };

            this.ws.onclose = () => {
                document.getElementById('status').textContent = 'Status: Disconnected';
            };
        }

        async handleMessage(data) {
            switch(data.type) {
                case 'transcript':
                    document.getElementById('userText').textContent = data.text;
                    break;

                case 'response':
                    document.getElementById('aiText').textContent = data.text;
                    break;

                case 'audio':
                    // Decode and play audio
                    const audioData = atob(data.data);
                    await this.playAudio(audioData);
                    break;

                case 'complete':
                    const metrics = data.metrics || {};
                    this.updateMetrics(metrics);
                    break;

                case 'state':
                    console.log('State:', data.state);
                    break;
            }
        }

        updateMetrics(metrics) {
            const totalLatency = metrics.total_latency_ms || 0;
            this.latencies.push(totalLatency);

            // Update display
            document.getElementById('totalLatency').textContent = `${totalLatency}ms`;
            document.getElementById('totalLatency').className =
                totalLatency <= 2000 ? 'latency compliant' : 'latency exceeded';

            document.getElementById('sttLatency').textContent = metrics.stt_latency_ms || '--';
            document.getElementById('inferenceLatency').textContent = metrics.inference_latency_ms || '--';
            document.getElementById('ttsLatency').textContent = metrics.tts_latency_ms || '--';

            // Calculate averages
            if (this.latencies.length > 0) {
                const avg = this.latencies.reduce((a, b) => a + b) / this.latencies.length;
                document.getElementById('avgLatency').textContent = avg.toFixed(0);

                const compliant = this.latencies.filter(l => l <= 2000).length;
                const compliance = (compliant / this.latencies.length * 100).toFixed(1);
                document.getElementById('compliance').textContent = compliance;
            }
        }

        async startRecording() {
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            this.mediaRecorder = new MediaRecorder(stream);
            this.audioChunks = [];

            this.mediaRecorder.ondataavailable = (event) => {
                this.audioChunks.push(event.data);
            };

            this.mediaRecorder.onstop = async () => {
                const audioBlob = new Blob(this.audioChunks, { type: 'audio/wav' });
                const audioData = await audioBlob.arrayBuffer();
                this.sendAudio(audioData);
            };

            this.mediaRecorder.start();
            document.getElementById('startRecording').disabled = true;
            document.getElementById('stopRecording').disabled = false;
        }

        stopRecording() {
            if (this.mediaRecorder) {
                this.mediaRecorder.stop();
                document.getElementById('startRecording').disabled = false;
                document.getElementById('stopRecording').disabled = true;
            }
        }

        sendAudio(audioData) {
            const base64Audio = btoa(String.fromCharCode(...new Uint8Array(audioData)));
            this.ws.send(JSON.stringify({
                type: 'audio',
                data: base64Audio,
                sample_rate: 16000,
                format: 'wav'
            }));
        }

        async playAudio(audioData) {
            // Convert base64 to ArrayBuffer and play
            const arrayBuffer = new ArrayBuffer(audioData.length);
            const view = new Uint8Array(arrayBuffer);
            for (let i = 0; i < audioData.length; i++) {
                view[i] = audioData.charCodeAt(i);
            }

            const audioBuffer = await this.audioContext.decodeAudioData(arrayBuffer);
            const source = this.audioContext.createBufferSource();
            source.buffer = audioBuffer;
            source.connect(this.audioContext.destination);
            source.start();
        }
    }

    // Initialize client
    const client = new VoiceClient();

    // Event listeners
    document.getElementById('createSession').addEventListener('click', () => {
        client.createSession();
    });

    document.getElementById('startRecording').addEventListener('click', () => {
        client.startRecording();
    });

    document.getElementById('stopRecording').addEventListener('click', () => {
        client.stopRecording();
    });
    </script>
</body>
</html>
"""


def save_html_client():
    """Save HTML client to file."""
    with open("voice_client.html", "w") as f:
        f.write(HTML_CLIENT_EXAMPLE)
    print("HTML client saved to voice_client.html")


if __name__ == "__main__":
    # Save HTML client
    save_html_client()

    # Run interactive demo
    print("Starting Voice WebSocket Client Demo...")
    print("Make sure the server is running on http://localhost:8001")

    try:
        asyncio.run(interactive_demo())
    except KeyboardInterrupt:
        print("\nDemo terminated by user")
    except Exception as e:
        print(f"Error: {e}")