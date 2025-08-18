#!/usr/bin/env python3
"""
Demonstrate the retry backoff behavior for disk I/O errors.
Shows the retry intervals: 1s → 3s → 5s → 9s → 12s → 15s
"""

import time
import sys

def show_retry_timeline():
    """Visualize the retry timeline."""
    
    intervals = [1, 3, 5, 9, 12, 15, 15, 15]  # Seconds
    
    print("\n" + "="*70)
    print("DISK I/O ERROR RETRY BACKOFF DEMONSTRATION")
    print("="*70)
    print("\nRetry intervals: 1s → 3s → 5s → 9s → 12s → 15s (then stays at 15s)\n")
    
    # Show timeline
    print("Timeline visualization (each '-' = 1 second):")
    print("\nTime:  0" + "".join(f"{i:>5}" for i in range(10, 61, 10)))
    print("       |" + "----+"*12)
    
    timeline = [' '] * 60
    cumulative = 0
    for i, interval in enumerate(intervals[:6]):
        cumulative += interval
        if cumulative < 60:
            timeline[cumulative] = str(i+1)
    
    # Add more retries at 15s intervals
    while cumulative < 60:
        cumulative += 15
        if cumulative < 60:
            timeline[cumulative] = 'R'
    
    print("Retry: " + "".join(timeline))
    print("\nLegend: 1-6 = Retry attempts, R = Additional retries at 15s intervals")
    
    print("\n" + "-"*70)
    print("\nDetailed retry schedule:")
    print("-"*70)
    
    cumulative = 0
    for i, interval in enumerate(intervals):
        cumulative += interval
        print(f"Retry #{i+1:2d}: Wait {interval:2d}s → Attempt at t={cumulative:3d}s")
        if i == 5:
            print("           (All subsequent retries every 15s)")
            break
    
    print("\n" + "="*70)
    print("SIMULATING ACTUAL RETRY BEHAVIOR")
    print("="*70)
    
    print("\n[00:00] ❌ Initial write failed - disk I/O error detected")
    print("        💾 Reading buffered in memory")
    
    cumulative = 0
    for i, interval in enumerate(intervals[:6]):
        cumulative += interval
        mins = cumulative // 60
        secs = cumulative % 60
        
        print(f"\n[{mins:02d}:{secs:02d}] ⏳ Waiting {interval}s before retry #{i+1}...")
        time.sleep(min(interval, 2))  # Sleep max 2 seconds for demo
        
        if i < 3:
            print(f"[{mins:02d}:{secs:02d}] 🔄 Retry #{i+1} - Still failing (disk I/O error persists)")
        elif i == 3:
            print(f"[{mins:02d}:{secs:02d}] 🔄 Retry #{i+1} - Connection restored!")
            print(f"        ✅ Successfully wrote buffered readings to disk")
            break
    
    print("\n" + "="*70)
    print("BENEFITS OF THIS APPROACH:")
    print("="*70)
    print("✓ Quick initial retry (1s) catches transient errors")
    print("✓ Gradual backoff prevents system overload")
    print("✓ Reasonable max interval (15s) ensures timely recovery")
    print("✓ Total time to 6th retry: only 45 seconds")
    print("✓ Much faster recovery than exponential backoff")
    print()

if __name__ == "__main__":
    show_retry_timeline()