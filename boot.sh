#!/bin/sh
exec gunicorn -b :80 --access-logfile - --error-logfile - --timeout ${GUNICORN_TIMEOUT:-30} apolpi:app
