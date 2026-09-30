"""Spot P2P — interface gráfica do player (customtkinter + pygame.mixer).

Funcional: lista arquivos da rede, baixa para a pasta local e
reproduz com play/pause, anterior e próxima.
"""
import os
import threading

import customtkinter as ctk
from PIL import Image, ImageTk
from tkinter import ttk, Listbox, SINGLE, END, ANCHOR

try:
    import pygame
    _MIXER_OK = True
except Exception:
    _MIXER_OK = False

from .peer import P2PClient, DEFAULT_MUSIC

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CAPA = os.path.join(ROOT, "data", "capa.png")


class NexusStreamPlayer(ctk.CTk):
    def __init__(self, peer_port: int = 5001):
        super().__init__()
        self.client = P2PClient(self_port=peer_port)
        self.current_file = None
        self.playing = False
        if _MIXER_OK:
            pygame.mixer.init()

        self.title("Spot P2P Decentralized")
        self.geometry("1100x650")
        self.magenta = "#FF00FF"
        self.configure(fg_color="#121212")
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.create_sidebar()
        self.main_area = ctk.CTkFrame(self, fg_color="#121212")
        self.main_area.grid(row=0, column=1, rowspan=3, sticky="nsew",
                            padx=10, pady=10)
        self.create_player_section()
        self.create_network_section()
        self.create_controls_section()
        self.refresh_network()

    # ───────────────────────── sidebar ─────────────────────────
    def create_sidebar(self):
        self.sidebar = ctk.CTkFrame(self, width=200, corner_radius=0,
                                    fg_color="#1E1E1E")
        self.sidebar.grid(row=0, column=0, rowspan=4, sticky="nsew")
        self.logo_label = ctk.CTkLabel(
            self.sidebar, text="Spot",
            font=ctk.CTkFont(size=24, weight="bold"), text_color=self.magenta)
        self.logo_label.grid(row=0, column=0, padx=20, pady=(20, 10))
        for i, txt in enumerate(["Início", "Pesquisar", "Peers"], start=1):
            ctk.CTkButton(
                self.sidebar, text=txt, fg_color="transparent", border_width=2,
                border_color=self.magenta,
                font=ctk.CTkFont(size=14, weight="bold")
            ).grid(row=i, column=0, padx=20, pady=10, sticky="ew")

    # ───────────────────── player (capa + slider) ─────────────────────
    def create_player_section(self):
        if os.path.exists(CAPA):
            img = Image.open(CAPA).resize((250, 250), Image.Resampling.LANCZOS)
            self.album_img = ImageTk.PhotoImage(img)
            ctk.CTkLabel(self.main_area, image=self.album_img, text="") \
                .grid(row=0, column=0, padx=50, pady=20)
        self.song_title = ctk.CTkLabel(
            self.main_area, text="Nenhuma música selecionada",
            font=ctk.CTkFont(size=22, weight="bold"))
        self.song_title.grid(row=1, column=0)
        self.progress_slider = ctk.CTkSlider(
            self.main_area, width=400, progress_color=self.magenta,
            button_color=self.magenta)
        self.progress_slider.grid(row=2, column=0, pady=20)
        # lista de arquivos locais/da rede
        self.file_list = Listbox(self.main_area, bg="#1E1E1E", fg="#EEEEEE",
                                 selectbackground="#FF00FF", height=8,
                                 exportselection=False)
        self.file_list.grid(row=3, column=0, padx=50, pady=(0, 10), sticky="ew")
        self.file_list.bind("<<ListboxSelect>>", self._on_select)

    # ───────────────────── rede / downloads ─────────────────────
    def create_network_section(self):
        self.tabview = ctk.CTkTabview(self.main_area, width=350,
                                      fg_color="#1E1E1E")
        self.tabview.grid(row=0, column=1, rowspan=4, padx=20, pady=20,
                          sticky="nsew")
        self.tabview.add("Atividade de Rede")
        self.net_box = ctk.CTkTextbox(self.tabview.tab("Atividade de Rede"),
                                      fg_color="#121212")
        self.net_box.pack(fill="both", expand=True, padx=8, pady=8)
        ctk.CTkButton(self.tabview.tab("Atividade de Rede"),
                      text="⟳ Atualizar", border_width=2,
                      border_color=self.magenta, fg_color="transparent",
                      text_color=self.magenta,
                      command=self.refresh_network).pack(pady=8)
        ctk.CTkButton(self.tabview.tab("Atividade de Rede"),
                      text="⬇ Baixar selecionado", border_width=2,
                      border_color=self.magenta, fg_color="transparent",
                      text_color=self.magenta,
                      command=self.download_selected).pack(pady=4)

    def refresh_network(self):
        self.net_box.delete("1.0", END)
        files = self.client.network_files()
        for peer, fl in files.items():
            self.net_box.insert(END, f"● {peer}\n   {', '.join(fl) or '(vazio)'}\n")
        if not files:
            self.net_box.insert(END, "Nenhum peer online (suba outro com "
                                     "'python -m src.peer --port 5000').\n")
        # repovoa lista local
        self.client.shared_files = self.client.scan_music_folder()
        self.file_list.delete(0, END)
        for f in self.client.shared_files:
            self.file_list.insert(END, f)

    def download_selected(self):
        sel = self.file_list.curselection()
        if not sel:
            self.song_title.configure(text="Selecione um arquivo da rede")
            return
        name = self.file_list.get(sel[0])
        self.song_title.configure(text=f"Baixando {name}...")
        threading.Thread(target=self._do_download, args=(name,),
                         daemon=True).start()

    def _do_download(self, name):
        ok = self.client.download_file(name)
        self.after(0, lambda: (
            self.song_title.configure(text=f"Baixado: {name}" if ok
                                      else f"Falha ao baixar {name}"),
            self.refresh_network()))

    # ───────────────────── controles ─────────────────────
    def create_controls_section(self):
        ctrl = ctk.CTkFrame(self, height=80, fg_color="#000000")
        ctrl.grid(row=3, column=0, columnspan=2, sticky="nsew")
        ctk.CTkButton(ctrl, text="⏮", width=50, fg_color="transparent",
                      border_width=1, border_color=self.magenta,
                      text_color=self.magenta,
                      command=self.prev_song).grid(row=0, column=0, padx=10,
                                                   pady=15)
        self.play_btn = ctk.CTkButton(
            ctrl, text="⏯", width=50, fg_color="transparent", border_width=1,
            border_color=self.magenta, text_color=self.magenta,
            command=self.toggle_play)
        self.play_btn.grid(row=0, column=1, padx=10, pady=15)
        ctk.CTkButton(ctrl, text="⏭", width=50, fg_color="transparent",
                      border_width=1, border_color=self.magenta,
                      text_color=self.magenta,
                      command=self.next_song).grid(row=0, column=2, padx=10,
                                                   pady=15)

    def _on_select(self, _evt=None):
        sel = self.file_list.curselection()
        if sel:
            self.play_file(self.file_list.get(sel[0]))

    def play_file(self, name: str):
        path = os.path.join(self.client.music_dir, name)
        if not os.path.isfile(path):
            self.song_title.configure(text=f"{name} — baixe antes de tocar")
            return
        if not _MIXER_OK:
            self.song_title.configure(text=f"{name} (pygame ausente)")
            return
        pygame.mixer.music.load(path)
        pygame.mixer.music.play()
        self.current_file = name
        self.playing = True
        self.song_title.configure(text=name)

    def toggle_play(self):
        if not _MIXER_OK or not self.current_file:
            return
        if self.playing:
            pygame.mixer.music.pause()
            self.playing = False
        else:
            pygame.mixer.music.unpause()
            self.playing = True

    def _step(self, delta: int):
        files = self.client.shared_files
        if not files:
            return
        try:
            idx = files.index(self.current_file)
        except ValueError:
            idx = 0
        self.play_file(files[(idx + delta) % len(files)])
        # sincroniza seleção
        for i in range(self.file_list.size()):
            if self.file_list.get(i) == self.current_file:
                self.file_list.selection_clear(0, END)
                self.file_list.selection_set(i)
                break

    def prev_song(self):
        self._step(-1)

    def next_song(self):
        self._step(1)


def main():
    NexusStreamPlayer().mainloop()


if __name__ == "__main__":
    main()
