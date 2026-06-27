#!/bin/bash
echo "Project Akasha Setup Starting..."
sudo apt update && sudo apt install python3-pip ffmpeg -y
pip install -r requirements.txt
echo "🏳️Setup Complete! Now fill your .env file and run 'python3 main.py'"
