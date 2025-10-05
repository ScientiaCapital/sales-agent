"""
Voice Latency Benchmark - Verify <2000ms Target

Runs comprehensive latency tests to ensure voice turn targets are met:
- STT: <150ms
- Inference: <633ms
- TTS: <200ms
- Total: <2000ms

Generates detailed performance report with percentiles and compliance rates.
"""

import asyncio
import time
import statistics
import json
from dataclasses import dataclass, asdict
from typing import List, Dict, Any
import numpy as np
from datetime import datetime
import sys
import os

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.services.voice_agent import VoiceAgent, VoiceEmotion
from app.services.cartesia_service import VoiceConfig


@dataclass
class LatencyMeasurement:
    """Single latency measurement."""
    turn_number: int
    stt_ms: float
    inference_ms: float
    tts_ms: float
    total_ms: float
    met_target: bool
    timestamp: str


class VoiceLatencyBenchmark:
    """
    Comprehensive voice latency benchmarking tool.

    Tests various scenarios and generates detailed performance reports.
    """

    def __init__(self):
        self.agent: VoiceAgent = None
        self.measurements: List[LatencyMeasurement] = []
        self.scenarios_tested = 0

    async def setup(self):
        """Initialize voice agent and services."""
        self.agent = VoiceAgent()
        await self.agent.initialize()
        print("Voice agent initialized successfully")

    async def benchmark_single_turn(
        self,
        audio_size: int = 16000,  # 1 second of audio at 16kHz
        text_length: int = 50,
        emotion: VoiceEmotion = VoiceEmotion.PROFESSIONAL
    ) -> LatencyMeasurement:
        """
        Benchmark a single voice turn.

        Args:
            audio_size: Size of audio data in bytes
            text_length: Approximate length of response text
            emotion: Voice emotion setting

        Returns:
            LatencyMeasurement with breakdown
        """
        # Create session
        session = await self.agent.create_session(
            voice_id="benchmark_voice",
            emotion=emotion
        )

        # Generate mock audio data
        audio_data = b"x" * audio_size

        # Track metrics
        turn_metrics = None
        start_time = time.perf_counter()

        # Process turn
        async for chunk in self.agent.process_audio_turn(
            session_id=session.session_id,
            audio_data=audio_data,
            sample_rate=16000
        ):
            if chunk["type"] == "complete":
                turn_metrics = chunk["metrics"]

        # Clean up session
        await self.agent.close_session(session.session_id)

        if turn_metrics:
            measurement = LatencyMeasurement(
                turn_number=len(self.measurements) + 1,
                stt_ms=turn_metrics.get("stt_latency_ms", 0),
                inference_ms=turn_metrics.get("inference_latency_ms", 0),
                tts_ms=turn_metrics.get("tts_latency_ms", 0),
                total_ms=turn_metrics.get("total_latency_ms", 0),
                met_target=turn_metrics.get("total_latency_ms", 0) < 2000,
                timestamp=datetime.now().isoformat()
            )
            self.measurements.append(measurement)
            return measurement

        return None

    async def run_scenario(
        self,
        name: str,
        iterations: int = 10,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Run a specific benchmark scenario.

        Args:
            name: Scenario name
            iterations: Number of iterations
            **kwargs: Parameters for benchmark_single_turn

        Returns:
            Scenario results with statistics
        """
        print(f"\n=== Scenario: {name} ===")
        scenario_measurements = []

        for i in range(iterations):
            print(f"  Turn {i+1}/{iterations}...", end="")
            measurement = await self.benchmark_single_turn(**kwargs)

            if measurement:
                scenario_measurements.append(measurement)
                status = "✅" if measurement.met_target else "❌"
                print(f" {measurement.total_ms:.0f}ms {status}")
            else:
                print(" Failed")

            # Small delay between turns
            await asyncio.sleep(0.5)

        # Calculate statistics
        if scenario_measurements:
            total_latencies = [m.total_ms for m in scenario_measurements]
            stt_latencies = [m.stt_ms for m in scenario_measurements]
            inference_latencies = [m.inference_ms for m in scenario_measurements]
            tts_latencies = [m.tts_ms for m in scenario_measurements]

            compliance = sum(1 for m in scenario_measurements if m.met_target)
            compliance_rate = compliance / len(scenario_measurements) * 100

            results = {
                "scenario": name,
                "iterations": iterations,
                "compliance_rate": compliance_rate,
                "total": {
                    "mean": statistics.mean(total_latencies),
                    "median": statistics.median(total_latencies),
                    "stdev": statistics.stdev(total_latencies) if len(total_latencies) > 1 else 0,
                    "min": min(total_latencies),
                    "max": max(total_latencies),
                    "p50": np.percentile(total_latencies, 50),
                    "p95": np.percentile(total_latencies, 95),
                    "p99": np.percentile(total_latencies, 99)
                },
                "stt": {
                    "mean": statistics.mean(stt_latencies),
                    "p95": np.percentile(stt_latencies, 95)
                },
                "inference": {
                    "mean": statistics.mean(inference_latencies),
                    "p95": np.percentile(inference_latencies, 95)
                },
                "tts": {
                    "mean": statistics.mean(tts_latencies),
                    "p95": np.percentile(tts_latencies, 95)
                }
            }

            self.scenarios_tested += 1
            return results

        return None

    async def run_comprehensive_benchmark(self) -> Dict[str, Any]:
        """
        Run comprehensive benchmark with multiple scenarios.

        Returns:
            Complete benchmark results
        """
        print("\n" + "=" * 60)
        print("VOICE LATENCY BENCHMARK")
        print("Target: <2000ms per voice turn")
        print("=" * 60)

        await self.setup()

        scenario_results = []

        # Scenario 1: Short utterances (typical)
        result = await self.run_scenario(
            name="Short Utterances",
            iterations=10,
            audio_size=8000,  # 0.5 seconds
            text_length=30
        )
        if result:
            scenario_results.append(result)

        # Scenario 2: Medium utterances
        result = await self.run_scenario(
            name="Medium Utterances",
            iterations=10,
            audio_size=16000,  # 1 second
            text_length=50
        )
        if result:
            scenario_results.append(result)

        # Scenario 3: Long utterances
        result = await self.run_scenario(
            name="Long Utterances",
            iterations=5,
            audio_size=32000,  # 2 seconds
            text_length=100
        )
        if result:
            scenario_results.append(result)

        # Scenario 4: Different emotions
        for emotion in [VoiceEmotion.PROFESSIONAL, VoiceEmotion.EMPATHETIC, VoiceEmotion.EXCITED]:
            result = await self.run_scenario(
                name=f"Emotion: {emotion.value}",
                iterations=5,
                audio_size=16000,
                text_length=50,
                emotion=emotion
            )
            if result:
                scenario_results.append(result)

        # Generate report
        report = self.generate_report(scenario_results)
        return report

    def generate_report(self, scenario_results: List[Dict]) -> Dict[str, Any]:
        """Generate comprehensive benchmark report."""
        # Overall statistics
        all_measurements = self.measurements
        if not all_measurements:
            return {"error": "No measurements collected"}

        total_latencies = [m.total_ms for m in all_measurements]
        compliant = sum(1 for m in all_measurements if m.met_target)

        report = {
            "timestamp": datetime.now().isoformat(),
            "summary": {
                "total_turns": len(all_measurements),
                "scenarios_tested": self.scenarios_tested,
                "overall_compliance_rate": compliant / len(all_measurements) * 100,
                "target_latency_ms": 2000
            },
            "overall_latency": {
                "mean": statistics.mean(total_latencies),
                "median": statistics.median(total_latencies),
                "stdev": statistics.stdev(total_latencies) if len(total_latencies) > 1 else 0,
                "min": min(total_latencies),
                "max": max(total_latencies),
                "p50": np.percentile(total_latencies, 50),
                "p90": np.percentile(total_latencies, 90),
                "p95": np.percentile(total_latencies, 95),
                "p99": np.percentile(total_latencies, 99)
            },
            "component_breakdown": {
                "stt": {
                    "mean": statistics.mean([m.stt_ms for m in all_measurements]),
                    "target": 150
                },
                "inference": {
                    "mean": statistics.mean([m.inference_ms for m in all_measurements]),
                    "target": 633
                },
                "tts": {
                    "mean": statistics.mean([m.tts_ms for m in all_measurements]),
                    "target": 200
                }
            },
            "scenarios": scenario_results,
            "measurements": [asdict(m) for m in all_measurements[-20:]]  # Last 20 measurements
        }

        return report

    def print_report(self, report: Dict[str, Any]):
        """Print formatted benchmark report."""
        print("\n" + "=" * 60)
        print("BENCHMARK RESULTS")
        print("=" * 60)

        # Summary
        summary = report["summary"]
        print(f"\nTotal Turns: {summary['total_turns']}")
        print(f"Scenarios Tested: {summary['scenarios_tested']}")
        print(f"Overall Compliance: {summary['overall_compliance_rate']:.1f}%")

        # Overall latency
        latency = report["overall_latency"]
        print(f"\nOverall Latency Statistics:")
        print(f"  Mean: {latency['mean']:.0f}ms")
        print(f"  Median: {latency['median']:.0f}ms")
        print(f"  Std Dev: {latency['stdev']:.0f}ms")
        print(f"  Min: {latency['min']:.0f}ms")
        print(f"  Max: {latency['max']:.0f}ms")
        print(f"  P50: {latency['p50']:.0f}ms")
        print(f"  P90: {latency['p90']:.0f}ms")
        print(f"  P95: {latency['p95']:.0f}ms")
        print(f"  P99: {latency['p99']:.0f}ms")

        # Component breakdown
        components = report["component_breakdown"]
        print(f"\nComponent Breakdown:")
        for component, stats in components.items():
            status = "✅" if stats["mean"] <= stats["target"] else "⚠️"
            print(f"  {component.upper()}: {stats['mean']:.0f}ms (target: {stats['target']}ms) {status}")

        # Scenario results
        print(f"\nScenario Results:")
        for scenario in report["scenarios"]:
            print(f"\n  {scenario['scenario']}:")
            print(f"    Compliance: {scenario['compliance_rate']:.1f}%")
            print(f"    Mean: {scenario['total']['mean']:.0f}ms")
            print(f"    P95: {scenario['total']['p95']:.0f}ms")
            print(f"    P99: {scenario['total']['p99']:.0f}ms")

        # Final verdict
        print("\n" + "=" * 60)
        if summary["overall_compliance_rate"] >= 95:
            print("✅ BENCHMARK PASSED - System meets <2000ms target!")
        elif summary["overall_compliance_rate"] >= 90:
            print("⚠️ BENCHMARK MARGINAL - System mostly meets target")
        else:
            print("❌ BENCHMARK FAILED - System does not meet target")
        print("=" * 60)

    def save_report(self, report: Dict[str, Any], filename: str = "voice_latency_report.json"):
        """Save benchmark report to file."""
        with open(filename, "w") as f:
            json.dump(report, f, indent=2)
        print(f"\nReport saved to {filename}")


async def main():
    """Run voice latency benchmark."""
    benchmark = VoiceLatencyBenchmark()

    try:
        # Run comprehensive benchmark
        report = await benchmark.run_comprehensive_benchmark()

        # Print report
        benchmark.print_report(report)

        # Save report
        benchmark.save_report(report)

        # Check if targets are met
        if report["summary"]["overall_compliance_rate"] >= 95:
            print("\n🎉 Voice system successfully meets <2000ms latency target!")
            return 0
        else:
            print("\n⚠️ Voice system needs optimization to meet latency target")
            return 1

    except Exception as e:
        print(f"\n❌ Benchmark failed: {e}")
        return 1


if __name__ == "__main__":
    print("Starting Voice Latency Benchmark...")
    print("This will run multiple scenarios to verify <2000ms turn latency")
    print("Note: Requires Cartesia API key and running Redis")

    exit_code = asyncio.run(main())
    sys.exit(exit_code)