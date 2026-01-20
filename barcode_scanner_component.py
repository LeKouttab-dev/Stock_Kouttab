import streamlit as st
from streamlit_webrtc import webrtc_streamer
import av
import cv2
import threading

# Conteneur pour le résultat du scan, protégé par un verrou pour la sécurité entre les threads
lock = threading.Lock()
barcode_container = {"barcode": None}

# Initialiser le détecteur de code-barres d'OpenCV
barcode_detector = cv2.barcode.BarcodeDetector()

def video_frame_callback(frame: av.VideoFrame):
    """
    Cette fonction est appelée pour chaque image de la caméra.
    """
    img = frame.to_ndarray(format="bgr24")

    # Dessiner un rectangle de guidage vert au centre de l'image
    h, w, _ = img.shape
    rect_width = int(w * 0.8)
    rect_height = int(h * 0.3)
    x1 = (w - rect_width) // 2
    y1 = (h - rect_height) // 2
    x2 = x1 + rect_width
    y2 = y1 + rect_height
    cv2.rectangle(img, (x1, y1), (x2, y2), (0, 255, 0), 2)

    # Détecter et décoder les codes-barres
    ok, decoded_info, _, points = barcode_detector.detectAndDecode(img)

    if ok and decoded_info:
        barcode_data = decoded_info[0]
        
        # Dessiner un polygone rouge autour du code-barres détecté
        if points is not None:
            pts = points[0].astype(int)
            cv2.polylines(img, [pts], isClosed=True, color=(0, 0, 255), thickness=2)
        
        # Stocker le résultat de manière sécurisée
        with lock:
            if barcode_container["barcode"] is None:
                barcode_container["barcode"] = barcode_data
            
    return av.VideoFrame.from_ndarray(img, format="bgr24")

def run_scanner():
    """
    Affiche le composant scanner et retourne le code-barres une fois trouvé.
    """
    st.info("Visez le code-barres avec le rectangle vert. Le scan s'arrêtera automatiquement.")
    
    webrtc_ctx = webrtc_streamer(
        key="barcode-scanner",
        video_frame_callback=video_frame_callback,
        media_stream_constraints={"video": {"facingMode": "environment"}},
        async_processing=True,
    )

    # Boucle pour vérifier si un code-barres a été trouvé sans bloquer l'interface
    if webrtc_ctx.state.playing:
        while True:
            with lock:
                if barcode_container["barcode"]:
                    # Un code-barres a été trouvé, on le stocke dans la session et on arrête tout
                    st.session_state.barcode_scanned = barcode_container["barcode"]
                    barcode_container["barcode"] = None # On réinitialise pour les prochains scans
                    st.rerun() # On recharge la page pour traiter le code-barres
            
            # Petite pause pour ne pas surcharger le CPU
            threading.Event().wait(0.1)
    
    return None
