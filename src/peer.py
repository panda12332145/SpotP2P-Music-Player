"""Spot P2P — peer unificado: servidor Flask + cliente P2P + CLI.

Uso:
    python -m src.peer --port 5001            # inicia peer com menu CLI
    python -m src.peer --port 5000 --no-menu   # só servidor (para UI)
"""
import argparse
import os
import time
from threading import Thread

import requests
from flask import Flask, jsonify, send_file

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_MUSIC = os.path.join(ROOT, "data", "music")


class P2PClient:
    """Cliente P2P: varredura da pasta local, descoberta e download."""

    def __init__(self, music_dir: str = None, peers: list = None,
                 self_port: int = 5001):
        self.music_dir = music_dir or DEFAULT_MUSIC
        self.self_url = f"http://localhost:{self_port}"
        self.known_peers = list(peers or [f"http://localhost:{p}"
                                          for p in (5000, 5001)])
        self.shared_files = self.scan_music_folder()

    def scan_music_folder(self):
        os.makedirs(self.music_dir, exist_ok=True)
        return sorted(f for f in os.listdir(self.music_dir)
                      if f.lower().endswith((".mp3", ".wav", ".ogg")))

    def update_peers(self, new_peer):
        if new_peer not in self.known_peers:
            self.known_peers.append(new_peer)

    def share_file(self, filename):
        if filename not in self.shared_files:
            self.shared_files.append(filename)

    def download_file(self, filename, timeout: float = 5.0) -> bool:
        """Baixa um arquivo do primeiro peer que o oferecer."""
        safe = os.path.basename(filename)
        if not safe or safe != filename:
            return False
        for peer in self.known_peers:
            try:
                if peer == self.self_url:
                    continue
                r = requests.get(f"{peer}/files", timeout=timeout)
                if r.status_code == 200 and safe in r.json():
                    fr = requests.get(f"{peer}/download/{safe}",
                                      timeout=timeout)
                    if fr.status_code == 200:
                        with open(os.path.join(self.music_dir, safe), "wb") as f:
                            f.write(fr.content)
                        self.shared_files = self.scan_music_folder()
                        return True
            except requests.exceptions.RequestException:
                continue
        return False

    def network_files(self, timeout: float = 3.0) -> dict:
        """Arquivos oferecidos por cada peer conhecido."""
        out = {}
        for peer in self.known_peers:
            try:
                r = requests.get(f"{peer}/files", timeout=timeout)
                if r.status_code == 200:
                    out[peer] = r.json()
            except requests.exceptions.RequestException:
                continue
        return out


def create_app(client: P2PClient) -> Flask:
    """Factory do app Flask (testável sem subir servidor real)."""
    app = Flask(__name__)
    app.config["CLIENT"] = client

    @app.route("/")
    def index():
        return "Peer node running"

    @app.route("/files")
    def list_files():
        return jsonify(client.shared_files)

    @app.route("/download/<filename>")
    def download(filename):
        # Proteção contra path traversal: só o basename é aceito
        safe = os.path.basename(filename)
        if safe != filename or not safe:
            return "Invalid filename", 400
        file_path = os.path.join(client.music_dir, safe)
        real = os.path.realpath(file_path)
        if not real.startswith(os.path.realpath(client.music_dir) + os.sep):
            return "Invalid path", 400
        if os.path.isfile(real):
            return send_file(real, as_attachment=True)
        return "File not found", 404

    return app


def peer_discovery(client: P2PClient, interval: float = 30.0):
    while True:
        time.sleep(interval)
        for peer in list(client.known_peers):
            try:
                r = requests.get(f"{peer}/files", timeout=3)
                if r.status_code == 200:
                    client.update_peers(peer)
            except requests.exceptions.RequestException:
                continue


def _cli_menu(client: P2PClient):
    while True:
        print("\n1. Listar arquivos disponíveis")
        print("2. Baixar arquivo")
        print("3. Sair")
        choice = input("Escolha uma opção: ").strip()
        if choice == "1":
            for peer, files in client.network_files().items():
                print(f"Peer {peer}: {', '.join(files) or '(vazio)'}")
            print(f"Local: {', '.join(client.shared_files) or '(vazio)'}")
        elif choice == "2":
            name = input("Nome do arquivo para baixar: ").strip()
            if client.download_file(name):
                print(f"Arquivo {name} baixado com sucesso!")
            else:
                print("Arquivo não encontrado na rede")
        elif choice == "3":
            return
        else:
            print("Opção inválida.")


def main():
    ap = argparse.ArgumentParser(description="Spot P2P peer")
    ap.add_argument("--port", type=int, default=5001)
    ap.add_argument("--music", default=None, help="pasta de música")
    ap.add_argument("--no-menu", action="store_true",
                    help="só servidor (para usar com a UI)")
    args = ap.parse_args()

    client = P2PClient(music_dir=args.music, self_port=args.port)
    app = create_app(client)
    Thread(target=peer_discovery, args=(client,), daemon=True).start()
    Thread(target=lambda: app.run(host="0.0.0.0", port=args.port,
                                  debug=False, use_reloader=False),
          daemon=True).start()
    print(f"[+] Peer em http://0.0.0.0:{args.port} | música: {client.music_dir}")
    if args.no_menu:
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            return
    _cli_menu(client)


if __name__ == "__main__":
    main()
