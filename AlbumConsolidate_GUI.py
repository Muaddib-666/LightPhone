import os
import threading
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import requests
from PIL import Image, ImageTk
from io import BytesIO
import random
from pydub import AudioSegment
from pydub.utils import mediainfo
from mutagen.easyid3 import EasyID3
from mutagen.mp3 import MP3

GAP_DURATION_MS = 1000
BITRATES = ["128k", "192k", "256k", "320k"]

def is_valid_audio_file(file_path):
    try:
        info = mediainfo(file_path)
        return 'duration' in info
    except Exception:
        return False

def safe_audio_segment(file_path):
    try:
        if is_valid_audio_file(file_path):
            return AudioSegment.from_file(file_path)
    except Exception as e:
        print(f"Skipping {file_path}: {e}")
    return None

def extract_sentences(text):
    return [s.strip() + '.' for s in text.replace('\n', ' ').split('.') if len(s.strip()) > 30]


class AlbumConverterApp:
    def __init__(self, master):
        self.master = master
        master.title("Album Combiner")
        self.input_dir = ""
        self.output_dir = ""
        self.to_convert = []
        self.converted = []
        self.cancel_current = False
        self.cancel_all = False
        self.current_thread = None
        self.gap_preferences = {}
        self.checkbox_vars = {}
        self.selected_albums = set()
        self.bitrate = tk.StringVar(value=BITRATES[-1])
        self.save_in_artist_folder = tk.IntVar(value=0)
        self.album_art_label = None
        self.album_fact_label = None
        self.current_album_img = None
        self.current_artist_label = None
        self.current_album_label = None
        self.current_fact_sentences = []
        self.fact_cycle_index = 0
        self.fact_cycle_job = None
        self.fact_cycle_pairs = []
        self.select_all_var = tk.IntVar(value=1)
        self.setup_ui()
        self.master.protocol("WM_DELETE_WINDOW", self.on_close)


    def setup_ui(self):
        dir_frame = tk.Frame(self.master)
        dir_frame.pack(fill=tk.X, padx=10, pady=5)

        # Top bar controls
        tk.Label(dir_frame, text="Input Directory:").grid(row=0, column=0, sticky="e")
        self.input_entry = tk.Entry(dir_frame, width=60)
        self.input_entry.grid(row=0, column=1, padx=5)
        tk.Button(dir_frame, text="Browse", command=self.browse_input).grid(row=0, column=2, padx=(0, 10))

        tk.Label(dir_frame, text="Output Directory:").grid(row=1, column=0, sticky="e")
        self.output_entry = tk.Entry(dir_frame, width=60)
        self.output_entry.grid(row=1, column=1, padx=5)
        tk.Button(dir_frame, text="Browse", command=self.browse_output).grid(row=1, column=2, padx=(0, 10))

        self.save_artist_folder_cb = tk.Checkbutton(
            dir_frame, text="Save albums in artist folders",
            variable=self.save_in_artist_folder)
        self.save_artist_folder_cb.grid(row=1, column=3, padx=10, sticky="w")

        tk.Label(dir_frame, text="MP3 Bitrate:").grid(row=2, column=0, sticky="e")
        self.bitrate_dropdown = ttk.Combobox(dir_frame, textvariable=self.bitrate, values=BITRATES, width=10, state="readonly")
        self.bitrate_dropdown.grid(row=2, column=1, sticky="w")

        # Right-aligned Cancel buttons
        cancel_frame = tk.Frame(dir_frame)
        cancel_frame.grid(row=0, column=10, rowspan=2, sticky="ne", padx=(410,0))
        ttk.Button(cancel_frame, text="Cancel Album", command=self.cancel_album).pack(side=tk.TOP, anchor="e", padx=5, pady=2)
        ttk.Button(cancel_frame, text="Cancel Batch", command=self.cancel_batch).pack(side=tk.TOP, anchor="e", padx=5, pady=2)



        # Main layout frame
        main_frame = tk.Frame(self.master)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # LEFT COLUMN: Converted Albums
        self.left_frame = tk.Frame(main_frame, bg="white", bd=1, relief=tk.SOLID, width=300)
        self.left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=False, padx=5, pady=(40, 5))  # Match pady with right column
        tk.Label(self.left_frame, text="Converted Albums", bg="white", font=("Arial", 12)).pack()
        self.converted_text = tk.Text(self.left_frame, width=40, height=30, wrap=tk.WORD)
        self.converted_text.pack(fill=tk.BOTH, expand=True)

        # RIGHT COLUMN OUTER FRAME
        self.right_outer_frame = tk.Frame(main_frame)
        self.right_outer_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=False, padx=5, pady=(0, 5))  # Match pady with left column

        # Controls above the Albums to Convert box (not inside right_frame)
        right_controls_frame = tk.Frame(self.right_outer_frame, bg="white")
        right_controls_frame.pack(fill=tk.X, pady=(0, 5), anchor="n")

        select_all_cb = tk.Checkbutton(
            right_controls_frame, text="Select/Deselect All Gap Boxes",
            variable=self.select_all_var, command=self.toggle_all_checkboxes)
        select_all_cb.pack(side=tk.LEFT, padx=5, pady=5)

        remove_button = ttk.Button(right_controls_frame, text="Remove Selected", command=self.remove_selected_albums)
        remove_button.pack(side=tk.LEFT, padx=5, pady=5)

        # The Albums to Convert label and box
        self.right_frame = tk.Frame(self.right_outer_frame, bg="white", bd=1, relief=tk.SOLID, width=300)
        self.right_frame.pack(fill=tk.BOTH, expand=True)
        tk.Label(self.right_frame, text="Albums to Convert", bg="white", font=("Arial", 12)).pack(anchor="n", pady=(0, 0))

        header_frame = tk.Frame(self.right_frame, bg="white")
        header_frame.pack(fill=tk.X, padx=5, pady=5)
        tk.Label(header_frame, text="gap", bg="white").grid(row=0, column=0, sticky="w", padx=(2, 10))
        tk.Label(header_frame, text="Artist", bg="white", width=18, anchor="w").grid(row=0, column=1, sticky="w")
        tk.Label(header_frame, text="Album", bg="white", width=18, anchor="w").grid(row=0, column=2, sticky="w")

        self.album_canvas = tk.Canvas(self.right_frame, bg="white")
        self.album_scrollbar = tk.Scrollbar(self.right_frame, orient="vertical", command=self.album_canvas.yview)
        self.album_scroll_frame = tk.Frame(self.album_canvas, bg="white")

        self.album_scroll_frame.bind(
            "<Configure>",
            lambda e: self.album_canvas.configure(scrollregion=self.album_canvas.bbox("all"))
        )

        self.album_canvas.create_window((0, 0), window=self.album_scroll_frame, anchor="nw")
        self.album_canvas.configure(yscrollcommand=self.album_scrollbar.set, bg="white")
        self.album_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.album_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # CENTER COLUMN: Current Album/Controls
        self.center_frame = tk.Frame(main_frame)
        self.center_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10)

        self.status_label = tk.Label(self.center_frame, text="", font=("Arial", 9), wraplength=300, justify="left")
        self.status_label.pack(pady=(0, 0))

        self.progress = ttk.Progressbar(self.center_frame, orient="horizontal", length=300, mode="determinate")
        self.progress.pack(side=tk.TOP, anchor="n", pady=(20, 10))

        self.start_button = ttk.Button(self.center_frame, text="Start Conversion", command=self.start_conversion)
        self.start_button.pack(pady=5)

        self.current_artist_label = tk.Label(
            self.center_frame, text="", font=("Arial", 16, "bold"), wraplength=400, justify="center"
        )
        self.current_artist_label.pack(pady=(0, 0))
        self.current_album_label = tk.Label(
            self.center_frame, text="", font=("Arial", 12), wraplength=400, justify="center"
        )
        self.current_album_label.pack(pady=(0, 10))

        self.album_art_label = tk.Label(self.center_frame)
        self.album_art_label.pack(pady=10)

        self.album_fact_label = tk.Label(self.center_frame, text="", wraplength=400, justify="center", font=("Arial", 8), fg="gray")
        self.album_fact_label.pack(pady=5)

    def show_no_art_placeholder(self):
        from PIL import ImageDraw, ImageFont
        size = 400
        img = Image.new("RGB", (size, size), "#444")
        draw = ImageDraw.Draw(img)

        try:
            font = ImageFont.truetype("arial.ttf", 24)
        except:
            font = ImageFont.load_default()

        text = "No Album Art Found"
        bbox = draw.textbbox((0, 0), text, font=font)
        w = bbox[2] - bbox[0]
        h = bbox[3] - bbox[1]
        draw.text(((size - w) // 2, (size - h) // 2), text, fill="white", font=font)

        tk_img = ImageTk.PhotoImage(img)
        self.album_art_label.config(image=tk_img)
        self.current_album_img = tk_img


    def update_album_lists(self):
        self.converted_text.delete(1.0, tk.END)
        for artist, album, success, duration, size in self.converted:
            status = "✅" if success else "❌"
            size_str = f"{size:.1f} MB" if size else ""
            prefix = f"({duration}) {size_str}" if duration else ""
            entry = f"{prefix} {status}\n{artist}\n{album}\n\n"
            self.converted_text.insert(tk.END, entry)
        for widget in self.album_scroll_frame.winfo_children():
            widget.destroy()
        self.row_widgets = {}
        # Do not reset checkbox_vars here! This preserves their state.
        for idx, (artist, album) in enumerate(self.to_convert):
            key = (artist, album)
            if key not in self.checkbox_vars:
                self.checkbox_vars[key] = tk.IntVar(value=1)
            var = self.checkbox_vars[key]
            row = tk.Frame(self.album_scroll_frame, bg="white")
            row.pack(fill="x", padx=5, pady=2)
            cb = tk.Checkbutton(row, variable=var, bg="white")
            cb.grid(row=0, column=0, sticky="w")
            artist_label = tk.Label(row, text=artist, bg="white", anchor="w", width=18, wraplength=140, justify="left")
            artist_label.grid(row=0, column=1, sticky="w")
            album_label = tk.Label(row, text=album, bg="white", anchor="w", width=18, wraplength=140, justify="left")
            album_label.grid(row=0, column=2, sticky="w")
            def on_row_click(event, key=key, row=row):
                if key in self.selected_albums:
                    self.selected_albums.remove(key)
                    row.config(bg="white")
                    for child in row.winfo_children():
                        child.config(bg="white")
                else:
                    self.selected_albums.add(key)
                    row.config(bg="#cce6ff")
                    for child in row.winfo_children():
                        child.config(bg="#cce6ff")
            row.bind("<Button-1>", on_row_click)
            for child in row.winfo_children():
                child.bind("<Button-1>", on_row_click)
            self.row_widgets[key] = row
            if key in self.selected_albums:
                row.config(bg="#cce6ff")
                for child in row.winfo_children():
                    child.config(bg="#cce6ff")
            else:
                row.config(bg="white")
                for child in row.winfo_children():
                    child.config(bg="white")

    def toggle_all_checkboxes(self):
        value = self.select_all_var.get()
        for var in self.checkbox_vars.values():
            var.set(value)

    def remove_selected_albums(self):
        for key in list(self.selected_albums):
            if key in self.to_convert:
                self.to_convert.remove(key)
            if key in self.checkbox_vars:
                del self.checkbox_vars[key]
            self.selected_albums.remove(key)
        if not self.to_convert:
            self.album_art_label.config(image='')
            self.album_fact_label.config(text="")
            self.current_album_img = None
        self.update_album_lists()

    def browse_input(self):
        path = filedialog.askdirectory()
        if path:
            self.input_entry.delete(0, tk.END)
            self.input_entry.insert(0, path)
            self.load_albums()
            self.start_button.config(state="normal")

    def browse_output(self):
        path = filedialog.askdirectory()
        if path:
            self.output_entry.delete(0, tk.END)
            self.output_entry.insert(0, path)

    def load_albums(self):
        root_dir = self.input_entry.get().strip()
        self.to_convert = []
        if not root_dir or not os.path.isdir(root_dir):
            messagebox.showerror("Error", "Invalid input directory")
            return False

        entries = [e for e in os.listdir(root_dir) if not e.startswith('.')]
        for entry in entries:
            entry_path = os.path.join(root_dir, entry)
            if not os.path.isdir(entry_path):
                continue

            subentries = [s for s in os.listdir(entry_path) if not s.startswith('.')]
            subdirs = [os.path.join(entry_path, s) for s in subentries if os.path.isdir(os.path.join(entry_path, s))]

            if subdirs:
                # Looks like Artist > Album structure
                for album_path in subdirs:
                    album = os.path.basename(album_path)
                    artist = os.path.basename(entry_path)
                    self.to_convert.append((artist, album))
            else:
                # Looks like we opened an Artist folder directly, and these are albums
                artist = os.path.basename(root_dir)
                album = entry
                self.to_convert.append((artist, album))

        self.selected_albums.clear()
        self.update_album_lists()
        self.start_button.config(state="normal")
        return True



    def cancel_album(self):
        self.cancel_current = True

    def cancel_batch(self):
        self.cancel_all = True
        self.cancel_current = True
        self.to_convert.clear()

    def start_conversion(self):
        self.output_dir = self.output_entry.get().strip()
        if not self.output_dir or not os.path.isdir(self.output_dir):
            messagebox.showerror("Error", "Invalid output directory")
            return
        # Respect the actual state of each checkbox
        for key, var in self.checkbox_vars.items():
            self.gap_preferences[key] = var.get() == 1
        self.update_album_lists()
        self.start_button.config(state="disabled")
        self.current_thread = threading.Thread(target=self.run_conversion)
        self.current_thread.start()

    def run_conversion(self):
        while self.to_convert and not self.cancel_all:
            artist, album = self.to_convert.pop(0)
            self.update_album_lists()
            self.display_album_art_and_fact(artist, album)
            self.current_artist_label.config(text=artist)
            self.current_album_label.config(text=album)
            self.convert_album(artist, album)
            self.current_artist_label.config(text="")
            self.current_album_label.config(text="")
            self.status_label.config(text="")
            self.progress.stop()
            if self.fact_cycle_job:
                self.master.after_cancel(self.fact_cycle_job)
                self.fact_cycle_job = None
        self.album_art_label.config(image='')
        self.album_fact_label.config(text="")
        self.current_album_img = None

    def display_album_art_and_fact(self, artist, album):
        self.album_art_label.config(image='')
        self.album_fact_label.config(text="")
        self.current_album_img = None
        self.current_fact_sentences = []
        self.fact_cycle_index = 0
        self.fact_cycle_pairs = []
        if self.fact_cycle_job:
            self.master.after_cancel(self.fact_cycle_job)
            self.fact_cycle_job = None

        art_found = False
        fact_found = False

        def set_album_image(img):
            nonlocal art_found
            if not art_found:
                self.current_album_img = img
                self.album_art_label.config(image=img)
                art_found = True

        def set_album_facts(sentences):
            cleaned = list(dict.fromkeys(sentences))  # remove duplicates
            random.shuffle(cleaned)  # randomize order
            self.current_fact_sentences = cleaned
            self.fact_cycle_index = 0
            self.cycle_album_facts()


        def try_wikipedia_summary(search_term):
            nonlocal art_found, fact_found
            url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{search_term.replace(' ', '_')}"
            response = requests.get(url)
            sentences = []
            if response.status_code == 200:
                data = response.json()
                if 'thumbnail' in data and not art_found:
                    try:
                        img_url = data['thumbnail']['source']
                        headers = {"User-Agent": "AlbumCombiner/1.0 (contact@example.com)"}
                        img_resp = requests.get(img_url, headers=headers)
                        img_resp.raise_for_status()
                        img = Image.open(BytesIO(img_resp.content)).resize((400, 400))
                        tk_img = ImageTk.PhotoImage(img)
                        set_album_image(tk_img)
                    except Exception as e:
                        print(f"Could not load image from {img_url}: {e}")
                if 'extract' in data and not fact_found:
                    all_sentences = [s.strip() for s in data['extract'].replace('\n', ' ').split('.') if len(s.strip()) > 30]
                    sentences = [s + '.' for s in all_sentences]
                    if sentences:
                        set_album_facts(sentences)
                        fact_found = True
                return 'thumbnail' in data or 'extract' in data
            # If not found, do a search
            search_url = f"https://en.wikipedia.org/w/api.php?action=query&list=search&srsearch={requests.utils.quote(search_term)}&format=json"
            search_resp = requests.get(search_url)
            if search_resp.status_code == 200:
                search_data = search_resp.json()
                if search_data.get("query", {}).get("search"):
                    best_title = search_data["query"]["search"][0]["title"]
                    url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{best_title.replace(' ', '_')}"
                    response = requests.get(url)
                    if response.status_code == 200:
                        data = response.json()
                        if 'thumbnail' in data and not art_found:
                            try:
                                img_url = data['thumbnail']['source']
                                headers = {"User-Agent": "AlbumCombiner/1.0 (contact@example.com)"}
                                img_resp = requests.get(img_url, headers=headers)
                                img_resp.raise_for_status()
                                img = Image.open(BytesIO(img_resp.content)).resize((400, 400))
                                tk_img = ImageTk.PhotoImage(img)
                                self.album_art_label.config(image=tk_img)
                                self.current_album_img = tk_img
                                art_found = True
                            except Exception as e:
                                print(f"Could not load image from {img_url}: {e}")
                        if 'extract' in data and not fact_found:
                            all_sentences = [s.strip() for s in data['extract'].replace('\n', ' ').split('.') if len(s.strip()) > 30]
                            sentences = [s + '.' for s in all_sentences]
                            if sentences:
                                set_album_facts(sentences)
                                fact_found = True
                        return 'thumbnail' in data or 'extract' in data
            return False

        def try_wikipedia_band_overview(band):
            nonlocal fact_found
            url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{band.replace(' ', '_')}"
            response = requests.get(url)
            if response.status_code == 200 and not fact_found:
                data = response.json()
                if 'extract' in data:
                    all_sentences = [s.strip() for s in data['extract'].replace('\n', ' ').split('.') if len(s.strip()) > 30]
                    sentences = [s + '.' for s in all_sentences]
                    if sentences:
                        set_album_facts(sentences)
                        fact_found = True
                else:
                    set_album_facts([])
            else:
                set_album_facts([])

        def try_musicbrainz_and_caa(artist, album):
            nonlocal art_found, fact_found
            try:
                query = f'releasegroup:"{album}" AND artist:"{artist}"'
                mb_url = f"https://musicbrainz.org/ws/2/release-group/?query={requests.utils.quote(query)}&fmt=json"
                mb_resp = requests.get(mb_url, headers={"User-Agent": "AlbumCombiner/1.0 (contact@example.com)"})
                if mb_resp.status_code != 200:
                    return False
                mb_data = mb_resp.json()
                if not mb_data.get("release-groups"):
                    return False
                rg = mb_data["release-groups"][0]
                rgid = rg["id"]
                caa_url = f"https://coverartarchive.org/release-group/{rgid}/front-500"
                caa_resp = requests.get(caa_url)
                if caa_resp.status_code == 200 and not art_found:
                    img = Image.open(BytesIO(caa_resp.content)).resize((400, 400))
                    tk_img = ImageTk.PhotoImage(img)
                    set_album_image(tk_img)
                if not fact_found:
                    fact = rg.get("disambiguation") or rg.get("first-release-date", "")
                    if not fact:
                        fact = f"{album} is an album by {artist}."
                    set_album_facts([fact])
                    fact_found = True
                if art_found or fact_found:
                    return True
                else:
                    try_wikipedia_band_overview(artist)
                    return True
            except Exception as e:
                print("MusicBrainz/CoverArtArchive error:", e)
                return False

        all_sentences = []

        # Try Wikipedia: album name
        url_album = f"https://en.wikipedia.org/api/rest_v1/page/summary/{album.replace(' ', '_')}"
        resp_album = requests.get(url_album)
        if resp_album.status_code == 200:
            data = resp_album.json()
            if 'extract' in data:
                all_sentences += extract_sentences(data['extract'])
            if 'thumbnail' in data and not art_found:
                try:
                    img_url = data['thumbnail']['source']
                    headers = {"User-Agent": "AlbumCombiner/1.0 (contact@example.com)"}
                    img_resp = requests.get(img_url, headers=headers)
                    img_resp.raise_for_status()
                    img = Image.open(BytesIO(img_resp.content)).resize((400, 400))
                    tk_img = ImageTk.PhotoImage(img)
                    self.album_art_label.config(image=tk_img)
                    self.current_album_img = tk_img
                    art_found = True
                except Exception as e:
                    print(f"Could not load image from {img_url}: {e}")


        # Try Wikipedia: "Artist Album"
        url_combo = f"https://en.wikipedia.org/api/rest_v1/page/summary/{(artist + ' ' + album).replace(' ', '_')}"
        resp_combo = requests.get(url_combo)
        if resp_combo.status_code == 200:
            data = resp_combo.json()
            if 'extract' in data:
                all_sentences += extract_sentences(data['extract'])

        # Try Wikipedia: artist name
        url_artist = f"https://en.wikipedia.org/api/rest_v1/page/summary/{artist.replace(' ', '_')}"
        resp_artist = requests.get(url_artist)
        if resp_artist.status_code == 200:
            data = resp_artist.json()
            if 'extract' in data:
                all_sentences += extract_sentences(data['extract'])

        if all_sentences:
            set_album_facts(all_sentences)
        else:
            self.album_fact_label.config(text="")
        if not art_found:
            self.show_no_art_placeholder()


    def cycle_album_facts(self):
        if not self.current_fact_sentences:
            self.album_fact_label.config(text="")
            return
        fact = self.current_fact_sentences[self.fact_cycle_index]
        self.album_fact_label.config(text=fact)
        self.fact_cycle_index = (self.fact_cycle_index + 1) % len(self.current_fact_sentences)
        self.fact_cycle_job = self.master.after(8000, self.cycle_album_facts)  # 8 seconds


    def convert_album(self, artist, album):
        root_dir = self.input_entry.get().strip()
        album_path = os.path.join(root_dir, artist, album)
        files = sorted(os.listdir(album_path))
        self.cancel_current = False

        self.status_label.config(text="Processing Audio")

        supported = [f for f in files if is_valid_audio_file(os.path.join(album_path, f))]
        if not supported:
            self.converted.append((artist, album, False, "", None))
            self.update_album_lists()
            return

        self.progress.config(maximum=len(supported), value=0)
        combined = AudioSegment.empty()
        insert_gap = self.gap_preferences.get((artist, album), False)

        for i, filename in enumerate(files):
            path = os.path.join(album_path, filename)
            if not os.path.isfile(path):
                continue
            if not is_valid_audio_file(path):
                continue
            if self.cancel_current:
                self.converted.append((artist, album, False, "", None))
                self.update_album_lists()
                return
            audio = safe_audio_segment(path)
            if audio:
                combined += audio
                if insert_gap:
                    combined += AudioSegment.silent(duration=GAP_DURATION_MS)
            self.progress.config(value=i+1)

        if self.save_in_artist_folder.get():
            artist_folder = os.path.join(self.output_dir, artist)
            os.makedirs(artist_folder, exist_ok=True)
            output_path = os.path.join(artist_folder, f"{album}.mp3")
        else:
            output_path = os.path.join(self.output_dir, f"{artist} - {album}.mp3")

        try:
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            combined.export(output_path, format="mp3", bitrate=self.bitrate.get())
            duration = len(combined)
            minutes = duration // 60000
            seconds = (duration % 60000) // 1000
            duration_str = f"{minutes}:{seconds:02}"
            size_mb = os.path.getsize(output_path) / (1024 * 1024)
            mp3 = MP3(output_path, ID3=EasyID3)
            mp3["artist"] = artist
            mp3["album"] = album
            mp3["title"] = f"{album} (Full Album)"
            mp3.save()
            self.converted.append((artist, album, True, duration_str, size_mb))
        except Exception as e:
            print(f"Export failed: {e}")
            self.converted.append((artist, album, False, "", None))
        self.update_album_lists()
        self.progress.config(value=0)
        self.status_label.config(text="")

    def on_close(self):
        if self.fact_cycle_job:
            self.master.after_cancel(self.fact_cycle_job)
            self.fact_cycle_job = None
        if self.current_thread and self.current_thread.is_alive():
            if messagebox.askyesno("Exit", "Conversion in progress. Cancel and exit?"):
                self.cancel_current = True
                self.cancel_all = True
                self.to_convert.clear()
                self.master.after(1000, self.master.destroy)
            else:
                self.master.destroy()
        else:
            self.master.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = AlbumConverterApp(root)
    root.geometry("1250x850")
    root.mainloop()
