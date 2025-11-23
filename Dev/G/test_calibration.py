import time
from serial_api import SERIAL_API

def run_calibration_test():
    # Initialisation de l'API
    api = SERIAL_API()
    
    # Récupération des ports
    devs = api.get_serial_devices()
    print(f"Ports détectés : {devs}")

    if not devs:
        print("Aucun appareil série trouvé. Vérifiez la connexion USB.")
        return

    # SÉLECTION DU PORT
    # Dans votre exemple précédent, vous utilisiez l'index 2 (devs[2]).
    # Je mets une sécurité pour prendre le premier si la liste est plus courte.
    port_idx = 2 if len(devs) > 2 else 0
    target_device = devs[port_idx]

    print(f"Tentative de connexion à : {target_device} ...")

    if api.connect_serial_device(target_device):
        print("Connecté avec succès. Démarrage de la séquence de test...")
        print("="*50)
        
        # Paramètres fixes
        ADDR = 0       # Adresse du moteur
        FREQ = 3       # Fréquence standard
        DURATION = 1.0 # Durée de vibration en secondes
        PAUSE = 0.3    # Pause technique pour laisser le PIC reset (éviter bug double lancement)

        # Boucle de 0 à 30 avec un pas de 5
        # range(start, stop, step) -> s'arrête AVANT stop, donc 31 pour inclure 30
        for duty in range(0, 31, 2):
            print(f"\n>>> TEST NIVEAU DUTY : {duty}/31")

            # -------------------------------------------------
            # 1. TEST SINUS (Wave = 1)
            # -------------------------------------------------
            print(f"    [SINUS] ON  (Duty {duty})")
            api.send_command(addr=ADDR, duty=duty, freq=FREQ, start_or_stop=1, wave=1)
            
            time.sleep(DURATION)
            
            # STOP SINUS
            api.send_command(addr=ADDR, duty=0, freq=FREQ, start_or_stop=0, wave=1)
            print("    [SINUS] OFF")
            
            # PAUSE CRITIQUE (Pour éviter que le Square ne se lance trop vite sur le Sine)
            time.sleep(PAUSE)

            # -------------------------------------------------
            # 2. TEST SQUARE (Wave = 0)
            # -------------------------------------------------
            # print(f"    [SQUARE] ON (Duty {duty})")
            # api.send_command(addr=ADDR, duty=duty, freq=FREQ, start_or_stop=1, wave=0)
            
            # time.sleep(DURATION)
            
            # # STOP SQUARE
            # api.send_command(addr=ADDR, duty=0, freq=FREQ, start_or_stop=0, wave=0)
            # print("    [SQUARE] OFF")
            
            # # Pause avant le prochain niveau d'intensité
            # time.sleep(PAUSE)

        print("="*50)
        print("Test terminé.")
        api.disconnect_serial_device()
    else:
        print("Échec de la connexion série.")

if __name__ == "__main__":
    run_calibration_test()