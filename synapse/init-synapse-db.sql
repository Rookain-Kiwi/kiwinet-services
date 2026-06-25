-- ============================================================================
-- PostgreSQL Initialization for Synapse (Matrix Server)
-- ============================================================================
-- Ce script est exécuté automatiquement au démarrage du container PostgreSQL
-- il crée l'utilisateur synapse et la base de données synapse

-- Création de l'utilisateur synapse avec la password du .env
CREATE USER synapse WITH PASSWORD :'SYNAPSE_DB_PASSWORD';

-- Création de la base de données synapse
CREATE DATABASE synapse WITH OWNER synapse ENCODING 'UTF8' LC_COLLATE 'C' LC_CTYPE 'C';

-- Attribution des permissions sur la base synapse à l'utilisateur synapse
GRANT ALL PRIVILEGES ON DATABASE synapse TO synapse;

-- Attribution des permissions sur le schéma public (PostgreSQL 15+ requirement)
GRANT ALL ON SCHEMA public TO synapse;

-- Attribution des permissions par défaut pour les tables futures
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO synapse;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO synapse;

-- Log de succès
\echo 'Synapse database and user created successfully'
