#!/usr/bin/env python3
"""
Disaster Recovery Drill Automation

This script automates the execution of disaster recovery drills
for the Check Review Console.

Usage:
    python scripts/dr-drills/run_drill.py --scenario database
    python scripts/dr-drills/run_drill.py --scenario application
    python scripts/dr-drills/run_drill.py --verify-only
    python scripts/dr-drills/run_drill.py --list-scenarios

Requirements:
    - Docker and docker-compose installed
    - Access to backup directory
    - Appropriate permissions
"""

import argparse
import json
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any


class DrillStatus(Enum):
    """Status of a drill step."""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class DrillStep:
    """A single step in a DR drill."""
    name: str
    description: str
    command: str | None = None
    verification: str | None = None
    status: DrillStatus = DrillStatus.PENDING
    duration_seconds: float = 0
    output: str = ""
    error: str = ""


@dataclass
class DrillResult:
    """Result of a DR drill."""
    drill_id: str
    scenario: str
    started_at: datetime
    completed_at: datetime | None = None
    status: DrillStatus = DrillStatus.PENDING
    steps: list[DrillStep] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)


class DrillRunner:
    """Runs disaster recovery drills."""

    SCENARIOS = {
        "database": {
            "name": "Database Failure Recovery",
            "description": "Simulates database failure and recovery from backup",
            "steps": [
                DrillStep(
                    name="pre_check",
                    description="Verify system health before drill",
                    command=None,
                    verification="curl -sf http://localhost:8000/health",
                ),
                DrillStep(
                    name="backup_verification",
                    description="Verify backup availability",
                    command="ls -la /backups/*.dump 2>/dev/null | head -5 || echo 'No backups found'",
                ),
                DrillStep(
                    name="simulate_failure",
                    description="Stop database container",
                    command="docker-compose stop db",
                ),
                DrillStep(
                    name="detect_failure",
                    description="Verify failure is detected",
                    verification="! docker exec check_review_db pg_isready -U postgres 2>/dev/null",
                ),
                DrillStep(
                    name="recovery_start",
                    description="Start database recovery",
                    command="docker-compose start db",
                ),
                DrillStep(
                    name="wait_for_recovery",
                    description="Wait for database to be ready",
                    command="sleep 15",
                ),
                DrillStep(
                    name="verify_database",
                    description="Verify database is operational",
                    verification="docker exec check_review_db pg_isready -U postgres",
                ),
                DrillStep(
                    name="verify_application",
                    description="Verify application connectivity",
                    verification="curl -sf http://localhost:8000/health",
                ),
                DrillStep(
                    name="verify_data",
                    description="Verify data integrity",
                    command="docker exec check_review_db psql -U postgres -d check_review -c 'SELECT count(*) FROM users;'",
                ),
            ],
        },
        "application": {
            "name": "Application Failure Recovery",
            "description": "Simulates backend application failure and recovery",
            "steps": [
                DrillStep(
                    name="pre_check",
                    description="Verify system health before drill",
                    verification="curl -sf http://localhost:8000/health",
                ),
                DrillStep(
                    name="simulate_failure",
                    description="Stop backend container",
                    command="docker-compose stop backend",
                ),
                DrillStep(
                    name="detect_failure",
                    description="Verify health check fails",
                    verification="! curl -sf http://localhost:8000/health 2>/dev/null",
                ),
                DrillStep(
                    name="recovery_start",
                    description="Start backend recovery",
                    command="docker-compose start backend",
                ),
                DrillStep(
                    name="wait_for_recovery",
                    description="Wait for backend to start",
                    command="sleep 20",
                ),
                DrillStep(
                    name="verify_health",
                    description="Verify health endpoint",
                    verification="curl -sf http://localhost:8000/health",
                ),
                DrillStep(
                    name="verify_metrics",
                    description="Verify metrics endpoint",
                    verification="curl -sf http://localhost:8000/metrics | head -1",
                ),
            ],
        },
        "redis": {
            "name": "Redis Cache Failure Recovery",
            "description": "Simulates Redis failure and recovery",
            "steps": [
                DrillStep(
                    name="pre_check",
                    description="Verify Redis is healthy",
                    verification="docker exec check_review_redis redis-cli ping",
                ),
                DrillStep(
                    name="simulate_failure",
                    description="Stop Redis container",
                    command="docker-compose stop redis",
                ),
                DrillStep(
                    name="recovery_start",
                    description="Start Redis recovery",
                    command="docker-compose start redis",
                ),
                DrillStep(
                    name="wait_for_recovery",
                    description="Wait for Redis to start",
                    command="sleep 10",
                ),
                DrillStep(
                    name="verify_redis",
                    description="Verify Redis is operational",
                    verification="docker exec check_review_redis redis-cli ping",
                ),
                DrillStep(
                    name="verify_application",
                    description="Verify application still works",
                    verification="curl -sf http://localhost:8000/health",
                ),
            ],
        },
    }

    def __init__(self, scenario: str, dry_run: bool = False):
        self.scenario = scenario
        self.dry_run = dry_run
        self.drill_id = f"DR-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        self.result = DrillResult(
            drill_id=self.drill_id,
            scenario=scenario,
            started_at=datetime.now(timezone.utc),
        )

    def run(self) -> DrillResult:
        """Execute the DR drill."""
        if self.scenario not in self.SCENARIOS:
            raise ValueError(f"Unknown scenario: {self.scenario}")

        scenario_config = self.SCENARIOS[self.scenario]
        print(f"\n{'='*60}")
        print(f"DISASTER RECOVERY DRILL: {scenario_config['name']}")
        print(f"Drill ID: {self.drill_id}")
        print(f"{'='*60}\n")

        if self.dry_run:
            print("*** DRY RUN MODE - No changes will be made ***\n")

        # Copy steps from scenario
        self.result.steps = [
            DrillStep(
                name=s.name,
                description=s.description,
                command=s.command,
                verification=s.verification,
            )
            for s in scenario_config["steps"]
        ]

        total_start = time.time()

        for i, step in enumerate(self.result.steps):
            print(f"[{i+1}/{len(self.result.steps)}] {step.description}")
            self._execute_step(step)

            if step.status == DrillStatus.FAILED:
                print(f"    FAILED: {step.error}")
                self.result.status = DrillStatus.FAILED
                break
            else:
                print(f"    OK ({step.duration_seconds:.1f}s)")

        total_duration = time.time() - total_start

        if self.result.status != DrillStatus.FAILED:
            self.result.status = DrillStatus.SUCCESS

        self.result.completed_at = datetime.now(timezone.utc)
        self.result.metrics = {
            "total_duration_seconds": total_duration,
            "steps_completed": sum(1 for s in self.result.steps if s.status == DrillStatus.SUCCESS),
            "steps_failed": sum(1 for s in self.result.steps if s.status == DrillStatus.FAILED),
        }

        self._print_summary()
        return self.result

    def _execute_step(self, step: DrillStep) -> None:
        """Execute a single drill step."""
        step.status = DrillStatus.RUNNING
        start_time = time.time()

        try:
            if step.command and not self.dry_run:
                result = subprocess.run(
                    step.command,
                    shell=True,
                    capture_output=True,
                    text=True,
                    timeout=120,
                )
                step.output = result.stdout
                if result.returncode != 0:
                    step.error = result.stderr or "Command failed"
                    step.status = DrillStatus.FAILED
                    return

            if step.verification:
                result = subprocess.run(
                    step.verification,
                    shell=True,
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                if result.returncode != 0:
                    step.error = result.stderr or "Verification failed"
                    step.status = DrillStatus.FAILED
                    return

            step.status = DrillStatus.SUCCESS

        except subprocess.TimeoutExpired:
            step.error = "Step timed out"
            step.status = DrillStatus.FAILED
        except Exception as e:
            step.error = str(e)
            step.status = DrillStatus.FAILED
        finally:
            step.duration_seconds = time.time() - start_time

    def _print_summary(self) -> None:
        """Print drill summary."""
        print(f"\n{'='*60}")
        print("DRILL SUMMARY")
        print(f"{'='*60}")
        print(f"Drill ID: {self.result.drill_id}")
        print(f"Scenario: {self.result.scenario}")
        print(f"Status: {self.result.status.value.upper()}")
        print(f"Duration: {self.result.metrics['total_duration_seconds']:.1f} seconds")
        print(f"Steps: {self.result.metrics['steps_completed']} completed, "
              f"{self.result.metrics['steps_failed']} failed")
        print(f"{'='*60}\n")


def verify_system() -> bool:
    """Verify system health without running a drill."""
    print("\n=== SYSTEM VERIFICATION ===\n")

    checks = [
        ("Backend API", "curl -sf http://localhost:8000/health"),
        ("Database", "docker exec check_review_db pg_isready -U postgres"),
        ("Redis", "docker exec check_review_redis redis-cli ping"),
        ("Prometheus", "curl -sf http://localhost:9090/-/healthy"),
    ]

    all_passed = True
    for name, command in checks:
        result = subprocess.run(command, shell=True, capture_output=True)
        status = "OK" if result.returncode == 0 else "FAIL"
        print(f"{name}: {status}")
        if result.returncode != 0:
            all_passed = False

    print("\n" + "="*40)
    if all_passed:
        print("All checks PASSED")
    else:
        print("Some checks FAILED")
    print("="*40 + "\n")

    return all_passed


def list_scenarios() -> None:
    """List available drill scenarios."""
    print("\n=== AVAILABLE DR DRILL SCENARIOS ===\n")
    for key, scenario in DrillRunner.SCENARIOS.items():
        print(f"  {key}:")
        print(f"    Name: {scenario['name']}")
        print(f"    Description: {scenario['description']}")
        print(f"    Steps: {len(scenario['steps'])}")
        print()


def main():
    parser = argparse.ArgumentParser(
        description="Run disaster recovery drills",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "--scenario",
        choices=list(DrillRunner.SCENARIOS.keys()),
        help="Drill scenario to execute",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without making changes",
    )
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="Only verify system health",
    )
    parser.add_argument(
        "--list-scenarios",
        action="store_true",
        help="List available scenarios",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Write results to JSON file",
    )

    args = parser.parse_args()

    if args.list_scenarios:
        list_scenarios()
        return 0

    if args.verify_only:
        success = verify_system()
        return 0 if success else 1

    if not args.scenario:
        parser.print_help()
        print("\nError: --scenario is required (or use --verify-only)")
        return 1

    runner = DrillRunner(args.scenario, dry_run=args.dry_run)
    result = runner.run()

    if args.output:
        with open(args.output, "w") as f:
            json.dump({
                "drill_id": result.drill_id,
                "scenario": result.scenario,
                "status": result.status.value,
                "started_at": result.started_at.isoformat(),
                "completed_at": result.completed_at.isoformat() if result.completed_at else None,
                "metrics": result.metrics,
                "steps": [
                    {
                        "name": s.name,
                        "description": s.description,
                        "status": s.status.value,
                        "duration_seconds": s.duration_seconds,
                        "error": s.error if s.error else None,
                    }
                    for s in result.steps
                ],
            }, f, indent=2)
        print(f"Results written to: {args.output}")

    return 0 if result.status == DrillStatus.SUCCESS else 1


if __name__ == "__main__":
    sys.exit(main())
