#!/usr/bin/env bash
# Script para iniciar el servidor del Museo y Estudio de Audiodescripción
set -e

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
cd "$DIR"

echo "=========================================================="
echo " Centro de Interpretación Santuario Ibérico de El Pajarillo"
echo " Servidor de Audiodescripción Accesible para Museos (MUSA)"
echo "=========================================================="
echo ""
echo "Iniciando servidor local en el puerto 8000..."
echo ""
echo "-> Pantalla del Museo (Kiosco TV):  http://localhost:8000"
echo "-> Estudio de Audiodescripción IA:   http://localhost:8000/editor"
echo ""

./.venv/bin/python3 -m uvicorn app:app --host 0.0.0.0 --port 8000 --reload
