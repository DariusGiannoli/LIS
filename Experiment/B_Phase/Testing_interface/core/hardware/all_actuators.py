#!/usr/bin/env python3
"""
Script pour faire vibrer tous les actuateurs connectés via BLE
Utilise la classe python_ble_api pour contrôler les moteurs de vibration
"""

import time
import sys
from core.io.python_ble_api import python_ble_api

class ActuatorController:
    def __init__(self, device_name='QT Py ESP32-S3', max_actuators=16):
        """
        Initialise le contrôleur d'actuateurs
        
        Args:
            device_name: Nom de l'appareil BLE à rechercher
            max_actuators: Nombre maximum d'actuateurs à tester (1-127)
        """
        self.ble_api = python_ble_api()
        self.device_name = device_name
        self.max_actuators = min(max_actuators, 127)  # Limite selon l'API
        self.connected = False
        
    def connect(self):
        """Se connecte au dispositif BLE"""
        print("Recherche des appareils BLE...")
        devices = self.ble_api.get_ble_devices()
        print(f"Appareils trouvés: {devices}")
        
        if self.device_name in devices:
            print(f"Connexion à {self.device_name}...")
            if self.ble_api.connect_ble_device(self.device_name):
                self.connected = True
                print("✅ Connexion réussie!")
                return True
            else:
                print("❌ Échec de la connexion")
                return False
        else:
            print(f"❌ Appareil '{self.device_name}' non trouvé")
            print("Appareils disponibles:", devices)
            return False
    
    def disconnect(self):
        """Se déconnecte du dispositif BLE"""
        if self.connected:
            print("Déconnexion...")
            if self.ble_api.disconnect_ble_device():
                self.connected = False
                print("✅ Déconnecté")
            else:
                print("❌ Erreur lors de la déconnexion")
    
    def vibrate_all_sync(self, duty=10, freq=4, duration=2):
        """
        Fait vibrer tous les actuateurs en même temps
        
        Args:
            duty: Intensité de vibration (0-15)
            freq: Fréquence de vibration (0-7)
            duration: Durée en secondes
        """
        if not self.connected:
            print("❌ Pas connecté au dispositif BLE")
            return
            
        print(f"🔵 Vibration synchronisée (duty={duty}, freq={freq}) pendant {duration}s")
        
        # Créer la liste de commandes pour démarrer tous les actuateurs
        start_commands = []
        for addr in range(0, self.max_actuators):
            start_commands.append({
                "addr": addr,
                "duty": duty,
                "freq": freq,
                "start_or_stop": 1
            })
        
        # Envoyer par paquets de 10 (limite de l'API)
        for i in range(0, len(start_commands), 10):
            batch = start_commands[i:i+10]
            if self.ble_api.send_command_list(batch):
                print(f"✅ Batch {i//10 + 1} envoyé ({len(batch)} actuateurs)")
            else:
                print(f"❌ Erreur envoi batch {i//10 + 1}")
        
        # Attendre
        time.sleep(duration)
        
        # Arrêter tous les actuateurs
        stop_commands = []
        for addr in range(0, self.max_actuators):
            stop_commands.append({
                "addr": addr,
                "duty": 0,
                "freq": 0,
                "start_or_stop": 0
            })
        
        # Envoyer les commandes d'arrêt par paquets
        for i in range(0, len(stop_commands), 10):
            batch = stop_commands[i:i+10]
            if self.ble_api.send_command_list(batch):
                print(f"✅ Arrêt batch {i//10 + 1}")
            else:
                print(f"❌ Erreur arrêt batch {i//10 + 1}")
    
    def vibrate_wave(self, duty=8, freq=3, wave_speed=0.2):
        """
        Crée une vague de vibration qui parcourt tous les actuateurs
        
        Args:
            duty: Intensité de vibration (0-15)
            freq: Fréquence de vibration (0-7)  
            wave_speed: Vitesse de la vague en secondes entre chaque actuateur
        """
        if not self.connected:
            print("❌ Pas connecté au dispositif BLE")
            return
            
        print(f"🌊 Vague de vibration (duty={duty}, freq={freq}, speed={wave_speed}s)")
        
        for addr in range(0, self.max_actuators):
            # Démarrer l'actuateur actuel
            self.ble_api.send_command(addr, duty, freq, 1)
            print(f"🔵 Actuateur {addr} ON")
            
            time.sleep(wave_speed)
            
            # Arrêter l'actuateur actuel
            self.ble_api.send_command(addr, 0, 0, 0)
            print(f"⚫ Actuateur {addr} OFF")
    
    def vibrate_pattern_random(self, duration=10, change_interval=0.5):
        """
        Fait vibrer les actuateurs avec un pattern aléatoire
        
        Args:
            duration: Durée totale en secondes
            change_interval: Intervalle entre les changements en secondes
        """
        if not self.connected:
            print("❌ Pas connecté au dispositif BLE")
            return
            
        import random
        
        print(f"🎲 Pattern aléatoire pendant {duration}s (changement toutes les {change_interval}s)")
        
        start_time = time.time()
        
        while time.time() - start_time < duration:
            # Générer un pattern aléatoire
            commands = []
            for addr in range(0, self.max_actuators):
                if random.random() > 0.5:  # 50% de chance d'être actif
                    commands.append({
                        "addr": addr,
                        "duty": random.randint(5, 15),
                        "freq": random.randint(2, 7),
                        "start_or_stop": 1
                    })
                else:
                    commands.append({
                        "addr": addr,
                        "duty": 0,
                        "freq": 0,
                        "start_or_stop": 0
                    })
            
            # Envoyer par paquets
            for i in range(0, len(commands), 10):
                batch = commands[i:i+10]
                self.ble_api.send_command_list(batch)
            
            print(f"🎲 Pattern changé - {sum(1 for c in commands if c['start_or_stop'] == 1)} actuateurs actifs")
            time.sleep(change_interval)
        
        # Arrêter tous les actuateurs à la fin
        self.stop_all()
    
    def stop_all(self):
        """Arrête tous les actuateurs"""
        if not self.connected:
            print("❌ Pas connecté au dispositif BLE")
            return
            
        print("⏹️  Arrêt de tous les actuateurs")
        
        stop_commands = []
        for addr in range(0, self.max_actuators):
            stop_commands.append({
                "addr": addr,
                "duty": 0,
                "freq": 0,
                "start_or_stop": 0
            })
        
        # Envoyer par paquets de 10
        for i in range(0, len(stop_commands), 10):
            batch = stop_commands[i:i+10]
            if self.ble_api.send_command_list(batch):
                print(f"✅ Arrêt batch {i//10 + 1}")

def main():
    """Fonction principale avec menu interactif"""
    controller = ActuatorController()
    
    # Se connecter
    if not controller.connect():
        print("❌ Impossible de se connecter. Arrêt du programme.")
        return
    
    try:
        while True:
            print("\n" + "="*50)
            print("🎮 CONTRÔLE DES ACTUATEURS")
            print("="*50)
            print("1. Vibration synchronisée (tous en même temps)")
            print("2. Vague de vibration (séquentiel)")
            print("3. Pattern aléatoire") 
            print("4. Arrêter tous les actuateurs")
            print("5. Test individuel d'un actuateur")
            print("6. Quitter")
            print("="*50)
            
            choice = input("Votre choix (1-6): ").strip()
            
            if choice == '1':
                duty = int(input("Intensité (0-15) [défaut: 10]: ") or "10")
                freq = int(input("Fréquence (0-7) [défaut: 4]: ") or "4") 
                duration = float(input("Durée en secondes [défaut: 2]: ") or "2")
                controller.vibrate_all_sync(duty, freq, duration)
                
            elif choice == '2':
                duty = int(input("Intensité (0-15) [défaut: 8]: ") or "8")
                freq = int(input("Fréquence (0-7) [défaut: 3]: ") or "3")
                speed = float(input("Vitesse vague en secondes [défaut: 0.2]: ") or "0.2")
                controller.vibrate_wave(duty, freq, speed)
                
            elif choice == '3':
                duration = float(input("Durée totale en secondes [défaut: 10]: ") or "10")
                interval = float(input("Intervalle changement [défaut: 0.5]: ") or "0.5")
                controller.vibrate_pattern_random(duration, interval)
                
            elif choice == '4':
                controller.stop_all()
                
            elif choice == '5':
                addr = int(input("Adresse actuateur (0-127): "))
                duty = int(input("Intensité (0-15): "))
                freq = int(input("Fréquence (0-7): "))
                duration = float(input("Durée en secondes: "))
                
                print(f"Test actuateur {addr}...")
                controller.ble_api.send_command(addr, duty, freq, 1)
                time.sleep(duration)
                controller.ble_api.send_command(addr, 0, 0, 0)
                print("Test terminé")
                
            elif choice == '6':
                break
                
            else:
                print("❌ Choix invalide")
                
    except KeyboardInterrupt:
        print("\n⏹️  Interruption détectée")
        
    finally:
        # S'assurer que tous les actuateurs sont arrêtés
        controller.stop_all()
        controller.disconnect()
        print("👋 Programme terminé")

if __name__ == '__main__':
    main()