import requests
import streamlit as st

def get_product_info_from_openfoodfacts(barcode):
    """
    Interroge l'API d'Open Food Facts pour obtenir les informations d'un produit.
    """
    api_url = f"https://world.openfoodfacts.org/api/v0/product/{barcode}.json"
    
    try:
        response = requests.get(api_url)
        response.raise_for_status()  # Lève une exception pour les codes d'erreur HTTP
        
        data = response.json()
        
        if data.get("status") == 1:
            product = data.get("product")
            product_name = product.get("product_name_fr") or product.get("product_name")
            image_url = product.get("image_front_url")
            
            if product_name:
                return {
                    "name": product_name,
                    "image_url": image_url
                }
            else:
                return None
        else:
            return None
            
    except requests.exceptions.RequestException as e:
        st.error(f"Erreur de connexion à l'API : {e}")
        return None
    except Exception as e:
        st.error(f"Une erreur est survenue lors du traitement des données : {e}")
        return None
