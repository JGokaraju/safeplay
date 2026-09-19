# SafePlay

Laptop dashboard: `pip install -r monitor/requirements.txt`, fill `.env` (see `.env.example`), then
`python -m streamlit run monitor/app.py --server.address 0.0.0.0` and open `http://<laptop-ip>:8501` (phone on same Wi-Fi/Tailscale).

Raspberry Pi: see `rpi/` (`.env.example`, `requirements.txt`, `safeplay.service`).
