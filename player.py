import os
import time
import pygame
from pathlib import Path

class ChorusPlayer:
    def __init__(self):
        self.play_queue_file = "play_queue.txt"
        self.currently_playing_file = "currently_playing.txt"
        self.cleanup_queue = []
        pygame.mixer.init()

    def try_cleanup_files(self):
        """Attempt to clean up files from the cleanup queue"""
        remaining_files = []
        for file_path in self.cleanup_queue:
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
                    print(f"Cleaned up: {file_path}")
            except Exception as e:
                # If file can't be deleted, keep it in the queue for later
                remaining_files.append(file_path)
        self.cleanup_queue = remaining_files
    
    def get_next_chorus(self):
        """Get and remove first chorus from play queue"""
        try:
            with open(self.play_queue_file, 'r') as f:
                lines = f.readlines()
            
            if not lines:
                return None
            
            # Get first chorus
            first_chorus = lines[0].strip()
            
            # Write remaining choruses back to file
            with open(self.play_queue_file, 'w') as f:
                f.writelines(lines[1:])
            
            return first_chorus if os.path.exists(first_chorus) else None
            
        except Exception as e:
            print(f"Error getting next chorus: {e}")
            return None
    
    def run(self):
        """Main loop for playing choruses"""
        print("Starting chorus player...")
        current_chorus = None
        
        while True:
            try:
                if not pygame.mixer.music.get_busy():
                    if current_chorus:
                        # Clean up previous chorus
                        pygame.mixer.music.stop()
                        pygame.mixer.music.unload()
                        if current_chorus not in self.cleanup_queue:
                            self.cleanup_queue.append(current_chorus)
                        self.try_cleanup_files()
                        current_chorus = None
                    
                    # Get next chorus
                    next_chorus = self.get_next_chorus()
                    if next_chorus:
                        try:
                            print(f"\n► Playing chorus: {Path(next_chorus).stem}")
                            pygame.mixer.music.load(next_chorus)
                            pygame.mixer.music.play()
                            current_chorus = next_chorus
                        except Exception as e:
                            print(f"Error playing chorus: {e}")
                            if next_chorus not in self.cleanup_queue:
                                self.cleanup_queue.append(next_chorus)
                
                time.sleep(0.1)
                
            except KeyboardInterrupt:
                print("\nStopping player...")
                break
            except Exception as e:
                print(f"Error in player loop: {e}")
                time.sleep(1)
        
        # Cleanup
        pygame.mixer.quit()
        
        # Try to clean up all remaining files
        self.cleanup_queue.append(current_chorus)
        for _ in range(3):  # Try cleanup a few times
            self.try_cleanup_files()
            if not self.cleanup_queue:
                break
            time.sleep(1)
        
        # Clear status files
        for file in [self.play_queue_file, self.currently_playing_file]:
            if os.path.exists(file):
                os.remove(file)

if __name__ == "__main__":
    player = ChorusPlayer()
    player.run()