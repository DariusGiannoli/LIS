import cv2
import time
import math
import numpy as np
import mediapipe as mp
import matplotlib.pyplot as plt


# --------- Paramètres ---------
RECORD_DURATION = 30.0   # secondes
SAMPLE_PERIOD = 0.03     # ~33 Hz
COUNTDOWN_SECONDS = 3
USE_WRISTS = True        # sinon épaules

N_POINTS_CYCLE = 200     # nb de points pour la phase normalisée (0..1)

mp_drawing = mp.solutions.drawing_utils
mp_pose = mp.solutions.pose


def moving_average(x, window_size=7):
    if window_size < 2:
        return x
    window = np.ones(window_size) / window_size
    # mode='same' pour garder la même longueur
    return np.convolve(x, window, mode='same')


def detect_cycles(t, d, min_distance_points=10):
    """
    Détecte les cycles centre -> écarté -> centre.
    On cherche des 'vallées' (minima locaux) et on
    prend les segments vallée_i -> vallée_{i+1}
    dès qu'il y a au moins un pic entre les deux.
    """
    d = np.array(d)
    t = np.array(t)
    if len(d) < 3:
        return []

    # dérivée approx
    dt = np.diff(t)
    dd = np.diff(d)
    deriv = dd / dt

    # indices de minima / maxima locaux
    minima = []
    maxima = []
    for i in range(1, len(deriv)):
        prev = deriv[i - 1]
        curr = deriv[i]
        # changement de signe + -> - : maximum
        if prev > 0 and curr <= 0:
            maxima.append(i)
        # changement de signe - -> + : minimum
        if prev < 0 and curr >= 0:
            minima.append(i)

    minima = np.array(minima, dtype=int)
    maxima = np.array(maxima, dtype=int)

    cycles = []
    if len(minima) < 2:
        return cycles

    # Segment vallée_i -> vallée_{i+1}
    for i in range(len(minima) - 1):
        start = minima[i]
        end = minima[i + 1]
        if end - start < min_distance_points:
            continue
        # y a-t-il au moins un maximum entre ces deux minima ?
        has_peak = np.any((maxima > start) & (maxima < end))
        if not has_peak:
            continue
        cycles.append((start, end))

    return cycles


def main():
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("Impossible d'ouvrir la caméra.")
        return

    pose = mp_pose.Pose(
        min_detection_confidence=0.5,
        min_tracking_confidence=0.5
    )

    print("Appuie sur 's' pour lancer le compte à rebours, 'q' pour quitter.")
    recording = False
    countdown_started = False
    countdown_start_time = None

    t_all = []
    d_all = []
    last_sample_time = None
    record_start_time = None

    while True:
        ret, frame = cap.read()
        if not ret:
            print("Frame non lue, fin.")
            break

        frame = cv2.flip(frame, 1)
        h, w, _ = frame.shape

        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = pose.process(rgb)

        # Statut
        if not countdown_started and not recording:
            status = "Ready - 's' pour commencer (20s), 'q' pour quitter"
        elif countdown_started and not recording:
            status = "Countdown..."
        else:
            status = "Recording 20 s..."

        cv2.putText(frame, status, (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)

        # Countdown
        if countdown_started and not recording:
            elapsed = time.time() - countdown_start_time
            remaining = COUNTDOWN_SECONDS - elapsed
            if remaining > 0:
                countdown_str = f"{int(remaining) + 1}"
                cv2.putText(frame, countdown_str,
                            (w // 2 - 20, h // 2),
                            cv2.FONT_HERSHEY_SIMPLEX, 2, (0, 0, 255), 4)
            else:
                recording = True
                record_start_time = time.time()
                last_sample_time = None
                print(">>> Début enregistrement 20 s. "
                      "Fais plusieurs aller-retours bras centre <-> écartés.")

        # Pose / distance
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

            p1 = (int(xL * w), int(yL * h))
            p2 = (int(xR * w), int(yR * h))
            cv2.line(frame, p1, p2, (255, 0, 0), 3)
            cv2.circle(frame, p1, 5, (255, 0, 0), -1)
            cv2.circle(frame, p2, 5, (255, 0, 0), -1)

            if recording:
                now = time.time()
                if last_sample_time is None or (now - last_sample_time) >= SAMPLE_PERIOD:
                    last_sample_time = now
                    t_rel = now - record_start_time
                    t_all.append(t_rel)
                    d_all.append(dist)

                # stop après RECORD_DURATION
                if (now - record_start_time) >= RECORD_DURATION:
                    print(">>> Fin enregistrement 20 s.")
                    recording = False
                    countdown_started = False
                    break

        # Dessin landmarks (pour debug)
        if results.pose_landmarks:
            mp_drawing.draw_landmarks(
                frame, results.pose_landmarks, mp_pose.POSE_CONNECTIONS
            )

        cv2.imshow("Arm back-and-forth capture", frame)

        key = cv2.waitKey(1) & 0xFF
        if key == ord('s') and not countdown_started and not recording:
            countdown_started = True
            countdown_start_time = time.time()
            print(">>> Compte à rebours lancé.")
        elif key == ord('q'):
            print(">>> Quitter.")
            cap.release()
            cv2.destroyAllWindows()
            pose.close()
            return

    cap.release()
    cv2.destroyAllWindows()
    pose.close()

    # ---------- Analyse ----------
    if len(t_all) < 10:
        print("Pas assez de données.")
        return

    t_all = np.array(t_all)
    d_all = np.array(d_all)

    # Lissage
    d_smooth = moving_average(d_all, window_size=7)

    # Détection des cycles centre->écarté->centre
    cycles = detect_cycles(t_all, d_smooth, min_distance_points=10)
    print(f"Cycles détectés : {len(cycles)}")

    if len(cycles) == 0:
        print("Aucun cycle complet trouvé. Essaie de faire des aller-retours plus réguliers.")
        # on affiche quand même distance vs temps
        plt.figure()
        plt.plot(t_all, d_smooth, label="distance lissée")
        plt.xlabel("Temps (s)")
        plt.ylabel("Distance normalisée")
        plt.title("Distance bras vs temps (aucun cycle fiable trouvé)")
        plt.grid(True)
        plt.show()
        return

    # Grille de phase 0..1
    phase_common = np.linspace(0.0, 1.0, N_POINTS_CYCLE)
    interp_cycles = []

    for (i0, i1) in cycles:
        t_seg = t_all[i0:i1 + 1]
        d_seg = d_smooth[i0:i1 + 1]

        if len(t_seg) < 3:
            continue

        # phase 0..1 sur ce cycle
        t_rel = t_seg - t_seg[0]
        phase = t_rel / t_rel[-1]

        # Assurer ordre croissant
        order = np.argsort(phase)
        phase = phase[order]
        d_seg = d_seg[order]

        d_interp = np.interp(phase_common, phase, d_seg)
        interp_cycles.append(d_interp)

    if len(interp_cycles) == 0:
        print("Pas assez de points pour interpoler les cycles.")
        return

    interp_cycles = np.stack(interp_cycles, axis=0)
    mean_cycle = np.mean(interp_cycles, axis=0)

    # ---------- Plots ----------
    # 1) distance vs temps (global)
    plt.figure()
    plt.plot(t_all, d_smooth, label="distance lissée")
    for (i0, i1) in cycles:
        plt.axvspan(t_all[i0], t_all[i1], color='gray', alpha=0.1)
    plt.xlabel("Temps (s)")
    plt.ylabel("Distance normalisée entre les bras")
    plt.title("Distance bras vs temps (zones = cycles détectés)")
    plt.grid(True)
    plt.legend()

    # 2) cycles superposés + moyenne
    plt.figure()
    for i, d_interp in enumerate(interp_cycles, start=1):
        plt.plot(phase_common, d_interp, alpha=0.3, label=f"Cycle {i}")
    plt.plot(phase_common, mean_cycle, linewidth=2.5, color='k', label="Cycle moyen")
    plt.xlabel("Phase du mouvement")
    plt.ylabel("Distance normalisée")
    plt.title("Cycle bras centre ↔ écartés ↔ centre (moyenne sur cycles)")
    plt.grid(True)
    plt.legend()
    plt.show()


if __name__ == "__main__":
    main()