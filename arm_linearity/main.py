import cv2
import time
import math
import numpy as np
import mediapipe as mp
import matplotlib.pyplot as plt

# --------- Paramètres ---------
COUNTDOWN_SECONDS = 5
SAMPLE_PERIOD = 0.05  # en secondes (20 Hz)
RECORD_DURATION = 3.0  # <<< durée d'enregistrement auto en secondes

# Choix des points : WRIST ou SHOULDER
USE_WRISTS = True  # si False, on utilisera les épaules

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

    recording = False
    countdown_started = False
    countdown_start_time = None
    record_start_time = None
    last_sample_time = None
    auto_stopped = False  # <<< flag pour savoir si on s'est arrêté tout seul

    # On stocke (t, distance)
    samples_t = []
    samples_d = []

    print("Appuie sur 's' pour lancer le compte à rebours, 'q' pour quitter (optionnel).")

    while True:
        ret, frame = cap.read()
        if not ret:
            print("Frame non lue, fin.")
            break

        # Flip pour effet miroir (optionnel)
        frame = cv2.flip(frame, 1)
        h, w, _ = frame.shape

        # Passage en RGB pour MediaPipe
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = pose.process(rgb)

        # Gestion du texte d'état
        status_text = "Ready - press 's' to start"
        if countdown_started and not recording:
            status_text = "Countdown..."
        elif recording:
            status_text = "Recording... (auto-stop)"

        cv2.putText(frame, status_text, (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 0), 2)

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
                # Countdown fini -> start recording
                recording = True
                record_start_time = time.time()
                last_sample_time = None
                print(">>> Début de l'enregistrement (stop auto après "
                      f"{RECORD_DURATION} s).")

        # Si on a des landmarks, on peut calculer la distance
        if results.pose_landmarks:
            landmarks = results.pose_landmarks.landmark

            if USE_WRISTS:
                left_point = landmarks[mp_pose.PoseLandmark.LEFT_WRIST]
                right_point = landmarks[mp_pose.PoseLandmark.RIGHT_WRIST]
            else:
                left_point = landmarks[mp_pose.PoseLandmark.LEFT_SHOULDER]
                right_point = landmarks[mp_pose.PoseLandmark.RIGHT_SHOULDER]

            # Coordonnées normalisées [0,1]
            xL, yL = left_point.x, left_point.y
            xR, yR = right_point.x, right_point.y

            # Distance euclidienne dans le plan de l'image (normalisée)
            dist = math.sqrt((xR - xL) ** 2 + (yR - yL) ** 2)

            # On dessine un trait entre les 2 points pour debug
            p1 = (int(xL * w), int(yL * h))
            p2 = (int(xR * w), int(yR * h))
            cv2.line(frame, p1, p2, (255, 0, 0), 3)
            cv2.circle(frame, p1, 5, (255, 0, 0), -1)
            cv2.circle(frame, p2, 5, (255, 0, 0), -1)

            # Enregistrement à intervalle régulier
            if recording:
                now = time.time()

                # 1) Auto-stop si durée dépassée
                if (now - record_start_time) >= RECORD_DURATION:
                    print(">>> Fin de l'enregistrement (auto-stop atteint).")
                    auto_stopped = True
                    recording = False
                    # On sort de la boucle principale
                    cv2.imshow("Arm linearity capture", frame)
                    break

                # 2) Prise d'échantillons
                if last_sample_time is None or (now - last_sample_time) >= SAMPLE_PERIOD:
                    last_sample_time = now
                    t_rel = now - record_start_time
                    samples_t.append(t_rel)
                    samples_d.append(dist)
                    # print(f"t={t_rel:.2f}, dist={dist:.4f}")

        # Dessin des landmarks (optionnel, purement visuel)
        if results.pose_landmarks:
            mp_drawing.draw_landmarks(
                frame,
                results.pose_landmarks,
                mp_pose.POSE_CONNECTIONS
            )

        cv2.imshow("Arm linearity capture", frame)

        key = cv2.waitKey(1) & 0xFF
        # 's' -> lancer le compte à rebours (si pas déjà lancé)
        if key == ord('s') and not countdown_started and not recording:
            countdown_started = True
            countdown_start_time = time.time()
            print(">>> Compte à rebours lancé.")
        # 'q' -> sortie manuelle (optionnelle)
        elif key == ord('q'):
            print(">>> Fin du script (q).")
            break

    # Cleanup
    cap.release()
    cv2.destroyAllWindows()
    pose.close()

    # ----- Analyse des données -----
    if len(samples_t) < 3:
        print("Pas assez d'échantillons pour analyser quelque chose.")
        return

    t = np.array(samples_t)
    d = np.array(samples_d)

    # Régression linéaire d(t) = a*t + b
    coeffs = np.polyfit(t, d, deg=1)
    a, b = coeffs
    d_pred = a * t + b

    # R²
    ss_res = np.sum((d - d_pred) ** 2)
    ss_tot = np.sum((d - np.mean(d)) ** 2)
    r2 = 1 - ss_res / ss_tot

    print(f"Pente (a) = {a:.4f} (distance par seconde)")
    print(f"Ordonnée à l'origine (b) = {b:.4f}")
    print(f"R² (linéarité) = {r2:.4f}")
    if auto_stopped:
        print(f"(Enregistrement arrêté automatiquement après {RECORD_DURATION} s)")

    # Plot
    plt.figure()
    plt.scatter(t, d, label="Mesures", s=10)
    plt.plot(t, d_pred, label=f"Fit linéaire (R²={r2:.3f})")
    plt.xlabel("Temps (s)")
    plt.ylabel("Distance normalisée entre les bras")
    plt.title("Linéarité de l'écartement des bras")
    plt.legend()
    plt.grid(True)
    plt.show()


if __name__ == "__main__":
    main()