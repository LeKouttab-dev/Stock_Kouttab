-- Script SQL pour créer la structure complète de la base de données
-- À exécuter dans phpMyAdmin O2Switch

-- Création de la base si elle n'existe pas
CREATE DATABASE IF NOT EXISTS `sc9bewu6999_stock` DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE `sc9bewu6999_stock`;

-- Table Stock
CREATE TABLE IF NOT EXISTS `Stock` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `nom` VARCHAR(255) NOT NULL UNIQUE,
    `categorie` VARCHAR(255) NOT NULL,
    `sous_categorie` VARCHAR(255),
    `quantite` INT NOT NULL DEFAULT 0,
    `seuil_alerte` INT NOT NULL DEFAULT 10,
    `emoji` VARCHAR(10) DEFAULT '📦',
    `alert_sent` BOOLEAN DEFAULT FALSE,
    `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    `updated_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX `idx_categorie` (`categorie`),
    INDEX `idx_nom` (`nom`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Table Categories
CREATE TABLE IF NOT EXISTS `Categories` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `nom` VARCHAR(255) NOT NULL UNIQUE,
    `is_default` BOOLEAN DEFAULT FALSE,
    `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX `idx_nom` (`nom`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Table SousCategories
CREATE TABLE IF NOT EXISTS `SousCategories` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `nom_categorie` VARCHAR(255) NOT NULL,
    `nom_sous_categorie` VARCHAR(255) NOT NULL,
    `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY `unique_category_sub` (`nom_categorie`, `nom_sous_categorie`),
    INDEX `idx_categorie` (`nom_categorie`),
    INDEX `idx_sous_categorie` (`nom_sous_categorie`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Table Admins
CREATE TABLE IF NOT EXISTS `Admins` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `username` VARCHAR(50) NOT NULL UNIQUE,
    `password_hash` VARCHAR(255) NOT NULL,
    `role` VARCHAR(50) NOT NULL DEFAULT 'Benevole',
    `validation_status` VARCHAR(20) DEFAULT 'pending',
    `nom` VARCHAR(255),
    `prenom` VARCHAR(255),
    `email` VARCHAR(255),
    `telephone` VARCHAR(50),
    `rib` VARCHAR(255),
    `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    `updated_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX `idx_username` (`username`),
    INDEX `idx_email` (`email`),
    INDEX `idx_role` (`role`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Table NotesDeFrais
CREATE TABLE IF NOT EXISTS `NotesDeFrais` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `id_user` INT NOT NULL,
    `date_depense` DATE NOT NULL,
    `rattachement` VARCHAR(255),
    `fournisseur` VARCHAR(255),
    `nature_charge` VARCHAR(255),
    `montant` DECIMAL(10,2) NOT NULL DEFAULT 0.00,
    `commentaires` TEXT,
    `remb_emis` BOOLEAN DEFAULT FALSE,
    `remise` DECIMAL(10,2) DEFAULT 0.00,
    `status` VARCHAR(20) DEFAULT 'En attente',
    `commentaires_compta` TEXT,
    `date_soumission` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    `updated_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX `idx_user` (`id_user`),
    INDEX `idx_status` (`status`),
    INDEX `idx_date_depense` (`date_depense`),
    FOREIGN KEY (`id_user`) REFERENCES `Admins`(`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Table FichiersNotesDeFrais
CREATE TABLE IF NOT EXISTS `FichiersNotesDeFrais` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `id_note_de_frais` INT NOT NULL,
    `nom_fichier` VARCHAR(255) NOT NULL,
    `chemin_fichier` VARCHAR(500) NOT NULL,
    `taille_fichier` INT,
    `type_fichier` VARCHAR(100),
    `date_upload` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX `idx_note_de_frais` (`id_note_de_frais`),
    FOREIGN KEY (`id_note_de_frais`) REFERENCES `NotesDeFrais`(`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Table Factures
CREATE TABLE IF NOT EXISTS `Factures` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `id_user` INT NOT NULL,
    `commentaire` TEXT,
    `date_depot` DATE NOT NULL,
    `status` VARCHAR(20) DEFAULT 'En attente',
    `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    `updated_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX `idx_user` (`id_user`),
    INDEX `idx_status` (`status`),
    INDEX `idx_date_depot` (`date_depot`),
    FOREIGN KEY (`id_user`) REFERENCES `Admins`(`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Table FichiersFactures
CREATE TABLE IF NOT EXISTS `FichiersFactures` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `id_facture` INT NOT NULL,
    `nom_fichier` VARCHAR(255) NOT NULL,
    `chemin_fichier` VARCHAR(500) NOT NULL,
    `taille_fichier` INT,
    `type_fichier` VARCHAR(100),
    `date_upload` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX `idx_facture` (`id_facture`),
    FOREIGN KEY (`id_facture`) REFERENCES `Factures`(`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Table StockModifications
CREATE TABLE IF NOT EXISTS `StockModifications` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `id_user` INT NOT NULL,
    `id_stock` INT NOT NULL,
    `quantite_actuelle` INT NOT NULL,
    `quantite_demandee` INT NOT NULL,
    `date_demande` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    `status` VARCHAR(20) DEFAULT 'En attente',
    `approuve_par` INT,
    `date_approbation` TIMESTAMP NULL,
    `commentaires` TEXT,
    INDEX `idx_user` (`id_user`),
    INDEX `idx_stock` (`id_stock`),
    INDEX `idx_status` (`status`),
    INDEX `idx_date_demande` (`date_demande`),
    FOREIGN KEY (`id_user`) REFERENCES `Admins`(`id`) ON DELETE CASCADE,
    FOREIGN KEY (`id_stock`) REFERENCES `Stock`(`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Table AdminInvitations
CREATE TABLE IF NOT EXISTS `AdminInvitations` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `email` VARCHAR(255) NOT NULL UNIQUE,
    `token_hash` VARCHAR(255) NOT NULL,
    `expires_at` TIMESTAMP NOT NULL,
    `used` BOOLEAN DEFAULT FALSE,
    `attempts` INT DEFAULT 0,
    `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX `idx_email` (`email`),
    INDEX `idx_token` (`token_hash`),
    INDEX `idx_expires_at` (`expires_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Insertion des catégories par défaut
INSERT IGNORE INTO `Categories` (`nom`, `is_default`) VALUES 
('Nourriture', TRUE),
('Fournitures', TRUE),
('Intendance', TRUE),
('Bibliothèque', TRUE);

-- Insertion des sous-catégories par défaut
INSERT IGNORE INTO `SousCategories` (`nom_categorie`, `nom_sous_categorie`) VALUES 
('Nourriture', 'Snacks'),
('Nourriture', 'Boissons'),
('Nourriture', 'Produits frais'),
('Fournitures', 'Papeterie'),
('Fournitures', 'Nettoyage'),
('Fournitures', 'Informatique'),
('Intendance', 'Entretien'),
('Intendance', 'Sécurité'),
('Intendance', 'Équipement'),
('Bibliothèque', 'Livres'),
('Bibliothèque', 'Magazines'),
('Bibliothèque', 'Documents');

-- Création d'un utilisateur admin par défaut (mot de passe: admin123)
INSERT IGNORE INTO `Admins` (`username`, `password_hash`, `role`, `validation_status`, `nom`, `prenom`, `email`) VALUES 
('admin', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewdBPj6ukx.LFvOe', 'Super Admin', 'active', 'Admin', 'System', 'admin@lekouttab.fr');

-- Affichage du résumé
SELECT 'Base de données créée avec succès !' AS message;
SELECT COUNT(*) AS nb_categories FROM Categories;
SELECT COUNT(*) AS nb_sous_categories FROM SousCategories;
SELECT COUNT(*) AS nb_admins FROM Admins;
