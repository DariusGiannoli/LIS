#!/usr/bin/env python3
"""
Complete verification script - checks all fixes are applied correctly
"""

import json
import sys
from pathlib import Path

def check_file(filepath, description):
    """Check if file exists"""
    if Path(filepath).exists():
        print(f"✅ {description}: Found")
        return True
    else:
        print(f"❌ {description}: NOT FOUND")
        return False

def check_calibration(filepath):
    """Check calibration file is correct"""
    if not Path(filepath).exists():
        print(f"❌ Calibration file not found: {filepath}")
        return False
    
    with open(filepath, 'r') as f:
        cal = json.load(f)
    
    print(f"\n📊 Calibration Check: {filepath}")
    print(f"  Horizontal: {cal['min_horizontal']:.1f} - {cal['max_horizontal']:.1f}")
    print(f"  Vertical: {cal['min_vertical']:.1f} - {cal['max_vertical']:.1f}")
    print(f"  Neutral: {cal['neutral_vertical']:.1f}")
    
    # Check if vertical is correct
    if cal['min_vertical'] < cal['max_vertical']:
        print("  ✅ Vertical values CORRECT (min < max)")
        return True
    else:
        print("  ❌ Vertical values INVERTED (min > max)")
        print("  → Use the fixed gabriel.json file!")
        return False

def check_simu_file(filepath):
    """Check if simu.py has the fix"""
    if not Path(filepath).exists():
        print(f"❌ Simulation file not found: {filepath}")
        return False
    
    with open(filepath, 'r') as f:
        content = f.read()
    
    print(f"\n📊 Simulation Check: {filepath}")
    
    # Check for the fix (height_value instead of height)
    if 'self.height_value' in content:
        print("  ✅ Variable naming fix APPLIED (uses height_value)")
        return True
    else:
        print("  ❌ Variable naming fix NOT APPLIED")
        print("  → Use the fixed simu.py file!")
        return False

def check_calibration_tool(filepath):
    """Check if calibration tool has auto-swap"""
    if not Path(filepath).exists():
        print(f"❌ Calibration tool not found: {filepath}")
        return False
    
    with open(filepath, 'r') as f:
        content = f.read()
    
    print(f"\n📊 Calibration Tool Check: {filepath}")
    
    # Check for auto-swap logic
    if 'AUTO-FIX' in content or 'Auto-fixing' in content:
        print("  ✅ Auto-swap fix APPLIED")
        return True
    else:
        print("  ❌ Auto-swap fix NOT APPLIED")
        print("  → Use the fixed calibration_tool.py file!")
        return False

def main():
    print("=" * 60)
    print("  HAND TRACKING SYSTEM - VERIFICATION SCRIPT")
    print("=" * 60)
    
    all_good = True
    
    # Check files exist
    print("\n📁 File Existence Check:")
    files_ok = True
    files_ok &= check_file("src/hand_detector.py", "Hand Detector")
    files_ok &= check_file("src/websocket_server.py", "WebSocket Server")
    files_ok &= check_file("tracker.py", "Tracker")
    files_ok &= check_file("simu.py", "Simulation")
    
    if not files_ok:
        print("\n⚠️  Some core files are missing!")
        all_good = False
    
    # Check calibration
    print()
    cal_ok = check_calibration("calibrations/gabriel.json")
    if not cal_ok:
        all_good = False
    
    # Check simulation fix
    print()
    simu_ok = check_simu_file("simu.py")
    if not simu_ok:
        all_good = False
    
    # Check calibration tool fix
    print()
    tool_ok = check_calibration_tool("src/tools/calibration_tool.py")
    if not tool_ok:
        all_good = False
    
    # Final verdict
    print("\n" + "=" * 60)
    if all_good:
        print("✅ ALL CHECKS PASSED!")
        print("\nYour system is ready to use:")
        print("  1. Terminal 1: python tracker.py")
        print("  2. Terminal 2: python simu.py")
        print("  3. Move your hands and watch the magic! ✨")
    else:
        print("❌ SOME CHECKS FAILED")
        print("\nPlease apply the fixes:")
        print("  1. Copy fixed files from outputs folder")
        print("  2. See COMPLETE_FIX.md for detailed instructions")
    print("=" * 60)
    
    return 0 if all_good else 1

if __name__ == "__main__":
    sys.exit(main())