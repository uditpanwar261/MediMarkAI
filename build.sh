#!/usr/bin/env bash
# MediMark AI — Render Build Script
# Render runs this automatically after installing dependencies.
# It creates DB tables and seeds demo data.

set -e   # exit on any error

echo "=== MediMark AI Build Script ==="

echo "--- Creating database tables..."
flask --app app db-init 2>/dev/null || flask --app manage db-init

echo "--- Seeding demo data..."
flask --app manage seed

echo "=== Build complete ==="
