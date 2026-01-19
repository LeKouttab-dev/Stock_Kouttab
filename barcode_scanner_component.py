import streamlit as st
import streamlit.components.v1 as components
import os

def barcode_scanner_component():
    """Composant de scanner de codes barres professionnel"""
    
    # HTML et JavaScript pour le scanner
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
            
            .scanner-line {
                position: absolute;
                width: 100%;
                height: 2px;
                background: linear-gradient(90deg, transparent, #00ff88, transparent);
                animation: scan 2s linear infinite;
            }
            
            @keyframes scan {
                0% { top: 0; }
                100% { top: 100%; }
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
            }
            
            .btn-primary {
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
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
                    <div class="scanner-line"></div>
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
        </div>

        <script>
            let codeReader = null;
            let isScanning = false;
            
            function initCodeReader() {
                codeReader = new ZXing.BrowserMultiFormatReader();
                codeReader.timeBetweenScansMillis = 800;
            }
            
            async function startScanner() {
                try {
                    const videoElement = document.getElementById('video');
                    const startBtn = document.getElementById('startBtn');
                    const stopBtn = document.getElementById('stopBtn');
                    const resultDiv = document.getElementById('result');
                    
                    const stream = await navigator.mediaDevices.getUserMedia({
                        video: { 
                            facingMode: 'environment',
                            width: { ideal: 1280 },
                            height: { ideal: 720 }
                        }
                    });
                    
                    videoElement.srcObject = stream;
                    
                    videoElement.onloadedmetadata = () => {
                        videoElement.play();
                        
                        codeReader.decodeFromVideoDevice(undefined, videoElement, (result, err) => {
                            if (result && result.text && isScanning) {
                                handleScanSuccess(result.text);
                            }
                        });
                        
                        isScanning = true;
                        startBtn.style.display = 'none';
                        stopBtn.style.display = 'inline-block';
                        
                        resultDiv.innerHTML = '<div style="padding: 20px;">🔍 Recherche d\'un code-barres...</div>';
                    };
                    
                } catch (error) {
                    console.error('Erreur:', error);
                    showResult('error', 'Erreur: ' + error.message);
                }
            }
            
            function stopScanner() {
                const videoElement = document.getElementById('video');
                const startBtn = document.getElementById('startBtn');
                const stopBtn = document.getElementById('stopBtn');
                
                if (videoElement.srcObject) {
                    videoElement.srcObject.getTracks().forEach(track => track.stop());
                    videoElement.srcObject = null;
                }
                
                if (codeReader) {
                    codeReader.reset();
                }
                
                isScanning = false;
                startBtn.style.display = 'inline-block';
                stopBtn.style.display = 'none';
                
                showResult('info', 'Cliquez sur "Démarrer" pour commencer le scan');
            }
            
            function handleScanSuccess(barcode) {
                stopScanner();
                showResult('success', '✅ Code-barres détecté : ' + barcode);
                
                // Envoyer à Streamlit
                window.parent.postMessage({
                    type: 'streamlit:setComponentValue',
                    key: 'barcode_result',
                    value: barcode
                }, '*');
                
                setTimeout(() => {
                    window.parent.postMessage({
                        type: 'streamlit:setComponentValue',
                        key: 'close_scanner',
                        value: true
                    }, '*');
                }, 2000);
            }
            
            function showResult(type, message) {
                const resultDiv = document.getElementById('result');
                
                if (type === 'success') {
                    resultDiv.innerHTML = '<div class="result-success">' + message + '</div>';
                } else {
                    resultDiv.innerHTML = '<div style="padding: 20px; color: #666;">' + message + '</div>';
                }
            }
            
            document.addEventListener('DOMContentLoaded', () => {
                initCodeReader();
                document.getElementById('startBtn').addEventListener('click', startScanner);
                document.getElementById('stopBtn').addEventListener('click', stopScanner);
            });
            
            window.addEventListener('beforeunload', () => {
                stopScanner();
            });
        </script>
    </body>
    </html>
    """
    
    # Créer le composant Streamlit
    return components.html(scanner_html, height=650)

def get_barcode_result():
    """Récupère le résultat du scanner depuis session_state"""
    return st.session_state.get('barcode_result', None)

def should_close_scanner():
    """Vérifie si le scanner doit être fermé"""
    return st.session_state.get('close_scanner', False)
