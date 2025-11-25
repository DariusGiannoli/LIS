import cv2
import time
import math
import numpy as np
import mediapipe as mp
import matplotlib.pyplot as plt

# --------- Paramètres globaux ---------
COUNTDOWN_SECONDS = 3
SAMPLE_PERIOD = 0.05   # en secondes (20 Hz)
RECORD_DURATION = 3.0  # durée d'enregistrement auto par session (s)
USE_WRISTS = True      # True: poignets, False: épaules

mp_drawing = mp.solutions.drawing_utils
mp_pose = mp.solutions.pose


def main():
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("Impossible d'ouvrir la caméra.")
        return

    pose = mp_pose.Pose(
        min_detection_confidence=0.5,
        min_tracking_confidence=0.5
    )

    # État général
    recording = False
    countdown_started = False
    countdown_start_time = None
    record_start_time = None
    last_sample_time = None

    # Données des sessions
    sessions_t = []  # liste de listes : chaque élément = [t0, t1, ...]
    sessions_d = []  # liste de listes : chaque élément = [d0, d1, ...]

    # Données de la session en cours
    current_t = []
    current_d = []

    print("Commandes :")
    print("  's' : lancer une nouvelle session (compte à rebours)")
    print("  'f' : terminer toutes les sessions et afficher les courbes")
    print("  'q' : quitter immédiatement (sans plots si aucune session complète)")

    while True:
        ret, frame = cap.read()
        if not ret:
            print("Frame non lue, fin.")
            break

        frame = cv2.flip(frame, 1)
        h, w, _ = frame.shape

        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = pose.process(rgb)

        # Texte de statut
        if not countdown_started and not recording:
            status_text = "Ready - 's' = start session, 'f' = finish"
        elif countdown_started and not recording:
            status_text = "Countdown..."
        else:
            status_text = "Recording (auto-stop)"

        cv2.putText(frame, status_text, (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

        # Gestion du compte à rebours
        if countdown_started and not recording:
            elapsed = time.time() - countdown_start_time
            remaining = COUNTDOWN_SECONDS - elapsed
            if remaining > 0:
                countdown_str = f"{int(remaining) + 1}"
                cv2.putText(frame, countdown_str,
                            (w // 2 - 20, h // 2),
                            cv2.FONT_HERSHEY_SIMPLEX, 2, (0, 0, 255), 4)
            else:
                # Début d'enregistrement pour une nouvelle session
                recording = True
                record_start_time = time.time()
                last_sample_time = None
                current_t = []
                current_d = []
                print(f">>> Début session {len(sessions_t) + 1} (auto-stop après {RECORD_DURATION}s).")

        # Si landmarks dispo, on peut calculer la distance
        if results.pose_landmarks:
            landmarks = results.pose_landmarks.landmark

            if USE_WRISTS:
                left_point = landmarks[mp_pose.PoseLandmark.LEFT_WRIST]
                right_point = landmarks[mp_pose.PoseLandmark.RIGHT_WRIST]
            else:
                left_point = landmarks[mp_pose.PoseLandmark.LEFT_SHOULDER]
                right_point = landmarks[mp_pose.PoseLandmark.RIGHT_SHOULDER]

            xL, yL = left_point.x, left_point.y
            xR, yR = right_point.x, right_point.y

            dist = math.sqrt((xR - xL) ** 2 + (yR - yL) ** 2)

            # Visualisation
            p1 = (int(xL * w), int(yL * h))
            p2 = (int(xR * w), int(yR * h))
            cv2.line(frame, p1, p2, (255, 0, 0), 3)
            cv2.circle(frame, p1, 5, (255, 0, 0), -1)
            cv2.circle(frame, p2, 5, (255, 0, 0), -1)

            if recording:
                now = time.time()

                # Auto-stop si durée dépassée
                if (now - record_start_time) >= RECORD_DURATION:
                    recording = False
                    countdown_started = False
                    # Sauvegarde de la session
                    sessions_t.append(current_t)
                    sessions_d.append(current_d)
                    print(f">>> Session {len(sessions_t)} enregistrée ({len(current_t)} points).")
                else:
                    # Échantillonnage à fréquence fixe
                    if last_sample_time is None or (now - last_sample_time) >= SAMPLE_PERIOD:
                        last_sample_time = now
                        t_rel = now - record_start_time
                        current_t.append(t_rel)
                        current_d.append(dist)

        # Dessin des landmarks (optionnel)
        if results.pose_landmarks:
            mp_drawing.draw_landmarks(
                frame, results.pose_landmarks, mp_pose.POSE_CONNECTIONS
            )

        cv2.imshow("Arm linearity - multi-session", frame)

        key = cv2.waitKey(1) & 0xFF
        if key == ord('s') and not countdown_started and not recording:
            countdown_started = True
            countdown_start_time = time.time()
            print(">>> Compte à rebours lancé pour nouvelle session.")
        elif key == ord('f'):
            print(">>> Fin des acquisitions, on passe aux plots.")
            break
        elif key == ord('q'):
            print(">>> Quitter (q).")
            break

    cap.release()
    cv2.destroyAllWindows()
    pose.close()

    # ----- Analyse / plots -----
    if len(sessions_t) == 0:
        print("Aucune session complète enregistrée.")
        return

    # Grille de temps commune pour la moyenne
    t_common = np.linspace(0, RECORD_DURATION, 200)
    interp_sessions = []

    for idx, (t_list, d_list) in enumerate(zip(sessions_t, sessions_d), start=1):
        t_arr = np.array(t_list)
        d_arr = np.array(d_list)
        if len(t_arr) < 2:
            print(f"Session {idx} ignorée (trop peu de points).")
            continue

        # Assurer l'ordre croissant
        order = np.argsort(t_arr)
        t_arr = t_arr[order]
        d_arr = d_arr[order]

        d_interp = np.interp(t_common, t_arr, d_arr)
        interp_sessions.append(d_interp)

    if len(interp_sessions) == 0:
        print("Pas assez de données exploitables pour faire une moyenne.")
        return

    interp_sessions = np.stack(interp_sessions, axis=0)
    mean_d = np.mean(interp_sessions, axis=0)

    # Plot : toutes les courbes + moyenne
    plt.figure()
    for i, d_interp in enumerate(interp_sessions, start=1):
        plt.plot(t_common, d_interp, alpha=0.3, label=f"Session {i}")

    plt.plot(t_common, mean_d, linewidth=2.5, label="Moyenne", color='k')
    plt.xlabel("Temps (s)")
    plt.ylabel("Distance normalisée entre les bras")
    plt.title("Linéarité de l'écartement des bras - multi-sessions")
    plt.legend()
    plt.grid(True)
    plt.show()


if __name__ == "__main__":
    main()