import streamlit as st
import os
from streamlit.components.v1 import declare_component

# On définit le nom du composant et le chemin vers le build du frontend
_COMPONENT_NAME = "barcode_scanner"
_component_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "frontend", "build")

# On déclare la fonction du composant
barcode_scanner = declare_component(_COMPONENT_NAME, path=_component_path)
