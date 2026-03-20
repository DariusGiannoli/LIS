# test_vibrate.py — Vibrer actuateurs 0-15 à duty 15/31
from ble_api import BLE_API, WAVE_SINE
import time

api = BLE_API()

if not api.connect_ble_device():
    print("Connexion échouée")
    exit(1)

try:
    print("Démarrage actuateurs 0-15 (duty=15, sine)...")
    
    start_cmds = [
        {'addr': i, 'duty': 15, 'freq': 3, 'start_or_stop': 1, 'wave': WAVE_SINE}
        for i in range(16)
    ]
    api.send_command_list(start_cmds)
    
    time.sleep(2.0)  # Vibrer 2 secondes
    
    print("Arrêt...")
    stop_cmds = [
        {'addr': i, 'duty': 0, 'freq': 3, 'start_or_stop': 0, 'wave': WAVE_SINE}
        for i in range(16)
    ]
    api.send_command_list(stop_cmds)
    
    time.sleep(0.3)

finally:
    api.disconnect_ble_device()
    print("Terminé")