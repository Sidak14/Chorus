# song_queue.py
import pandas as pd
import time
import os
import tkinter as tk
from tkinter import ttk
from tkinter import filedialog
import threading
from song_queue import SongQueueManager

class SongQueueUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Song Queue Manager")
        self.root.geometry("800x600")
        
        # Initialize manager as None (will be set when file is loaded)
        self.queue_manager = None
        self.is_running = False
        
        # Create main frame
        self.main_frame = ttk.Frame(self.root, padding="10")
        self.main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Status label
        self.status_label = ttk.Label(self.main_frame, text="No file loaded")
        self.status_label.grid(row=0, column=0, columnspan=2, sticky=tk.W, pady=(0, 10))
        
        # Create queue display
        self.create_queue_display()
        
        # Create controls
        self.create_controls()
        
        # Configure grid weights
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        self.main_frame.columnconfigure(0, weight=1)
        self.main_frame.rowconfigure(1, weight=1)
    
    def create_queue_display(self):
        """Create the queue display area"""
        # Frame for unprocessed songs
        queue_frame = ttk.LabelFrame(self.main_frame, text="Unprocessed Songs", padding="5")
        queue_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=(0, 5))
        
        # Treeview for unprocessed songs
        self.queue_tree = ttk.Treeview(queue_frame, columns=('Index', 'Song', 'Artist'), show='headings')
        self.queue_tree.heading('Index', text='#')
        self.queue_tree.heading('Song', text='Song')
        self.queue_tree.heading('Artist', text='Artist')
        
        self.queue_tree.column('Index', width=50)
        self.queue_tree.column('Song', width=200)
        self.queue_tree.column('Artist', width=150)
        
        # Scrollbar for treeview
        scrollbar = ttk.Scrollbar(queue_frame, orient=tk.VERTICAL, command=self.queue_tree.yview)
        self.queue_tree.configure(yscrollcommand=scrollbar.set)
        
        # Pack the treeview and scrollbar
        self.queue_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Bind up/down buttons to move items
        self.queue_tree.bind('<Key-Up>', lambda e: self.move_item_up())
        self.queue_tree.bind('<Key-Down>', lambda e: self.move_item_down())
    
    def create_controls(self):
        """Create control buttons"""
        control_frame = ttk.Frame(self.main_frame)
        control_frame.grid(row=2, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(5, 0))
        
        # Load file button
        self.load_btn = ttk.Button(control_frame, text="Load Excel File", command=self.load_file)
        self.load_btn.pack(side=tk.LEFT, padx=5)
        
        # Start/Stop button
        self.start_btn = ttk.Button(control_frame, text="Start Processing", command=self.toggle_processing)
        self.start_btn.pack(side=tk.LEFT, padx=5)
        self.start_btn.state(['disabled'])
        
        # Move buttons
        self.move_up_btn = ttk.Button(control_frame, text="Move Up", command=self.move_item_up)
        self.move_up_btn.pack(side=tk.LEFT, padx=5)
        
        self.move_down_btn = ttk.Button(control_frame, text="Move Down", command=self.move_item_down)
        self.move_down_btn.pack(side=tk.LEFT, padx=5)
    
    def load_file(self):
        """Load Excel file and initialize queue manager"""
        file_path = filedialog.askopenfilename(
            filetypes=[("Excel files", "*.xlsx"), ("All files", "*.*")]
        )
        
        if file_path:
            try:
                self.queue_manager = SongQueueManager(file_path)
                self.status_label.config(text=f"Loaded: {os.path.basename(file_path)}")
                self.start_btn.state(['!disabled'])
                self.update_queue_display()
            except Exception as e:
                self.status_label.config(text=f"Error loading file: {e}")
    
    def update_queue_display(self):
        """Update the queue display with current songs"""
        # Clear current display
        for item in self.queue_tree.get_children():
            self.queue_tree.delete(item)
        
        if self.queue_manager:
            # Add all unprocessed songs
            for idx, (_, row) in enumerate(self.queue_manager.df.iloc[self.queue_manager.current_index:].iterrows()):
                self.queue_tree.insert('', 'end', values=(idx + 1, row['song_name'], row['artist']))
    
    def move_item_up(self):
        """Move selected item up in the queue"""
        selected = self.queue_tree.selection()
        if not selected:
            return
            
        item = selected[0]
        idx = self.queue_tree.index(item)
        if idx > 0:
            # Get current values
            current_values = self.queue_tree.item(item)['values']
            prev_item = self.queue_tree.prev(item)
            prev_values = self.queue_tree.item(prev_item)['values']
            
            # Swap values in treeview
            self.queue_tree.item(item, values=(idx, *current_values[1:]))
            self.queue_tree.item(prev_item, values=(idx + 1, *prev_values[1:]))
            
            # Swap in DataFrame
            real_idx = self.queue_manager.current_index + idx
            self.queue_manager.df.iloc[real_idx-1:real_idx+1] = self.queue_manager.df.iloc[real_idx-1:real_idx+1].iloc[::-1].values
            
            # Move selection
            self.queue_tree.selection_set(prev_item)
            self.queue_tree.see(prev_item)
    
    def move_item_down(self):
        """Move selected item down in the queue"""
        selected = self.queue_tree.selection()
        if not selected:
            return
            
        item = selected[0]
        idx = self.queue_tree.index(item)
        if idx < len(self.queue_tree.get_children()) - 1:
            # Get current values
            current_values = self.queue_tree.item(item)['values']
            next_item = self.queue_tree.next(item)
            next_values = self.queue_tree.item(next_item)['values']
            
            # Swap values in treeview
            self.queue_tree.item(item, values=(idx + 2, *current_values[1:]))
            self.queue_tree.item(next_item, values=(idx + 1, *next_values[1:]))
            
            # Swap in DataFrame
            real_idx = self.queue_manager.current_index + idx
            self.queue_manager.df.iloc[real_idx:real_idx+2] = self.queue_manager.df.iloc[real_idx:real_idx+2].iloc[::-1].values
            
            # Move selection
            self.queue_tree.selection_set(next_item)
            self.queue_tree.see(next_item)
    
    def toggle_processing(self):
        """Start or stop the processing"""
        if not self.is_running:
            self.is_running = True
            self.start_btn.config(text="Stop Processing")
            self.load_btn.state(['disabled'])
            
            # Start queue manager in a separate thread
            self.queue_thread = threading.Thread(target=self.run_queue_manager)
            self.queue_thread.daemon = True
            self.queue_thread.start()
            
            # Start update thread
            self.update_thread = threading.Thread(target=self.update_loop)
            self.update_thread.daemon = True
            self.update_thread.start()
        else:
            self.is_running = False
            self.start_btn.config(text="Start Processing")
            self.load_btn.state(['!disabled'])
    
    def run_queue_manager(self):
        """Run the queue manager"""
        self.queue_manager.run()
    
    def update_loop(self):
        """Periodically update the display"""
        while self.is_running:
            self.root.after(1000, self.update_queue_display)
            time.sleep(1)

def main():
    root = tk.Tk()
    app = SongQueueUI(root)
    root.mainloop()

if __name__ == "__main__":
    main()