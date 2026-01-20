import logging

def setup_logger():
    """
    Configure et retourne un logger pour l'application.
    """
    # Évite d'ajouter plusieurs handlers si la fonction est appelée plusieurs fois
    if logging.getLogger('gestion_stock').hasHandlers():
        return logging.getLogger('gestion_stock')

    # Créer le logger principal
    logger = logging.getLogger('gestion_stock')
    logger.setLevel(logging.INFO)

    # Créer un formateur
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')

    # Handler pour la console uniquement
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    # Ajouter le handler console au logger
    logger.addHandler(console_handler)

    return logger

# Initialiser et obtenir le logger pour que les autres modules puissent l'importer
logger = setup_logger()
