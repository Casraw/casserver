#!/usr/bin/env python3
"""
Fee System Test Runner

Runs integration tests for the fee system components.
"""

import subprocess
import sys
import os

def run_fee_tests():
    """Run fee system integration tests."""
    print("🧪 Fee System Integration Test Runner")
    print("=====================================")
    
    # Set up environment
    os.environ['PYTHONPATH'] = os.getcwd()
    
    # Run integration tests
    print("\n📋 Running Fee System Integration Tests...")
    result = subprocess.run([
        sys.executable, '-m', 'pytest', 
        'tests/integration/test_fee_system_integration.py',
        '-v', '--tb=short'
    ], capture_output=False)
    
    if result.returncode == 0:
        print("\n✅ Fee system integration tests PASSED!")
        return True
    else:
        print("\n❌ Fee system integration tests FAILED!")
        return False

if __name__ == '__main__':
    success = run_fee_tests()
    sys.exit(0 if success else 1) 