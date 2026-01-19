# Gestion de Stock et Notes de Frais - Le Kouttâb

Cette application, développée avec Streamlit, permet de gérer les stocks et les notes de frais de l'institut.

## Prérequis

- Avoir Python installé sur votre machine (version 3.8 ou supérieure). Vous pouvez le télécharger depuis [python.org](https://www.python.org/downloads/).
- Avoir un compte Gmail pour l'envoi des e-mails d'alerte (facultatif).

## Installation

Suivez ces étapes pour lancer l'application sur votre ordinateur.

### 1. Cloner ou Télécharger le Projet

- **Si vous avez Git :** Ouvrez un terminal et clonez le projet avec la commande suivante :
  ```sh
  git clone https://github.com/oumss91370/Gestion_Stock_Kouttab.git
  ```
- **Sinon :** Téléchargez le projet en format ZIP depuis la page GitHub et décompressez-le dans un dossier de votre choix.

### 2. Se Placer dans le Dossier du Projet

Ouvrez un terminal (ou une invite de commandes) et naviguez jusqu'au dossier du projet que vous venez de cloner ou de décompresser.

```sh
cd chemin/vers/le/dossier/Gestion_Stock_Kouttab
```

### 3. Créer un Environnement Virtuel (Recommandé)

C'est une bonne pratique pour isoler les dépendances du projet.

```sh
python -m venv .venv
```

Activez ensuite l'environnement :
- **Sur Windows :**
  ```sh
  .venv\Scripts\activate
  ```
- **Sur macOS / Linux :**
  ```sh
  source .venv/bin/activate
  ```

### 4. Installer les Bibliothèques

Installez toutes les bibliothèques nécessaires en une seule commande grâce au fichier `requirements.txt`.

```sh
pip install -r requirements.txt
```

### 5. Configurer les E-mails (Facultatif)

Si vous souhaitez que l'application envoie des e-mails d'alerte de stock bas :

1.  Créez un dossier nommé `.streamlit` à la racine du projet.
2.  À l'intérieur de ce dossier, créez un fichier nommé `secrets.toml`.
3.  Copiez-y le contenu suivant et remplacez par vos informations :

    ```toml
    # .streamlit/secrets.toml
    [email_credentials]
    sender_email = "votre_email@gmail.com"
    sender_password = "votre_mot_de_passe_application_a_16_lettres"
    ```
    **Note :** Pour des raisons de sécurité, il est fortement recommandé d'utiliser un **"Mot de passe d'application"** généré par Google plutôt que votre mot de passe habituel.

## Lancement de l'Application

Une fois l'installation terminée, lancez l'application avec la commande suivante dans votre terminal :

```sh
streamlit run app.py
```

L'application devrait s'ouvrir automatiquement dans votre navigateur web.

## Accès à l'Application

- **Compte Super Administrateur par défaut :**
  - **Nom d'utilisateur :** `admin`
  - **Mot de passe :** `kouttab_admin`

Vous pouvez ensuite créer d'autres comptes directement depuis l'interface.
