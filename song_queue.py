import pandas as pd
import time
import os
from pathlib import Path

import pandas as pd
import time
import os

class SongQueueManager:
    def __init__(self, excel_file):
        self.df = pd.read_excel(excel_file, engine="openpyxl")
        self.current_index = 0
        self.queue_file = "song_queue.txt"
        self.buffer_size = 5
        
        # Initialize queue file
        with open(self.queue_file, 'w') as f:
            f.write('')
    
    def get_current_queue_size(self):
        """Get number of songs currently in queue"""
        try:
            with open(self.queue_file, 'r') as f:
                return len([line for line in f.readlines() if line.strip()])
        except Exception:
            return 0
    
    def add_song_to_queue(self):
        """Add next song to queue if available"""
        if self.current_index < len(self.df):
            row = self.df.iloc[self.current_index]
            song_info = f"{row['song_name']}|{row['artist']}\n"
            
            with open(self.queue_file, 'a') as f:
                f.write(song_info)
            
            print(f"Added to queue: {row['song_name']} by {row['artist']} ({self.current_index + 1}/{len(self.df)})")
            self.current_index += 1
            return True
        return False
    
    def run(self):
        """Main loop for managing song queue"""
        print(f"Starting to manage queue for {len(self.df)} songs...")
        
        while self.current_index < len(self.df) or self.get_current_queue_size() > 0:
            current_queue_size = self.get_current_queue_size()
            print(f"Current queue size: {current_queue_size}")
            
            # Add songs until buffer is full
            while current_queue_size < self.buffer_size and self.current_index < len(self.df):
                self.add_song_to_queue()
                current_queue_size = self.get_current_queue_size()
            
            time.sleep(1)  # Check every second
        
        print("All songs have been queued and processed!")

if __name__ == "__main__":
    import sys
    if len(sys.argv) != 2:
        print("Usage: python queue_songs.py <excel_file>")
        sys.exit(1)
        
    manager = SongQueueManager(sys.argv[1])
    manager.run()