# Setup (one time):
python calibration_tool.py         # Creates calibrations/gabriel.json
python linearization_tool.py       # Updates calibrations/gabriel.json

# Daily use:
# Edit tracker.py line 10: CALIBRATION_PROFILE = "gabriel"
python tracker.py                   # Run this to control drones