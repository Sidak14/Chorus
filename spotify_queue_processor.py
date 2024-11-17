import spotipy
from spotipy.oauth2 import SpotifyOAuth
import pandas as pd
from spotdl import Spotdl
import librosa
import numpy as np
from pydub import AudioSegment
import os
import time
from pathlib import Path
import urllib.parse
import tempfile

class SpotifyQueueProcessor:
    def __init__(self, client_id, client_secret):
        # Initialize Spotify client with proper authentication
        redirect_uri = 'http://localhost:8888/callback'
        
        auth_manager = SpotifyOAuth(
            client_id=client_id,
            client_secret=client_secret,
            redirect_uri=redirect_uri,
            scope="user-read-playback-state user-modify-playback-state user-read-currently-playing",
            open_browser=True,
            cache_path='.spotify_cache'
        )
        
        # Get token with proper handling
        try:
            token_info = auth_manager.get_cached_token()
            if not token_info:
                print("Please log in to Spotify in your browser...")
                auth_url = auth_manager.get_authorize_url()
                print(f"\nPlease visit this URL to authorize the application: \n{auth_url}\n")
                
                code = auth_manager.get_auth_response()
                token_info = auth_manager.get_access_token(code, as_dict=False)
            elif auth_manager.is_token_expired(token_info):
                token_info = auth_manager.refresh_access_token(token_info['refresh_token'])
                
        except Exception as e:
            print(f"Authentication error: {e}")
            raise

        self.sp = spotipy.Spotify(auth_manager=auth_manager)
        
        # Initialize spotdl
        self.spot_dl = Spotdl(client_id=client_id, client_secret=client_secret)
        
        # Initialize data storage
        self.queue_data_file = "queue_data.xlsx"
        self.initialize_queue_data()
    
    def initialize_queue_data(self):
        """Initialize or load the queue data Excel file"""
        if os.path.exists(self.queue_data_file):
            self.queue_data = pd.read_excel(self.queue_data_file)
        else:
            self.queue_data = pd.DataFrame(columns=[
                'track_id', 'track_name', 'artist', 'duration_ms', 
                'chorus_start_ms', 'chorus_end_ms', 'last_processed'
            ])
            self.save_queue_data()
    
    def save_queue_data(self):
        """Save queue data to Excel file"""
        self.queue_data.to_excel(self.queue_data_file, index=False)

    def get_current_queue(self):
        """Get current user's queue from Spotify"""
        try:
            devices = self.sp.devices()
            if not devices['devices']:
                print("No active Spotify devices found. Please start Spotify on any device.")
                return []

            current = self.sp.current_playback()
            if not current:
                print("No active playback found. Please start playing something on Spotify.")
                return []
            
            queue = self.sp.queue()
            current_track = [current['item']] if current['item'] else []
            queue_tracks = current_track + queue['queue'][:2]  # Current + next 2 songs
            
            return queue_tracks

        except spotipy.exceptions.SpotifyException as e:
            print(f"Spotify API error: {e}")
            return []
        except Exception as e:
            print(f"Error getting queue: {e}")
            return []

    def detect_chorus(self, audio_path):
        """Detect chorus section in the audio file"""
        try:
            audio = AudioSegment.from_mp3(audio_path)
            samples = np.array(audio.get_array_of_samples())
            
            if audio.channels == 2:
                samples = samples.reshape((-1, 2)).mean(axis=1)
            
            samples = samples.astype(float) / np.max(np.abs(samples))
            
            onset_env = librosa.onset.onset_strength(
                y=samples,
                sr=audio.frame_rate,
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
            
            if len(peaks) > 0:
                song_length = len(audio)
                target_position = song_length * 0.3
                chorus_start = peaks[
                    np.argmin(np.abs(librosa.frames_to_time(peaks, sr=audio.frame_rate) * 1000 - target_position))
                ]
                
                chorus_start_ms = int(librosa.frames_to_time(chorus_start, sr=audio.frame_rate) * 1000)
                chorus_end_ms = min(chorus_start_ms + 60000, len(audio))
                
                return chorus_start_ms, chorus_end_ms
            else:
                song_length = len(audio)
                chorus_start_ms = int(song_length * 0.3)
                chorus_end_ms = min(chorus_start_ms + 60000, song_length)
                return chorus_start_ms, chorus_end_ms
                
        except Exception as e:
            print(f"Error detecting chorus: {e}")
            return None, None

    def process_track(self, track):
        """Process a single track to find its chorus"""
        track_id = track['id']
        
        # Check if track is already processed
        if not self.queue_data.empty and track_id in self.queue_data['track_id'].values:
            print(f"Track {track['name']} already processed, skipping...")
            return
        
        try:
            # Create temporary directory for download
            with tempfile.TemporaryDirectory() as temp_dir:
                search_query = f"{track['name']} {track['artists'][0]['name']}"
                print(f"Processing new track: {search_query}")
                
                songs = self.spot_dl.search([search_query])
                if not songs:
                    print(f"Could not find {search_query} on YouTube")
                    return
                
                song = songs[0]
                print(f"Downloading: {song.name}")
                download_path = self.spot_dl.download(song)[1]
                
                # Move downloaded file to temp directory
                temp_path = os.path.join(temp_dir, os.path.basename(download_path))
                os.rename(download_path, temp_path)
                
                # Detect chorus
                print("Detecting chorus...")
                chorus_start, chorus_end = self.detect_chorus(temp_path)
                
                if chorus_start and chorus_end:
                    # Add to queue data
                    new_row = pd.DataFrame([{
                        'track_id': track_id,
                        'track_name': track['name'],
                        'artist': track['artists'][0]['name'],
                        'duration_ms': track['duration_ms'],
                        'chorus_start_ms': chorus_start,
                        'chorus_end_ms': chorus_end,
                        'last_processed': pd.Timestamp.now()
                    }])
                    
                    self.queue_data = pd.concat([self.queue_data, new_row], ignore_index=True)
                    self.save_queue_data()
                    print(f"Successfully processed: {track['name']}")
                
                # File will be automatically deleted when leaving the temp_dir context
                
        except Exception as e:
            print(f"Error processing track {track['name']}: {e}")

    def run(self):
        """Main processing loop"""
        print("Starting queue processor...")
        print("Please ensure Spotify is running and playing music on any device.")
        
        retry_count = 0
        max_retries = 3
        
        while True:
            try:
                queue_tracks = self.get_current_queue()
                
                if queue_tracks:
                    retry_count = 0
                    for track in queue_tracks:
                        self.process_track(track)
                else:
                    retry_count += 1
                    if retry_count >= max_retries:
                        print("Multiple failures to get queue. Please check your Spotify connection.")
                        retry_count = 0
                        time.sleep(30)
                
                time.sleep(5)
                
            except KeyboardInterrupt:
                print("\nStopping processor...")
                break
            except Exception as e:
                print(f"Error in processor loop: {e}")
                time.sleep(5)

if __name__ == "__main__":
    CLIENT_ID = "1e7160661b5849e7a50f41de5b8f9ef1"
    CLIENT_SECRET = "6c04a0251cda402688b667a8a4df52ec"
    
    try:
        processor = SpotifyQueueProcessor(CLIENT_ID, CLIENT_SECRET)
        processor.run()
    except Exception as e:
        print(f"Failed to start processor: {e}")
        print("\nTroubleshooting steps:")
        print("1. Make sure you've added exactly 'http://localhost:8888/callback' to your Spotify app's redirect URIs")
        print("2. Verify your CLIENT_ID and CLIENT_SECRET are correct")
        print("3. Try clearing the .spotify_cache file if it exists")