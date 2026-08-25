-- Migration: Add settings and role columns to users table
-- Run after initial init.sql

ALTER TABLE users ADD COLUMN IF NOT EXISTS settings JSONB DEFAULT '{}';
ALTER TABLE users ADD COLUMN IF NOT EXISTS role VARCHAR(20) DEFAULT 'user';  -- 'user' | 'admin'
