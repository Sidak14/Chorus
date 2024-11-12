from spotdl import Spotdl
from pydub import AudioSegment
import librosa
import numpy as np
import os
import time
import pygame

class SongProcessor:
    def __init__(self):
        self.spot = Spotdl(
            client_id="1e7160661b5849e7a50f41de5b8f9ef1",
            client_secret="6c04a0251cda402688b667a8a4df52ec"
        )
        self.queue_file = "song_queue.txt"
        self.play_queue_file = "play_queue.txt"
    
    def download_song(self, song_name, artist):
        try:
            search_query = f"{song_name} {artist}"
            print(f"Searching for: {search_query}")
            
            songs = self.spot.search([search_query])
            if not songs:
                print(f"Could not find {search_query}")
                return None, None
            
            song = songs[0]
            path = self.spot.download(song)[1]
            print(f"Downloaded to: {path}")
            return path, song.name
            
        except Exception as e:
            print(f"Error downloading {song_name}: {e}")
            return None, None
    
    def detect_chorus(self, audio_segment):
        try:
            samples = np.array(audio_segment.get_array_of_samples())
            
            if audio_segment.channels == 2:
                samples = samples.reshape((-1, 2)).mean(axis=1)
            
            samples = samples.astype(float) / np.max(np.abs(samples))
            
            onset_env = librosa.onset.onset_strength(
                y=samples, 
                sr=audio_segment.frame_rate,
                aggregate=np.median
            )
            
            peaks = librosa.util.peak_pick(
                onset_env,
                pre_max=30,
                post_max=30,
                pre_avg=30,
                post_avg=30,
                delta=0.2,
                wait=30
            )
            
            peak_times = librosa.frames_to_time(peaks, sr=audio_segment.frame_rate) * 1000
            
            if len(peak_times) > 0:
                song_length = len(audio_segment)
                target_position = song_length * 0.3
                estimated_chorus = peak_times[
                    np.argmin(np.abs(peak_times - target_position))
                ]
                print(f"Detected chorus at: {estimated_chorus/1000:.2f} seconds")
                return estimated_chorus
            else:
                default_position = len(audio_segment) * 0.3
                print(f"No peaks found, using default position: {default_position/1000:.2f} seconds")
                return default_position
            
        except Exception as e:
            print(f"Error in chorus detection: {e}")
            return None
    
    def extract_chorus(self, audio_segment, chorus_start_ms, duration_ms=60000, pre_chorus_duration=20000):
        try:
            post_chorus_duration = duration_ms - pre_chorus_duration
            start_ms = max(0, int(chorus_start_ms - pre_chorus_duration))
            end_ms = min(int(chorus_start_ms + post_chorus_duration), len(audio_segment))
            
            print(f"Extracting extended chorus section:")
            print(f"  Full song length: {len(audio_segment)/1000:.2f}s")
            print(f"  Chorus detected at: {chorus_start_ms/1000:.2f}s")
            print(f"  Extract from: {start_ms/1000:.2f}s to {end_ms/1000:.2f}s")
            print(f"  Extract duration: {(end_ms-start_ms)/1000:.2f}s")
            
            chorus = audio_segment[start_ms:end_ms]
            chorus = chorus.fade_in(500).fade_out(500)
            chorus = chorus.normalize()
            
            return chorus
        except Exception as e:
            print(f"Error extracting chorus: {e}")
            return None
    
    def process_song(self, song_name, artist):
        try:
            song_path, song_title = self.download_song(song_name, artist)
            if not song_path:
                return None

            audio = AudioSegment.from_mp3(song_path)
            chorus_start = self.detect_chorus(audio)
            
            if chorus_start is not None:
                chorus = self.extract_chorus(audio, chorus_start)
                
                if chorus is not None:
                    safe_title = "".join(c for c in song_title if c.isalnum() or c in (' ', '-', '_')).rstrip()
                    chorus_path = f"chorus_{safe_title}.wav"
                    
                    chorus.export(chorus_path, format='wav')
                    print(f"✓ Saved chorus from {song_title}")
                    
                    # Clean up downloaded song
                    os.remove(song_path)
                    return chorus_path
            
            if os.path.exists(song_path):
                os.remove(song_path)
            return None
            
        except Exception as e:
            print(f"Error processing {song_name}: {e}")
            if 'song_path' in locals() and os.path.exists(song_path):
                os.remove(song_path)
            return None

    def get_next_song(self):
        """Get and remove the first song from the queue"""
        try:
            with open(self.queue_file, 'r') as f:
                lines = f.readlines()
            
            if not lines:
                return None, None
            
            # Get first song
            first_song = lines[0].strip()
            song_name, artist = first_song.split('|')
            
            # Write remaining songs back to file
            with open(self.queue_file, 'w') as f:
                f.writelines(lines[1:])
            
            return song_name, artist
            
        except Exception as e:
            print(f"Error getting next song: {e}")
            return None, None

    def add_to_play_queue(self, chorus_path):
        """Add processed chorus to play queue"""
        try:
            with open(self.play_queue_file, 'a') as f:
                f.write(f"{chorus_path}\n")
            print(f"Added to play queue: {chorus_path}")
        except Exception as e:
            print(f"Error adding to play queue: {e}")

    def run(self):
        """Main loop for processing songs"""
        print("Starting song processor...")
        
        while True:
            try:
                # Get next song from queue
                song_name, artist = self.get_next_song()
                
                if song_name and artist:
                    print(f"\nProcessing: {song_name} by {artist}")
                    chorus_path = self.process_song(song_name, artist)
                    
                    if chorus_path:
                        self.add_to_play_queue(chorus_path)
                    else:
                        print(f"Failed to process song: {song_name}")
                
                time.sleep(0.1)  # Small delay
                
            except KeyboardInterrupt:
                print("\nStopping processor...")
                break
            except Exception as e:
                print(f"Error in processor loop: {e}")
                time.sleep(1)


if __name__ == "__main__":
    processor = SongProcessor()
    processor.run()