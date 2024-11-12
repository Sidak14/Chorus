import pandas as pd
from spotdl import Spotdl
from pydub import AudioSegment
import librosa
import numpy as np
import os
import threading
import queue
import pygame
import time
from collections import deque

class ConcurrentSongProcessor:
    def __init__(self):
        self.spot = Spotdl(
            client_id="1e7160661b5849e7a50f41de5b8f9ef1",
            client_secret="6c04a0251cda402688b667a8a4df52ec"
        )
        self.chorus_queue = queue.Queue()  # Queue for processed chorus files
        self.download_queue = queue.Queue()  # Queue for songs to be downloaded
        self.processed_files = deque()  # Keep track of processed files for cleanup
        self.is_running = True
        self.current_playing = None
        
        # Initialize pygame mixer
        pygame.mixer.init()
        
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
            
            mel_spec = librosa.feature.melspectrogram(
                y=samples,
                sr=audio_segment.frame_rate,
                n_mels=128,
                fmax=8000
            )
            
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
        """Process a single song and add its chorus to the queue"""
        try:
            song_path, song_title = self.download_song(song_name, artist)
            if not song_path:
                return

            audio = AudioSegment.from_mp3(song_path)
            chorus_start = self.detect_chorus(audio)
            
            if chorus_start is not None:
                chorus = self.extract_chorus(audio, chorus_start)
                
                if chorus is not None:
                    # Create chorus filename using song title
                    safe_title = "".join(c for c in song_title if c.isalnum() or c in (' ', '-', '_')).rstrip()
                    chorus_path = f"chorus_{safe_title}.wav"
                    
                    # Save chorus to current working directory
                    chorus.export(chorus_path, format='wav')
                    
                    # Add to queue and tracking
                    self.chorus_queue.put(chorus_path)
                    self.processed_files.append(chorus_path)
                    print(f"✓ Added chorus from {song_title} to queue")
            
            # Clean up downloaded song
            os.remove(song_path)
            return True
            
        except Exception as e:
            print(f"Error processing {song_name}: {e}")
            if 'song_path' in locals() and os.path.exists(song_path):
                os.remove(song_path)
            return False

    def download_thread(self):
        """Thread for downloading and processing songs"""
        while self.is_running:
            try:
                song_info = self.download_queue.get(timeout=1)  # 1 second timeout
                if song_info is None:  # Sentinel value
                    break
                    
                song_name, artist = song_info
                self.process_song(song_name, artist)
                self.download_queue.task_done()
                
            except queue.Empty:
                continue
            except Exception as e:
                print(f"Error in download thread: {e}")
                continue

    def playback_thread(self):
        """Thread for playing processed chorus files"""
        while self.is_running:
            try:
                if not pygame.mixer.music.get_busy():
                    if self.current_playing:
                        # Clean up previous file if it exists
                        try:
                            os.remove(self.current_playing)
                            self.processed_files.popleft()
                        except:
                            pass
                    
                    # Get next chorus file
                    next_chorus = self.chorus_queue.get(timeout=1)
                    self.current_playing = next_chorus
                    
                    # Play the chorus
                    pygame.mixer.music.load(next_chorus)
                    pygame.mixer.music.play()
                    print(f"► Playing chorus from: {next_chorus}")
                    
                time.sleep(0.1)  # Small delay to prevent busy waiting
                
            except queue.Empty:
                if self.download_queue.empty() and self.chorus_queue.empty():
                    print("No more songs to play")
                    break
                continue
            except Exception as e:
                print(f"Error in playback thread: {e}")
                continue

    def cleanup(self):
        """Clean up any remaining temporary files"""
        self.is_running = False
        pygame.mixer.quit()
        
        for file_path in self.processed_files:
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
                    print(f"Cleaned up: {file_path}")
            except Exception as e:
                print(f"Error cleaning up {file_path}: {e}")