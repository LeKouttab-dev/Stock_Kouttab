import streamlit as st
import streamlit.components.v1 as components
import time


def barcode_scanner_component():
    """Composant de scanner de codes barres avec retour direct via query params"""

    # Utiliser query params pour la communication
    scanner_html = """
    <!DOCTYPE html>
    <html lang="fr">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Scanner de Codes Barres</title>
        <script src="https://unpkg.com/@zxing/library@latest"></script>
        <style>
            body {
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                margin: 0;
                padding: 20px;
                background: #f8f9fa;
            }

            .scanner-container {
                max-width: 600px;
                margin: 0 auto;
                background: white;
                border-radius: 12px;
                box-shadow: 0 4px 20px rgba(0,0,0,0.1);
                overflow: hidden;
            }

            .scanner-header {
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                padding: 20px;
                text-align: center;
            }

            .video-container {
                position: relative;
                width: 100%;
                height: 400px;
                background: #000;
                display: flex;
                align-items: center;
                justify-content: center;
            }

            #video {
                width: 100%;
                height: 100%;
                object-fit: cover;
            }

            .scanner-overlay {
                position: absolute;
                top: 50%;
                left: 50%;
                transform: translate(-50%, -50%);
                width: 280px;
                height: 120px;
                border: 3px solid #00ff88;
                border-radius: 8px;
                box-shadow: 0 0 0 1000px rgba(0, 0, 0, 0.3);
                pointer-events: none;
            }

            .scanner-corners {
                position: absolute;
                width: 100%;
                height: 100%;
            }

            .corner {
                position: absolute;
                width: 20px;
                height: 20px;
                border: 3px solid #00ff88;
            }

            .corner-tl {
                top: -3px;
                left: -3px;
                border-right: none;
                border-bottom: none;
            }

            .corner-tr {
                top: -3px;
                right: -3px;
                border-left: none;
                border-bottom: none;
            }

            .corner-bl {
                bottom: -3px;
                left: -3px;
                border-right: none;
                border-top: none;
            }

            .corner-br {
                bottom: -3px;
                right: -3px;
                border-left: none;
                border-top: none;
            }

            .controls {
                padding: 20px;
                background: #f8f9fa;
                display: flex;
                gap: 12px;
                justify-content: center;
            }

            .btn {
                padding: 12px 24px;
                border: none;
                border-radius: 8px;
                font-size: 1rem;
                font-weight: 500;
                cursor: pointer;
                transition: all 0.2s;
                min-width: 120px;
            }

            .btn-primary {
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
            }

            .btn-primary:hover:not(:disabled) {
                transform: translateY(-2px);
                box-shadow: 0 4px 12px rgba(102, 126, 234, 0.4);
            }

            .btn-primary:disabled {
                background: #ccc;
                cursor: not-allowed;
                transform: none;
            }

            .btn-secondary {
                background: #6c757d;
                color: white;
            }

            .result {
                padding: 20px;
                text-align: center;
            }

            .result-success {
                background: #d4edda;
                color: #155724;
                border: 1px solid #c3e6cb;
                border-radius: 8px;
                padding: 16px;
                font-weight: 500;
            }

            .error-message {
                background: #f8d7da;
                color: #721c24;
                border: 1px solid #f5c6cb;
                border-radius: 8px;
                padding: 16px;
                margin: 10px 0;
            }
        </style>
    </head>
    <body>
        <div class="scanner-container">
            <div class="scanner-header">
                <h2>📷 Scanner Professionnel</h2>
                <p>Précision de type Yuka</p>
            </div>

            <div class="video-container">
                <video id="video" autoplay muted playsinline></video>
                <div class="scanner-overlay">
                    <div class="scanner-corners">
                        <div class="corner corner-tl"></div>
                        <div class="corner corner-tr"></div>
                        <div class="corner corner-bl"></div>
                        <div class="corner corner-br"></div>
                    </div>
                </div>
            </div>

            <div class="controls">
                <button id="startBtn" class="btn btn-primary">▶️ Démarrer</button>
                <button id="stopBtn" class="btn btn-secondary" style="display: none;">⏹️ Arrêter</button>
            </div>

            <div class="result" id="result">
                <div style="padding: 20px; color: #666;">
                    Cliquez sur "Démarrer" pour commencer le scan
                </div>
            </div>

            <!-- Debug panel -->
            <div style="padding: 20px; background: #f0f0f0; border-top: 1px solid #ddd;">
                <h4>🔧 Debug Panel</h4>
                <button id="testBtn" class="btn btn-primary" style="background: #28a745;">🧪 Test Communication</button>
                <div id="debugInfo" style="margin-top: 10px; font-family: monospace; font-size: 12px;"></div>
            </div>
        </div>

        <script>
            let codeReader = null;
            let isScanning = false;

            function initCodeReader() {
                try {
                    codeReader = new ZXing.BrowserMultiFormatReader();
                    codeReader.timeBetweenScansMillis = 1000;
                    console.log('ZXing reader initialized successfully');
                } catch (error) {
                    console.error('Failed to initialize ZXing reader:', error);
                    showResult('error', 'Erreur lors de l\\'initialisation du scanner: ' + error.message);
                }
            }

            function sendToStreamlit(key, value) {
                console.log('=== ENVOI VERS STREAMLIT ===');
                console.log('Key:', key);
                console.log('Value:', value);

                try {
                    // MÉTHODE CORRIGÉE: Utiliser l'API Streamlit Components
                    if (key === 'barcode_scanned') {
                        console.log('🔄 Envoi du barcode via Streamlit Component API...');

                        // Créer un input et le marquer comme modifié
                        const input = document.createElement('input');
                        input.type = 'hidden';
                        input.name = 'barcode_scanned';
                        input.value = value;
                        input.id = 'barcode_scanned_' + Date.now();

                        // Ajouter au document
                        document.body.appendChild(input);

                        // Créer un événement de modification
                        const event = new Event('input', { bubbles: true });
                        input.dispatchEvent(event);

                        // Aussi déclencher change
                        const changeEvent = new Event('change', { bubbles: true });
                        input.dispatchEvent(changeEvent);

                        console.log('✅ Input créé et événements déclenchés:', input);

                        // Forcer une détection par Streamlit
                        setTimeout(() => {
                            // Simuler une soumission de formulaire
                            const form = document.createElement('form');
                            form.method = 'POST';
                            form.appendChild(input.cloneNode(true));
                            document.body.appendChild(form);

                            // Pas de soumission automatique, juste forcer la détection
                            console.log('📋 Formulaire créé pour détection Streamlit');
                        }, 100);

                        return;
                    }

                    // Pour close_scanner
                    if (key === 'close_scanner') {
                        console.log('🔄 Envoi close_scanner...');
                        const input = document.createElement('input');
                        input.type = 'hidden';
                        input.name = 'close_scanner';
                        input.value = 'true';
                        input.id = 'close_scanner_' + Date.now();

                        document.body.appendChild(input);
                        input.dispatchEvent(new Event('input', { bubbles: true }));
                        input.dispatchEvent(new Event('change', { bubbles: true }));

                        console.log('✅ close_scanner envoyé');
                        return;
                    }

                } catch (error) {
                    console.error('❌ Erreur générale:', error);
                }
            }

            async function startScanner() {
                const startBtn = document.getElementById('startBtn');
                const stopBtn = document.getElementById('stopBtn');
                const resultDiv = document.getElementById('result');

                startBtn.disabled = true;
                startBtn.textContent = '⏳ Démarrage...';

                try {
                    const videoElement = document.getElementById('video');

                    const stream = await navigator.mediaDevices.getUserMedia({
                        video: { 
                            facingMode: 'environment',
                            width: { ideal: 640, max: 1280 },
                            height: { ideal: 480, max: 720 },
                            frameRate: { ideal: 30, max: 30 }
                        }
                    });

                    videoElement.srcObject = stream;

                    videoElement.onloadedmetadata = () => {
                        videoElement.play().then(() => {
                            setTimeout(() => {
                                try {
                                    // Vérifier que codeReader existe toujours
                                    if (codeReader && isScanning) {
                                        codeReader.decodeFromVideoDevice(undefined, videoElement, (result, err) => {
                                            if (result && result.text && isScanning) {
                                                console.log('Barcode detected:', result.text);
                                                handleScanSuccess(result.text);
                                            }
                                        });

                                        isScanning = true;
                                        startBtn.style.display = 'none';
                                        stopBtn.style.display = 'inline-block';

                                        resultDiv.innerHTML = '<div style="padding: 20px;">🔍 Recherche d\\'un code-barres...</div>';
                                    } else {
                                        console.log('❌ codeReader détruit ou scanning arrêté');
                                        resetStartButton();
                                    }
                                } catch (decodeError) {
                                    console.error('Decode error:', decodeError);
                                    showResult('error', 'Erreur lors du démarrage de la détection: ' + decodeError.message);
                                    resetStartButton();
                                }
                            }, 500);

                        }).catch(playError => {
                            console.error('Video play error:', playError);
                            showResult('error', 'Erreur lors du démarrage de la vidéo: ' + playError.message);
                            resetStartButton();
                        });
                    };

                } catch (error) {
                    console.error('Camera access error:', error);
                    let errorMessage = 'Erreur: ' + error.message;

                    if (error.name === 'NotAllowedError') {
                        errorMessage = 'Accès à la caméra refusé. Veuillez autoriser l\\'accès à la caméra dans les paramètres de votre navigateur.';
                    } else if (error.name === 'NotFoundError') {
                        errorMessage = 'Aucune caméra détectée sur cet appareil.';
                    } else if (error.name === 'NotReadableError') {
                        errorMessage = 'La caméra est déjà utilisée par une autre application.';
                    }

                    showResult('error', errorMessage);
                    resetStartButton();
                }
            }

            function resetStartButton() {
                const startBtn = document.getElementById('startBtn');
                startBtn.disabled = false;
                startBtn.textContent = '▶️ Démarrer';
            }

            function stopScanner() {
                const videoElement = document.getElementById('video');
                const startBtn = document.getElementById('startBtn');
                const stopBtn = document.getElementById('stopBtn');

                if (codeReader) {
                    try {
                        codeReader.reset();
                    } catch (error) {
                        console.error('Error resetting reader:', error);
                    }
                }

                isScanning = false;

                if (videoElement.srcObject) {
                    const tracks = videoElement.srcObject.getTracks();
                    tracks.forEach(track => {
                        track.stop();
                    });
                    videoElement.srcObject = null;
                }

                startBtn.style.display = 'inline-block';
                startBtn.disabled = false;
                startBtn.textContent = '▶️ Démarrer';
                stopBtn.style.display = 'none';

                showResult('info', 'Cliquez sur "Démarrer" pour commencer le scan');
            }

            function handleScanSuccess(barcode) {
                console.log('Handling scan success for barcode:', barcode);

                // ARRÊTER DÉFINITIVEMENT le scanner
                isScanning = false;

                // DÉTRUIRE le codeReader pour éviter les redémarrages
                if (codeReader) {
                    try {
                        codeReader.reset();
                        console.log('ZXing reader reset successful');

                        // DÉTRUIRE complètement le reader
                        codeReader = null;
                        console.log('ZXing reader destroyed');
                    } catch (error) {
                        console.error('Error resetting reader:', error);
                    }
                }

                // ARRÊTER la vidéo
                const videoElement = document.getElementById('video');
                if (videoElement.srcObject) {
                    const tracks = videoElement.srcObject.getTracks();
                    tracks.forEach(track => {
                        track.stop();
                        console.log('Video track stopped:', track);
                    });
                    videoElement.srcObject = null;
                    console.log('Video tracks stopped completely');
                }

                // METTRE À JOUR les boutons
                const startBtn = document.getElementById('startBtn');
                const stopBtn = document.getElementById('stopBtn');
                startBtn.style.display = 'inline-block';
                startBtn.disabled = false;
                startBtn.textContent = '▶️ Démarrer';
                stopBtn.style.display = 'none';

                showResult('success', '✅ Code-barres détecté : ' + barcode);

                console.log('=== BARCODE DETECTED ===');
                console.log('Value:', barcode);
                console.log('Type:', typeof barcode);
                console.log('Length:', barcode.length);
                console.log('========================');

                // Envoyer AUTOMATIQUEMENT à Streamlit
                console.log('🔄 Envoi du barcode à Streamlit...');
                sendToStreamlit('barcode_scanned', barcode);

                // Fermer automatiquement après 2 secondes
                setTimeout(() => {
                    if (isScanning === false) {  // Vérifier que le scanner n'a pas redémarré
                        sendToStreamlit('close_scanner', true);
                    }
                }, 2000);
            }

            function showResult(type, message) {
                const resultDiv = document.getElementById('result');

                if (type === 'success') {
                    resultDiv.innerHTML = '<div class="result-success">' + message + '</div>';
                } else if (type === 'error') {
                    resultDiv.innerHTML = '<div class="error-message">' + message + '</div>';
                } else {
                    resultDiv.innerHTML = '<div style="padding: 20px; color: #666;">' + message + '</div>';
                }
            }

            function updateDebugInfo(message) {
                const debugDiv = document.getElementById('debugInfo');
                const timestamp = new Date().toLocaleTimeString();
                debugDiv.innerHTML = timestamp + ': ' + message + '<br>' + debugDiv.innerHTML;
            }

            document.addEventListener('DOMContentLoaded', () => {
                console.log('Initializing barcode scanner...');
                updateDebugInfo('Scanner initialisé');

                initCodeReader();

                const startBtn = document.getElementById('startBtn');
                const stopBtn = document.getElementById('stopBtn');
                const testBtn = document.getElementById('testBtn');

                if (startBtn) {
                    startBtn.addEventListener('click', () => {
                        updateDebugInfo('Bouton Démarrer cliqué');
                        startScanner();
                    });
                }

                if (stopBtn) {
                    stopBtn.addEventListener('click', () => {
                        updateDebugInfo('Bouton Arrêter cliqué');
                        stopScanner();
                    });
                }

                if (testBtn) {
                    testBtn.addEventListener('click', () => {
                        updateDebugInfo('Test communication - rechargement avec barcode test...');
                        sendToStreamlit('barcode_scanned', '1234567890123');
                    });
                }

                if (navigator.mediaDevices && navigator.mediaDevices.enumerateDevices) {
                    navigator.mediaDevices.enumerateDevices()
                        .then(devices => {
                            const videoDevices = devices.filter(device => device.kind === 'videoinput');
                            console.log('Found video devices:', videoDevices.length);
                            updateDebugInfo('Caméras détectées: ' + videoDevices.length);

                            if (videoDevices.length === 0) {
                                showResult('error', 'Aucune caméra détectée sur cet appareil');
                                if (startBtn) startBtn.disabled = true;
                                updateDebugInfo('❌ Aucune caméra détectée');
                            }
                        })
                        .catch(err => {
                            console.error('Error enumerating devices:', err);
                            updateDebugInfo('❌ Erreur détection caméras: ' + err.message);
                        });
                }
            });

            window.addEventListener('beforeunload', () => {
                stopScanner();
            });
        </script>
    </body>
    </html>
    """

    # Créer le composant Streamlit
    return components.html(scanner_html, height=750)


def get_barcode_result():
    """Récupère le résultat du scanner depuis session_state"""
    return st.session_state.get('barcode_result', None)


def should_close_scanner():
    """Vérifie si le scanner doit être fermé"""
    return st.session_state.get('close_scanner', False)
