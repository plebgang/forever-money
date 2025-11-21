#!/usr/bin/env python3
"""
Test script to verify miner endpoint functionality.
"""
import requests
import json
import sys


def test_miner(miner_url: str = "http://localhost:8000"):
    """Test miner endpoint with sample request."""

    # Sample validator request
    test_request = {
        "pairAddress": "0x0000000000000000000000000000000000000000",
        "chainId": 8453,
        "target_block": 12345678,
        "mode": "inventory",
        "inventory": {
            "amount0": "1000000000000000000",
            "amount1": "2500000000"
        },
        "current_positions": [],
        "metadata": {
            "round_id": "test-round-001",
            "constraints": {
                "max_il": 0.10,
                "min_tick_width": 60,
                "max_rebalances": 4
            }
        }
    }

    print(f"Testing miner at {miner_url}")
    print("=" * 60)

    # Test health endpoint
    print("\n1. Testing health endpoint...")
    try:
        response = requests.get(f"{miner_url}/health", timeout=5)
        print(f"   Status: {response.status_code}")
        print(f"   Response: {response.json()}")
    except Exception as e:
        print(f"   Error: {e}")
        return False

    # Test strategy endpoint
    print("\n2. Testing strategy prediction endpoint...")
    try:
        response = requests.post(
            f"{miner_url}/predict_strategy",
            json=test_request,
            timeout=30,
            headers={'Content-Type': 'application/json'}
        )

        print(f"   Status: {response.status_code}")

        if response.status_code == 200:
            data = response.json()
            print(f"   Response structure:")
            print(f"     - Number of positions: {len(data['strategy']['positions'])}")
            print(f"     - Has rebalance rule: {data['strategy']['rebalance_rule'] is not None}")
            print(f"     - Miner version: {data['miner_metadata']['version']}")
            print(f"     - Model info: {data['miner_metadata']['model_info']}")

            print(f"\n   Full response:")
            print(json.dumps(data, indent=2))

            # Validate positions
            print(f"\n3. Validating positions...")
            for i, pos in enumerate(data['strategy']['positions']):
                tick_width = pos['tickUpper'] - pos['tickLower']
                print(f"   Position {i+1}:")
                print(f"     - Tick range: [{pos['tickLower']}, {pos['tickUpper']}]")
                print(f"     - Tick width: {tick_width}")
                print(f"     - Allocation0: {pos['allocation0']}")
                print(f"     - Allocation1: {pos['allocation1']}")
                print(f"     - Confidence: {pos.get('confidence', 'N/A')}")

                if tick_width < 60:
                    print(f"     ⚠️  WARNING: Tick width below minimum (60)")

            return True
        else:
            print(f"   Error response: {response.text}")
            return False

    except Exception as e:
        print(f"   Error: {e}")
        return False


if __name__ == '__main__':
    miner_url = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"
    success = test_miner(miner_url)
    sys.exit(0 if success else 1)
