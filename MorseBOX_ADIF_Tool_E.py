import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import requests
import re
from datetime import datetime, timedelta
import os

# ========== HELPER FUNCTIONS ==========

def format_date(value):
    """Formats date as YYYY-MM-DD"""
    digits = re.sub(r'\D', '', value)
    if len(digits) >= 4:
        digits = digits[:4] + '-' + digits[4:]
    if len(digits) >= 7:
        digits = digits[:7] + '-' + digits[7:]
    return digits[:10]

def format_time(value):
    """Formats time as HH:MM"""
    digits = re.sub(r'\D', '', value)
    if len(digits) >= 2:
        digits = digits[:2] + ':' + digits[2:]
    return digits[:5]

def normalize_report(report):
    """Replaces H→5, N→9, cleans unnecessary characters, returns max 3 chars"""
    if not report:
        return ''
    cleaned = re.sub(r'H', '5', re.sub(r'N', '9', report.upper()))
    return cleaned[:3]

def is_valid_callsign(call):
    """Checks if callsign is valid"""
    if re.match(r'^\d+$', call):
        return False
    if not re.search(r'\d', call):
        return False
    if len(call.replace('/', '')) < 3:
        return False
    parts = call.split('/')
    for part in parts:
        if re.match(r'^\d+$', part):
            return False
    return True

def remove_duplicates_within_2_minutes(rows):
    """Removes duplicates of the same station within 2 minutes"""
    seen = {}
    unique = []
    sorted_rows = sorted(rows, key=lambda r: datetime.strptime(f"{r['date']} {r['time']}", "%Y-%m-%d %H:%M"))
    for row in sorted_rows:
        call = row['call']
        current = datetime.strptime(f"{row['date']} {row['time']}", "%Y-%m-%d %H:%M")
        if call in seen:
            last = seen[call]
            if (current - last) > timedelta(minutes=2):
                unique.append(row)
                seen[call] = current
        else:
            unique.append(row)
            seen[call] = current
    return unique

def parse_log_content(content, my_call):
    """Parses log content and returns list of QSOs"""
    lines = content.split('\n')
    rows = []
    call_sign_regex = r'\b([A-Z0-9]{1,3}\/?[A-Z0-9]{1,4}\/?[A-Z0-9]{1,5}(?:\/[A-Z0-9]{1,5})?)\b'
    report_regex = r'\b([1-5H][1-9N][1-9N])\b'
    name_regex = r'\bDR\s+([A-Z]{2,})\b'

    for line in lines:
        date_match = re.search(r'\[(\d{4}-\d{2}-\d{2}) (\d{2}:\d{2}):\d{2}\]', line)
        if not date_match:
            continue
        date, time = date_match.groups()
        potential_calls = re.findall(call_sign_regex, line)
        potential_calls = [c.upper() for c in potential_calls]
        report_matches = re.findall(report_regex, line)
        name_match = re.search(name_regex, line)

        valid_calls = [c for c in potential_calls if is_valid_callsign(c)]
        foreign_call = next((c for c in valid_calls if c != my_call), None)
        report = report_matches[0] if report_matches else ''
        name = name_match.group(1).upper() if name_match else ''

        if foreign_call:
            rows.append({
                'date': date,
                'time': time,
                'call': foreign_call,
                'name': name,
                'report': report
            })
    return remove_duplicates_within_2_minutes(rows)

# ========== MAIN APPLICATION CLASS ==========

class MorseBoxLogViewer:
    def __init__(self, root):
        self.root = root
        self.root.title("MorseBOX_ADIF_Tool - SQ1KSM")
        self.root.geometry("700x700")
        self.root.minsize(700, 700)
        self.root.resizable(True, True)

        self.current_data = []               # list of QSO dictionaries
        self.my_call = tk.StringVar()         # empty at start
        self.server_url = tk.StringVar(value="http://192.168.1.12")
        self.file_list = []                   # list of files from server

        main_frame = ttk.Frame(root, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)

        main_frame.columnconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)

        # ---- Left column: Your data ----
        my_frame = ttk.LabelFrame(main_frame, text="Your data", padding=5)
        my_frame.grid(row=0, column=0, sticky='nsew', padx=(0,5), pady=5)

        ttk.Label(my_frame, text="Your callsign:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)

        self.my_call_entry = ttk.Entry(my_frame, textvariable=self.my_call, width=20)
        self.my_call_entry.grid(row=0, column=1, padx=5, pady=5, sticky=tk.W)
        self.my_call_entry.insert(0, "CALL")
        self.my_call_entry.config(foreground='red')

        def on_focus_in(event):
            if self.my_call.get() == "CALL":
                self.my_call.set("")
            self.my_call_entry.config(foreground='black')
            self.my_call_entry.unbind('<FocusIn>')

        self.my_call_entry.bind('<FocusIn>', on_focus_in)

        # ---- Right column: Band settings ----
        band_frame = ttk.LabelFrame(main_frame, text="Band settings", padding=5)
        band_frame.grid(row=0, column=1, sticky='nsew', padx=(5,0), pady=5)
        ttk.Label(band_frame, text="Band (e.g. 40):").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        self.global_band = tk.StringVar()
        ttk.Entry(band_frame, textvariable=self.global_band, width=10).grid(row=0, column=1, padx=5, pady=5, sticky=tk.W)
        self.fill_band_btn = ttk.Button(band_frame, text="Fill all bands", command=self.fill_all_bands)
        self.fill_band_btn.grid(row=0, column=2, padx=5, pady=5)

        # ---- Log server ----
        server_frame = ttk.LabelFrame(main_frame, text="Log server", padding=5)
        server_frame.grid(row=1, column=0, columnspan=2, sticky='nsew', pady=5)

        server_frame.grid_columnconfigure(0, minsize=100)
        server_frame.grid_columnconfigure(1, weight=1)
        server_frame.grid_columnconfigure(2, minsize=80)

        ttk.Label(server_frame, text="Server address:").grid(row=0, column=0, sticky='e', padx=5, pady=5)
        ttk.Entry(server_frame, textvariable=self.server_url, width=30).grid(row=0, column=1, padx=5, pady=5, sticky='ew')
        self.fetch_btn = ttk.Button(server_frame, text="Fetch list", command=self.fetch_file_list)
        self.fetch_btn.grid(row=0, column=2, padx=5, pady=5)

        ttk.Label(server_frame, text="Select file:").grid(row=1, column=0, sticky='e', padx=5, pady=5)
        self.file_combo = ttk.Combobox(server_frame, state="readonly", width=30)
        self.file_combo.grid(row=1, column=1, padx=5, pady=5, sticky='ew')
        self.file_combo.bind('<<ComboboxSelected>>', self.load_selected_file)

        self.download_btn = ttk.Button(server_frame, text="Download", command=self.download_selected_file, state=tk.DISABLED)
        self.download_btn.grid(row=1, column=2, padx=5, pady=5)

        ttk.Label(server_frame, text="Local file:").grid(row=2, column=0, sticky='e', padx=5, pady=5)
        self.local_file_path = tk.StringVar()
        local_file_entry = ttk.Entry(server_frame, textvariable=self.local_file_path, width=30, state='readonly')
        local_file_entry.grid(row=2, column=1, padx=5, pady=5, sticky='ew')
        self.local_file_btn = ttk.Button(server_frame, text="Browse", command=self.choose_local_file)
        self.local_file_btn.grid(row=2, column=2, padx=5, pady=5)

        # ---- QSO table ----
        table_frame = ttk.LabelFrame(main_frame, text="QSO list", padding=5)
        table_frame.grid(row=2, column=0, columnspan=2, sticky='nsew', pady=5)
        main_frame.rowconfigure(2, weight=1)

        tree_frame = ttk.Frame(table_frame)
        tree_frame.pack(fill=tk.BOTH, expand=True)

        vsb = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)

        self.tree = ttk.Treeview(tree_frame,
            columns=('date', 'time', 'call', 'name', 'report_sent', 'report_rcvd', 'band', 'select'),
            show='tree headings',
            yscrollcommand=vsb.set,
            height=15)
        vsb.config(command=self.tree.yview)

        self.tree.heading('#0', text='Lp')
        self.tree.heading('date', text='DATE')
        self.tree.heading('time', text='TIME')
        self.tree.heading('call', text='CALL')
        self.tree.heading('name', text='NAME')
        self.tree.heading('report_sent', text='RST TX')
        self.tree.heading('report_rcvd', text='RST RX')
        self.tree.heading('band', text='BAND')
        self.tree.heading('select', text='✓')

        self.tree.column('#0', width=40, anchor=tk.CENTER)
        self.tree.column('date', width=90, anchor=tk.CENTER)
        self.tree.column('time', width=60, anchor=tk.CENTER)
        self.tree.column('call', width=120)
        self.tree.column('name', width=100)
        self.tree.column('report_sent', width=60, anchor=tk.CENTER)
        self.tree.column('report_rcvd', width=60, anchor=tk.CENTER)
        self.tree.column('band', width=60, anchor=tk.CENTER)
        self.tree.column('select', width=30, anchor=tk.CENTER)

        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.tree.tag_configure('checked', foreground='red')
        self.tree.bind('<Button-1>', self.on_tree_click)
        self.tree.bind('<Double-1>', self.on_double_click)

        # ---- Buttons with author label on the right ----
        btn_frame = ttk.Frame(main_frame)
        btn_frame.grid(row=3, column=0, columnspan=2, pady=5, sticky='ew')
        btn_frame.columnconfigure(0, weight=1)
        btn_frame.columnconfigure(1, weight=0)

        left_frame = ttk.Frame(btn_frame)
        left_frame.grid(row=0, column=0, sticky='w')
        right_frame = ttk.Frame(btn_frame)
        right_frame.grid(row=0, column=1, sticky='e')

        self.add_row_btn = tk.Button(left_frame, text="Add empty row", command=self.add_empty_row, fg="green")
        self.add_row_btn.pack(side=tk.LEFT, padx=5)

        self.delete_btn = tk.Button(left_frame, text="Delete selected", command=self.delete_selected, fg="red")
        self.delete_btn.pack(side=tk.LEFT, padx=5)

        self.export_btn = ttk.Button(left_frame, text="Export ADIF", command=self.export_adif)
        self.export_btn.pack(side=tk.LEFT, padx=5)

        self.help_btn = ttk.Button(left_frame, text="Help", command=self.show_help)
        self.help_btn.pack(side=tk.LEFT, padx=5)

        author_label = tk.Label(right_frame, text="Program written by SQ1KSM", fg="green", font=("Arial", 10, "italic"))
        author_label.pack(side=tk.RIGHT, padx=10)

        # ---- Status ----
        self.status = tk.StringVar(value="Ready.")
        status_bar = ttk.Label(root, textvariable=self.status, relief=tk.SUNKEN, anchor=tk.W)
        status_bar.pack(side=tk.BOTTOM, fill=tk.X)

    # ========== METHODS ==========

    def show_help(self):
        help_window = tk.Toplevel(self.root)
        help_window.title("Help - MorseBOX_ADIF_Tool")
        help_window.geometry("450x270")
        help_window.resizable(False, False)

        text = tk.Text(help_window, wrap=tk.WORD, font=("Arial", 10), padx=10, pady=10)
        text.pack(fill=tk.BOTH, expand=True)

        help_content = """HELP:
1. Enter your callsign in the "Your callsign" field.
2. Provide the server address (e.g. http://192.168.1.12), click "Fetch list", select a file from the list – it loads automatically (the address will appear in MorseBOX "FILEMNG").
3. Local file – click "Browse" next to "Local file".
4. Edit data: double-click a cell.
5. Select rows: click the ☐ symbol in the ✓ column.
6. Buttons:
   - "Add empty row" (green) – adds a new row.
   - "Delete selected" (red) – deletes selected rows.
   - "Export ADIF" – saves data to .adi file.
   - "Fill all bands" – sets the given band in all rows.
7. The status bar at the bottom shows progress and errors."""

        text.insert(tk.END, help_content)
        text.config(state=tk.DISABLED)

        close_btn = ttk.Button(help_window, text="Close", command=help_window.destroy)
        close_btn.pack(pady=5)

    def fetch_file_list(self):
        url = self.server_url.get().strip()
        if not url:
            messagebox.showerror("Error", "Please provide server address")
            return
        if not url.startswith(('http://', 'https://')):
            url = 'http://' + url
        url = url.rstrip('/')
        logs_url = url + '/logs'

        self.status.set("Connecting to server...")
        self.root.update()

        try:
            resp = requests.get(logs_url, timeout=5)
            resp.raise_for_status()
            data = resp.json()
            if not isinstance(data, list):
                self.status.set("Server response is not a list.")
                return
            self.file_list = sorted(data)
            self.file_combo['values'] = self.file_list
            if self.file_list:
                self.file_combo.current(0)
                self.download_btn.config(state=tk.NORMAL)
                self.load_selected_file()
            else:
                self.file_combo.set('')
                self.download_btn.config(state=tk.DISABLED)
            self.status.set(f"Found {len(self.file_list)} files.")
        except requests.exceptions.RequestException as e:
            self.status.set(f"Connection error: {e}")
            messagebox.showerror("Error", f"Cannot fetch file list:\n{e}")

    def load_selected_file(self, event=None):
        filename = self.file_combo.get()
        if not filename:
            return

        base_url = self.server_url.get().strip()
        if not base_url.startswith(('http://', 'https://')):
            base_url = 'http://' + base_url
        base_url = base_url.rstrip('/')
        download_url = f"{base_url}/download?path=/logs/{filename}"

        self.status.set(f"Downloading file {filename}...")
        self.root.update()

        try:
            resp = requests.get(download_url, timeout=10)
            resp.raise_for_status()
            content = resp.text

            my_call = self.my_call.get().strip().upper()
            if not my_call or my_call == "CALL":
                messagebox.showerror("Error", "Please provide your callsign.")
                return

            parsed = parse_log_content(content, my_call)

            for qso in parsed:
                qso['report'] = normalize_report(qso.get('report', ''))
                qso['checked'] = False

            self.current_data = parsed
            self.refresh_table()
            self.status.set(f"Loaded {len(parsed)} QSOs from file {filename}.")
        except Exception as e:
            self.status.set(f"Error loading file: {e}")
            messagebox.showerror("Error", f"Cannot download/process file:\n{e}")

    def download_selected_file(self):
        filename = self.file_combo.get()
        if not filename:
            return

        base_url = self.server_url.get().strip()
        if not base_url.startswith(('http://', 'https://')):
            base_url = 'http://' + base_url
        base_url = base_url.rstrip('/')
        download_url = f"{base_url}/download?path=/logs/{filename}"

        self.status.set(f"Downloading file {filename}...")
        self.root.update()

        try:
            resp = requests.get(download_url, timeout=10)
            resp.raise_for_status()

            file_path = filedialog.asksaveasfilename(
                initialfile=filename,
                defaultextension=".txt",
                filetypes=[("Text files", "*.txt *.log"), ("All files", "*.*")]
            )
            if not file_path:
                self.status.set("Download cancelled.")
                return

            with open(file_path, 'wb') as f:
                f.write(resp.content)

            self.status.set(f"File {filename} saved.")
        except Exception as e:
            self.status.set(f"Download error: {e}")
            messagebox.showerror("Error", f"Cannot download file:\n{e}")

    def choose_local_file(self):
        filename = filedialog.askopenfilename(
            title="Select log file",
            filetypes=[("Text files", "*.txt *.log"), ("All files", "*.*")]
        )
        if filename:
            self.local_file_path.set(os.path.basename(filename))
            self.load_local_file(filename)

    def load_local_file(self, filepath):
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
        except Exception as e:
            messagebox.showerror("Error", f"Cannot read file:\n{e}")
            return

        my_call = self.my_call.get().strip().upper()
        if not my_call or my_call == "CALL":
            messagebox.showerror("Error", "Please provide your callsign.")
            return

        parsed = parse_log_content(content, my_call)
        for qso in parsed:
            qso['report'] = normalize_report(qso.get('report', ''))
            qso['checked'] = False
        self.current_data = parsed
        self.refresh_table()
        self.status.set(f"Loaded {len(parsed)} QSOs from file {os.path.basename(filepath)}.")

    def refresh_table(self):
        for row in self.tree.get_children():
            self.tree.delete(row)

        for i, qso in enumerate(self.current_data, start=1):
            checked = qso.get('checked', False)
            checkbox_symbol = '☑' if checked else '☐'
            values = (
                qso.get('date', ''),
                qso.get('time', ''),
                qso.get('call', ''),
                qso.get('name', ''),
                qso.get('report_sent', qso.get('report', '')),
                qso.get('report_rcvd', qso.get('report', '')),
                qso.get('band', ''),
                checkbox_symbol
            )
            item = self.tree.insert('', tk.END, text=str(i), values=values, tags=('qso',))
            if checked:
                self.tree.item(item, tags=('qso', 'checked'))

    def on_tree_click(self, event):
        region = self.tree.identify_region(event.x, event.y)
        if region != "cell":
            return
        column = self.tree.identify_column(event.x)
        if column != '#8':
            return
        item = self.tree.identify_row(event.y)
        if not item:
            return

        idx = int(self.tree.item(item, 'text')) - 1
        if 0 <= idx < len(self.current_data):
            self.current_data[idx]['checked'] = not self.current_data[idx].get('checked', False)
            self.refresh_table()

    def add_empty_row(self):
        empty = {
            'date': '',
            'time': '',
            'call': '',
            'name': '',
            'report_sent': '',
            'report_rcvd': '',
            'band': '',
            'checked': False
        }
        self.current_data.append(empty)
        self.refresh_table()
        self.status.set("Empty row added.")

    def delete_selected(self):
        to_delete = [i for i, qso in enumerate(self.current_data) if qso.get('checked', False)]
        if not to_delete:
            messagebox.showinfo("Info", "Select rows by clicking the ☐ symbol in the '✓' column.")
            return
        for i in sorted(to_delete, reverse=True):
            del self.current_data[i]
        self.refresh_table()
        self.status.set(f"Deleted {len(to_delete)} rows.")

    def fill_all_bands(self):
        band = self.global_band.get().strip().upper()
        if not band:
            messagebox.showwarning("Warning", "Please enter a band first.")
            return
        for qso in self.current_data:
            qso['band'] = band
        self.refresh_table()
        self.status.set(f"Band '{band}' filled in all rows.")

    def on_double_click(self, event):
        region = self.tree.identify_region(event.x, event.y)
        if region != "cell":
            return
        column = self.tree.identify_column(event.x)
        if column == '#0' or column == '#8':
            return
        item = self.tree.identify_row(event.y)
        if not item:
            return

        col_name = self.tree.column(column, 'id')
        x, y, width, height = self.tree.bbox(item, column)
        value = self.tree.set(item, col_name)

        entry = tk.Entry(self.tree, borderwidth=0, highlightthickness=1)
        entry.place(x=x, y=y, width=width, height=height)
        entry.insert(0, value)
        entry.focus_set()

        def save_edit(event=None):
            new_value = entry.get()
            if col_name == 'date':
                new_value = format_date(new_value)
            elif col_name == 'time':
                new_value = format_time(new_value)
                if not re.match(r'^([0-1][0-9]|2[0-3]):[0-5][0-9]$', new_value):
                    new_value = ''
            elif col_name in ('report_sent', 'report_rcvd'):
                new_value = normalize_report(new_value)[:3]
            entry.destroy()
            self.tree.set(item, col_name, new_value)

            idx = int(self.tree.item(item, 'text')) - 1
            if 0 <= idx < len(self.current_data):
                key_map = {
                    'date': 'date',
                    'time': 'time',
                    'call': 'call',
                    'name': 'name',
                    'report_sent': 'report_sent',
                    'report_rcvd': 'report_rcvd',
                    'band': 'band'
                }
                if col_name in key_map:
                    self.current_data[idx][key_map[col_name]] = new_value
            self.status.set("Updated.")

        entry.bind('<Return>', save_edit)
        entry.bind('<FocusOut>', save_edit)

    def export_adif(self):
        if not self.current_data:
            messagebox.showinfo("Info", "No data to export.")
            return

        operator = self.my_call.get().strip().upper()
        if not operator or operator == "CALL":
            messagebox.showerror("Error", "Please provide your callsign.")
            return

        crlf = '\r\n'
        adif = f"""ADIF Export from MorseBOX v3{crlf}<ADIF_VER:5>3.1.4{crlf}<PROGRAMID:10>MorseBOX{crlf}<PROGRAMVERSION:3>7.02{crlf}<EOH>{crlf}{crlf}"""

        count = 0
        for qso in self.current_data:
            date = qso.get('date', '').replace('-', '')
            time = qso.get('time', '').replace(':', '')[:4]
            call = qso.get('call', '').strip()
            name = qso.get('name', '').strip()
            report_sent = normalize_report(qso.get('report_sent', qso.get('report', '')))
            report_rcvd = normalize_report(qso.get('report_rcvd', qso.get('report', '')))
            band_raw = qso.get('band', '').strip()
            band = band_raw.upper() + 'M' if band_raw else ''

            if not call or not date or not time:
                continue

            adif += f"<OPERATOR:{len(operator)}>{operator} <CALL:{len(call)}>{call} <QSO_DATE:8>{date} <TIME_ON:4>{time} <MODE:2>CW "
            adif += f"<RST_SENT:{len(report_sent)}>{report_sent} <RST_RCVD:{len(report_rcvd)}>{report_rcvd}"
            if name:
                adif += f" <NAME:{len(name)}>{name}"
            if band:
                adif += f" <BAND:{len(band)}>{band}"
            adif += f" <EOR>{crlf}"
            count += 1

        if count == 0:
            messagebox.showwarning("Warning", "No complete record was exported.")
            return

        file_path = filedialog.asksaveasfilename(
            defaultextension=".adi",
            filetypes=[("ADIF files", "*.adi"), ("All files", "*.*")],
            title="Save ADIF file"
        )
        if not file_path:
            return

        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(adif)
            self.status.set(f"Export finished. Saved {count} QSOs.")
        except Exception as e:
            self.status.set(f"File write error: {e}")
            messagebox.showerror("Error", f"Cannot save file:\n{e}")

if __name__ == "__main__":
    root = tk.Tk()
    app = MorseBoxLogViewer(root)
    root.mainloop()