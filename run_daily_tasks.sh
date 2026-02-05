#!/bin/zsh
cd "$(dirname "$0")"
python manage.py mark_rent_late
