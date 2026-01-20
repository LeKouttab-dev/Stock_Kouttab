import { Streamlit } from "streamlit-component-lib";

const video = document.getElementById("video");
const statusEl = document.getElementById("status");
let barcodeDetector;

async function startCamera() {
    try {
        if (!("BarcodeDetector" in window)) {
            statusEl.textContent = "L'API BarcodeDetector n'est pas supportée par ce navigateur.";
            return;
        }
        
        barcodeDetector = new window.BarcodeDetector({ formats: ['ean_13', 'ean_8', 'upc_a', 'upc_e'] });
        
        const stream = await navigator.mediaDevices.getUserMedia({
            video: { facingMode: "environment" }
        });
        
        video.srcObject = stream;
        video.onloadedmetadata = () => {
            statusEl.textContent = "Visez un code-barres...";
            Streamlit.setFrameHeight();
            scan(); // Démarrer le scan une fois la vidéo chargée
        };

    } catch (err) {
        statusEl.textContent = `Erreur d'accès à la caméra: ${err.name}`;
        console.error(err);
    }
}

async function scan() {
    try {
        const barcodes = await barcodeDetector.detect(video);
        if (barcodes.length > 0) {
            const barcode = barcodes[0];
            statusEl.textContent = `Code-barres détecté : ${barcode.rawValue}`;
            
            // Envoyer la valeur à Streamlit
            Streamlit.setComponentValue(barcode.rawValue);

            // Arrêter la caméra après un scan réussi
            video.srcObject.getTracks().forEach(track => track.stop());
            return; // Arrêter la boucle de scan
        }
    } catch (e) {
        console.error(e);
    }
    
    // Continuer à scanner
    requestAnimationFrame(scan);
}

// Démarrer le processus lorsque le composant est chargé
startCamera();
