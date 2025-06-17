#!/usr/bin/env python3
"""
WebSocket Real-time Tests Runner

This script runs comprehensive tests for the WebSocket real-time functionality,
including unit tests for the WebSocket API, WebSocket notifier service, 
and integration tests for the complete real-time update flow.

Usage:
    python run_websocket_tests.py                          # Run all WebSocket tests
    python run_websocket_tests.py -v                       # Verbose output
    python run_websocket_tests.py --unit                   # Unit tests only
    python run_websocket_tests.py --integration            # Integration tests only
    python run_websocket_tests.py --coverage               # With coverage report
"""

import sys
import subprocess
import argparse
import os
from pathlib import Path

def run_command(command, description=""):
    """Run a command and return its exit code"""
    if description:
        print(f"\n{description}")
        print("=" * len(description))
    
    print(f"Running: {' '.join(command)}")
    result = subprocess.run(command, capture_output=False)
    return result.returncode

def main():
    parser = argparse.ArgumentParser(description="Run WebSocket real-time functionality tests")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output")
    parser.add_argument("--unit", action="store_true", help="Run only unit tests")
    parser.add_argument("--integration", action="store_true", help="Run only integration tests")
    parser.add_argument("--coverage", action="store_true", help="Run with coverage report")
    parser.add_argument("--html-coverage", action="store_true", help="Generate HTML coverage report")
    
    args = parser.parse_args()
    
    # Set up environment
    os.environ['PYTHONPATH'] = str(Path(__file__).parent.absolute())
    
    # Base pytest command
    base_cmd = ["python", "-m", "pytest"]
    
    if args.verbose:
        base_cmd.extend(["-v", "-s"])
    else:
        base_cmd.append("-v")
    
    # Add other pytest options
    base_cmd.extend([
        "--tb=short",
        "--color=yes"
    ])
    
    # Coverage options
    if args.coverage or args.html_coverage:
        base_cmd.extend([
            "--cov=backend.api.websocket_api",
            "--cov=backend.services.websocket_notifier",
            "--cov-report=term-missing"
        ])
        
        if args.html_coverage:
            base_cmd.extend(["--cov-report=html:htmlcov/websocket"])
    
    exit_code = 0
    
    print("🔌 WebSocket Real-time Functionality Test Suite")
    print("=" * 50)
    
    if args.unit or (not args.unit and not args.integration):
        print("\n📋 Running Unit Tests...")
        
        # WebSocket API unit tests
        unit_cmd = base_cmd + ["tests/api/test_websocket_api.py"]
        
        api_exit_code = run_command(
            unit_cmd,
            "🔌 WebSocket API Unit Tests"
        )
        
        # WebSocket notifier service unit tests
        service_cmd = base_cmd + ["tests/services/test_websocket_notifier.py"]
        
        service_exit_code = run_command(
            service_cmd,
            "🔔 WebSocket Notifier Service Unit Tests"
        )
        
        if api_exit_code != 0 or service_exit_code != 0:
            exit_code = 1
    
    if args.integration or (not args.unit and not args.integration):
        print("\n🔗 Running Integration Tests...")
        
        # WebSocket integration tests
        integration_cmd = base_cmd + ["integration_tests/test_realtime_websocket_integration.py"]
        
        integration_exit_code = run_command(
            integration_cmd,
            "🔗 WebSocket Real-time Integration Tests"
        )
        
        if integration_exit_code != 0:
            exit_code = 1
    
    # Summary
    print("\n" + "=" * 50)
    if exit_code == 0:
        print("✅ All WebSocket tests passed!")
        if args.coverage or args.html_coverage:
            print("\n📊 Coverage report generated")
            if args.html_coverage:
                print("   HTML report: htmlcov/websocket/index.html")
    else:
        print("❌ Some WebSocket tests failed")
        print("   Check the output above for details")
    
    print("=" * 50)
    
    return exit_code

if __name__ == "__main__":
    sys.exit(main()) 