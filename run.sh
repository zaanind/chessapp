#!/bin/bash

cd /home/getcheaphost-chessapp/htdocs/chessapp.getcheaphost.com && \
source venv/bin/activate && \
cd chessapp && \
exec daphne -b 0.0.0.0 -p 8000 chessapp.asgi:application
