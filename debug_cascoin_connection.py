#!/usr/bin/env python3
"""
Debug script for Cascoin RPC connection issues
"""
import requests
import json
import time
import os
import sys

def test_cascoin_connection(rpc_url, rpc_user, rpc_password, timeout=10):
    """Test Cascoin RPC connection with various methods"""
    
    print(f"Testing Cascoin RPC connection...")
    print(f"URL: {rpc_url}")
    print(f"User: {rpc_user}")
    print(f"Password: {'*' * len(rpc_password) if rpc_password else 'None'}")
    print(f"Timeout: {timeout}s")
    print("-" * 50)
    
    # Test 1: Basic connectivity
    print("1. Testing basic connectivity...")
    try:
        response = requests.get(rpc_url, timeout=timeout)
        print(f"   ✓ HTTP connection successful (status: {response.status_code})")
    except requests.exceptions.Timeout:
        print(f"   ✗ Connection timeout after {timeout}s")
        return False
    except requests.exceptions.ConnectionError as e:
        print(f"   ✗ Connection error: {e}")
        return False
    except Exception as e:
        print(f"   ✗ Other error: {e}")
        return False
    
    # Test 2: RPC authentication
    print("2. Testing RPC authentication...")
    try:
        payload = json.dumps({
            "jsonrpc": "2.0",
            "id": "test",
            "method": "getblockchaininfo",
            "params": []
        })
        
        response = requests.post(
            rpc_url,
            auth=(rpc_user, rpc_password),
            data=payload,
            headers={'Content-Type': 'application/json'},
            timeout=timeout
        )
        
        if response.status_code == 401:
            print("   ✗ Authentication failed (401 Unauthorized)")
            return False
        elif response.status_code == 200:
            print("   ✓ Authentication successful")
        else:
            print(f"   ? Unexpected status code: {response.status_code}")
            
    except requests.exceptions.Timeout:
        print(f"   ✗ Authentication test timeout after {timeout}s")
        return False
    except Exception as e:
        print(f"   ✗ Authentication test error: {e}")
        return False
    
    # Test 3: getblockchaininfo RPC call
    print("3. Testing getblockchaininfo RPC call...")
    try:
        data = response.json()
        if data.get("error"):
            print(f"   ✗ RPC error: {data['error']}")
            return False
        
        result = data.get("result")
        if result:
            print(f"   ✓ Blockchain info retrieved:")
            print(f"     Chain: {result.get('chain', 'Unknown')}")
            print(f"     Blocks: {result.get('blocks', 'Unknown')}")
            print(f"     Difficulty: {result.get('difficulty', 'Unknown')}")
        else:
            print("   ✗ No result in response")
            return False
            
    except json.JSONDecodeError:
        print(f"   ✗ Invalid JSON response: {response.text[:200]}...")
        return False
    except Exception as e:
        print(f"   ✗ Error parsing response: {e}")
        return False
    
    # Test 4: getnewaddress RPC call
    print("4. Testing getnewaddress RPC call...")
    try:
        payload = json.dumps({
            "jsonrpc": "2.0",
            "id": "test_address",
            "method": "getnewaddress",
            "params": []
        })
        
        response = requests.post(
            rpc_url,
            auth=(rpc_user, rpc_password),
            data=payload,
            headers={'Content-Type': 'application/json'},
            timeout=timeout
        )
        
        if response.status_code == 200:
            data = response.json()
            if data.get("error"):
                print(f"   ✗ RPC error: {data['error']}")
                # Try with label parameter (Bitcoin Core style)
                print("   Trying with label parameter...")
                payload = json.dumps({
                    "jsonrpc": "2.0",
                    "id": "test_address_label",
                    "method": "getnewaddress",
                    "params": [""]
                })
                
                response = requests.post(
                    rpc_url,
                    auth=(rpc_user, rpc_password),
                    data=payload,
                    headers={'Content-Type': 'application/json'},
                    timeout=timeout
                )
                
                if response.status_code == 200:
                    data = response.json()
                    if data.get("error"):
                        print(f"   ✗ RPC error with label: {data['error']}")
                    else:
                        address = data.get("result")
                        if address:
                            print(f"   ✓ New address generated with label: {address}")
                        else:
                            print("   ✗ No address returned")
                else:
                    print(f"   ✗ HTTP error with label: {response.status_code}")
            else:
                address = data.get("result")
                if address:
                    print(f"   ✓ New address generated: {address}")
                else:
                    print("   ✗ No address returned")
        else:
            print(f"   ✗ HTTP error: {response.status_code}")
            
    except requests.exceptions.Timeout:
        print(f"   ✗ getnewaddress timeout after {timeout}s")
        return False
    except Exception as e:
        print(f"   ✗ getnewaddress error: {e}")
        return False
    
    print("5. Testing with different timeout values...")
    for test_timeout in [30, 60]:
        print(f"   Testing with {test_timeout}s timeout...")
        try:
            payload = json.dumps({
                "jsonrpc": "2.0",
                "id": "timeout_test",
                "method": "getblockchaininfo",
                "params": []
            })
            
            start_time = time.time()
            response = requests.post(
                rpc_url,
                auth=(rpc_user, rpc_password),
                data=payload,
                headers={'Content-Type': 'application/json'},
                timeout=test_timeout
            )
            end_time = time.time()
            
            if response.status_code == 200:
                print(f"     ✓ Success with {test_timeout}s timeout (took {end_time - start_time:.2f}s)")
            else:
                print(f"     ✗ Failed with {test_timeout}s timeout (status: {response.status_code})")
                
        except requests.exceptions.Timeout:
            print(f"     ✗ Still timeout after {test_timeout}s")
        except Exception as e:
            print(f"     ✗ Error with {test_timeout}s timeout: {e}")
    
    return True

def main():
    # Get connection details from environment or use defaults
    rpc_url = os.getenv("CASCOIN_RPC_URL", "http://172.17.0.1:22222")
    rpc_user = os.getenv("CASCOIN_RPC_USER", "cascoin")
    rpc_password = os.getenv("CASCOIN_RPC_PASSWORD", "")
    
    # Ensure RPC URL is correctly formatted
    if not rpc_url.startswith("http://") and not rpc_url.startswith("https://"):
        rpc_url = "http://" + rpc_url
    
    print("=" * 60)
    print("CASCOIN RPC CONNECTION DIAGNOSTIC")
    print("=" * 60)
    
    if len(sys.argv) > 1:
        rpc_url = sys.argv[1]
    if len(sys.argv) > 2:
        rpc_user = sys.argv[2]
    if len(sys.argv) > 3:
        rpc_password = sys.argv[3]
    
    print(f"You can override settings with:")
    print(f"python {sys.argv[0]} <rpc_url> <rpc_user> <rpc_password>")
    print()
    
    # Test the connection
    success = test_cascoin_connection(rpc_url, rpc_user, rpc_password)
    
    print()
    print("=" * 60)
    if success:
        print("✓ CONNECTION DIAGNOSTIC COMPLETED")
        print("The Cascoin node appears to be accessible.")
        print("If you're still having issues, try:")
        print("1. Increasing the timeout in CascoinService (line 31)")
        print("2. Check if the Cascoin node is fully synced")
        print("3. Verify wallet is unlocked (if required)")
    else:
        print("✗ CONNECTION ISSUES DETECTED")
        print("Recommendations:")
        print("1. Verify Cascoin node is running and accessible")
        print("2. Check network connectivity to 172.17.0.1:22222")
        print("3. Verify RPC credentials")
        print("4. Check Cascoin node configuration (rpcallowip, rpcbind)")
        print("5. Consider increasing timeout values")
    print("=" * 60)

if __name__ == "__main__":
    main() 