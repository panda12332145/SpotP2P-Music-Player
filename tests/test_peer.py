"""Testes do SpotP2P-Music-Player (peer real em porta efêmera)."""
import os
import sys
import tempfile
import threading

import requests
from werkzeug.serving import make_server

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.peer import P2PClient, create_app


def _client(tmp, port=5001):
    return P2PClient(music_dir=tmp, self_port=port, peers=[])


def test_files_route_and_download(tmp_path_factory=None):
    tmp = tempfile.mkdtemp(prefix="p2p_a_")
    with open(os.path.join(tmp, "song.mp3"), "wb") as f:
        f.write(b"ID3-music-bytes")
    c = _client(tmp, port=5000)
    app = create_app(c)
    tc = app.test_client()
    r = tc.get("/files")
    assert r.status_code == 200 and r.get_json() == ["song.mp3"]
    r = tc.get("/download/song.mp3")
    assert r.status_code == 200 and r.data == b"ID3-music-bytes"
    assert tc.get("/download/nao_existe.mp3").status_code == 404


def test_path_traversal_blocked():
    tmp = tempfile.mkdtemp(prefix="p2p_b_")
    # deixa um arquivo sensível FORA da pasta de música
    secret = os.path.join(os.path.dirname(tmp), "secret.txt")
    with open(secret, "w") as f:
        f.write("segredo")
    c = _client(tmp, port=5000)
    tc = create_app(c).test_client()
    nome_fora = os.path.basename(secret)
    r = tc.get(f"/download/..%2F..%2F{nome_fora}")
    assert r.status_code in (400, 404), f"traversal passou: {r.status_code}"
    r = tc.get("/download/../secret.txt")
    assert r.status_code in (400, 404)


def test_scan_only_music_exts():
    tmp = tempfile.mkdtemp(prefix="p2p_c_")
    for n in ("a.mp3", "b.wav", "c.ogg", "readme.txt"):
        open(os.path.join(tmp, n), "w").close()
    c = _client(tmp, port=5000)
    assert c.shared_files == ["a.mp3", "b.wav", "c.ogg"]


def test_p2p_download_between_real_peers():
    """Sobe 2 peers em portas reais e baixa de um no outro."""
    tmp_a = tempfile.mkdtemp(prefix="p2p_peerA_")
    tmp_b = tempfile.mkdtemp(prefix="p2p_peerB_")
    with open(os.path.join(tmp_a, "hit.mp3"), "wb") as f:
        f.write(b"BYTES-DA-MUSICA")

    client_a = _client(tmp_a, port=5000)
    app_a = create_app(client_a)
    srv = make_server("127.0.0.1", 0, app_a)
    port_a = srv.socket.getsockname()[1]
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        url_a = f"http://127.0.0.1:{port_a}"
        # sanity: servidor real responde
        assert requests.get(f"{url_a}/files", timeout=5).json() == ["hit.mp3"]
        client_b = P2PClient(music_dir=tmp_b, self_port=5001,
                             peers=[url_a])
        assert client_b.download_file("hit.mp3") is True
        got = os.path.join(tmp_b, "hit.mp3")
        assert open(got, "rb").read() == b"BYTES-DA-MUSICA"
        # sem o arquivo → False
        assert client_b.download_file("fantasma.mp3") is False
        # traversal no cliente → False sem tocar rede
        assert client_b.download_file("../etc/passwd") is False
    finally:
        srv.shutdown()


def test_ui_import_headless():
    # importa o módulo da UI sem abrir janela (sem display)
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    import importlib
    import src.ui_player as ui
    importlib.reload(ui)
    assert hasattr(ui, "NexusStreamPlayer")


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"✅ {fn.__name__}")
    print(f"\n{len(fns)} testes passaram.")
