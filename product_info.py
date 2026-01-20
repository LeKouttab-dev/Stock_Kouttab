import requests
import streamlit as st

def get_product_info_from_openfoodfacts(barcode):
    """
    Interroge l'API d'Open Food Facts pour obtenir les informations d'un produit.
    Cherche plusieurs champs de nom possibles pour maximiser les chances de succès.
    """
    api_url = f"https://world.openfoodfacts.org/api/v2/product/{barcode}"
    
    try:
        response = requests.get(api_url)
        response.raise_for_status()
        
        data = response.json()
        
        if data.get("status") == 1:
            product = data.get("product")
            
            # Essayer de trouver un nom dans plusieurs champs, par ordre de priorité
            name_fields = [
                "product_name_fr", "generic_name_fr",
                "product_name", "generic_name",
                "product_name_en", "generic_name_en"
            ]
            
            product_name = None
            for field in name_fields:
                if product.get(field):
                    product_name = product.get(field)
                    break # On a trouvé un nom, on arrête de chercher

            image_url = product.get("image_front_url")
            
            if product_name:
                print(f"✅ Produit trouvé : {product_name}")
                return {
                    "name": product_name,
                    "image_url": image_url
                }
            else:
                print("Produit trouvé, mais aucun nom utilisable.")
                return None
        else:
            print(f"Produit non trouvé dans Open Food Facts pour le code-barres : {barcode}")
            return None
            
    except requests.exceptions.RequestException as e:
        st.error(f"Erreur de connexion à l'API : {e}")
        return None
    except Exception as e:
        st.error(f"Une erreur est survenue lors du traitement des données : {e}")
        print(f"Erreur lors du traitement JSON : {e}")
        return None
