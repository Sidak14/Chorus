import spotipy
from spotipy.oauth2 import SpotifyOAuth
import pandas as pd
import time
import os
from dotenv import load_dotenv

load_dotenv()  # Load environment variables from .env

class SpotifyPlaybackController:
    def __init__(self, client_id, client_secret):
        redirect_uri = 'http://localhost:8888/callback'
        
        auth_manager = SpotifyOAuth(
            client_id=client_id,
            client_secret=client_secret,
            redirect_uri=redirect_uri,
            scope="user-read-playback-state user-modify-playback-state user-read-currently-playing",
            open_browser=True,
            cache_path='.spotify_cache_controller'
        )
        
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
        
        self.queue_data_file = "queue_data.xlsx"
        self.last_track_id = None
        self.chorus_skipped = False
        self.queue_data = None
        self.last_data_load = 0
        self.data_reload_interval = 5
    
    def load_queue_data(self, force=False):
        """Load queue data from Excel file with caching"""
        current_time = time.time()
        if (force or 
            self.queue_data is None or 
            current_time - self.last_data_load >= self.data_reload_interval):
            
            if os.path.exists(self.queue_data_file):
                self.queue_data = pd.read_excel(self.queue_data_file)
                self.last_data_load = current_time
                return True
            else:
                self.queue_data = pd.DataFrame()
                return False
    
    def get_track_chorus_times(self, track_id):
        """Get chorus start/end times for a track"""
        self.load_queue_data()
        if not self.queue_data.empty:
            track_data = self.queue_data[self.queue_data['track_id'] == track_id]
            if not track_data.empty:
                return (
                    track_data.iloc[0]['chorus_start_ms'],
                    track_data.iloc[0]['chorus_end_ms']
                )
        return None, None
    
    def get_playback_mode(self):
        """Determine playback mode and clean up extra queue entries"""
        try:
            queue = self.sp.queue()
            current = self.sp.current_playback()
            if not current or not queue:
                return 'chorus-only'
            
            current_track_id = current['item']['id']
            current_track_name = current['item']['name']
            
            # Count consecutive occurrences
            consecutive_count = 1
            duplicates_to_remove = 0
            for track in queue['queue']:
                if track['id'] == current_track_id:
                    consecutive_count += 1
                    duplicates_to_remove += 1
                else:
                    break
            
            print(f"\nFound {consecutive_count} consecutive occurrences of '{current_track_name}'")
            
            # Clean up extra queue entries
            if duplicates_to_remove > 0:
                print(f"Removing {duplicates_to_remove} duplicate entries from queue...")
                # Pause playback
                self.sp.pause_playback()
                time.sleep(0.1)  # Small delay to ensure pause takes effect
                
                # Skip the duplicates
                for _ in range(duplicates_to_remove):
                    self.sp.next_track()
                    time.sleep(0.1)
                
                # Don't resume here - let the main playback handler handle it
            
            # Determine playback mode
            if consecutive_count == 1:
                return 'start-to-chorus'
            elif consecutive_count == 2:
                return 'chorus-only'
            elif consecutive_count >= 3:
                return 'full-song'
            
            return 'chorus-only'
            
        except Exception as e:
            print(f"Error determining playback mode: {e}")
            return 'chorus-only'

    def handle_playback(self):
        try:
            current = self.sp.current_playback()
            if not current or not current['is_playing']:
                return
            
            current_track_id = current['item']['id']
            progress_ms = current['progress_ms']
            duration_ms = current['item']['duration_ms']
            
            if current_track_id != self.last_track_id:
                # New track started
                playback_mode = self.get_playback_mode()
                print(f"\nNew track detected: {current['item']['name']}")
                print(f"Playback mode: {playback_mode}")
                
                self.last_track_id = current_track_id
                self.chorus_skipped = False
                self.current_mode = playback_mode
                self.load_queue_data(force=True)
                
                # Immediately skip to chorus if in chorus-only mode
                if self.current_mode == 'chorus-only':
                    chorus_start_ms, chorus_end_ms = self.get_track_chorus_times(current_track_id)
                    if chorus_start_ms is not None:
                        chorus_start_ms = int(chorus_start_ms)
                        self.sp.seek_track(position_ms=chorus_start_ms)
                        time.sleep(0.1)  # Tiny delay to ensure track has started
                        self.chorus_skipped = True

                self.sp.start_playback()
            
            chorus_start_ms, chorus_end_ms = self.get_track_chorus_times(current_track_id)
            
            if chorus_start_ms is not None and chorus_end_ms is not None:
                chorus_start_ms = int(chorus_start_ms)
                chorus_end_ms = int(chorus_end_ms)
                
                if self.current_mode == 'full-song':
                    if progress_ms >= duration_ms - 2000:
                        print("Song finished, skipping to next track")
                        self.sp.next_track()
                        self.last_track_id = None
                        
                elif self.current_mode == 'start-to-chorus':
                    if progress_ms >= chorus_end_ms:
                        print("Reached chorus end, skipping to next track")
                        self.sp.next_track()
                        self.last_track_id = None
                        
                else:  # chorus-only mode
                    if not self.chorus_skipped:  # This is now a backup in case the immediate skip failed
                        print(f"Skipping to chorus at {chorus_start_ms/1000:.1f}s")
                        self.sp.seek_track(position_ms=chorus_start_ms)
                        self.chorus_skipped = True
                    elif progress_ms >= chorus_end_ms:
                        print("Chorus finished, skipping to next track")
                        self.sp.next_track()
                        self.last_track_id = None
                
                time.sleep(1)  # Small delay between checks
                
        except spotipy.exceptions.SpotifyException as e:
            print(f"Spotify API error: {e}")
            time.sleep(5)
        except Exception as e:
            print(f"Error handling playback: {e}")
            time.sleep(1)
    
    def run(self):
        """Main playback control loop"""
        print("Starting playback controller...")
        print("Please ensure Spotify is running and playing music on any device.")
        
        retry_count = 0
        max_retries = 3
        
        while True:
            try:
                self.handle_playback()
                time.sleep(1)
                
            except KeyboardInterrupt:
                print("\nStopping controller...")
                break
            except spotipy.exceptions.SpotifyException as e:
                print(f"Spotify API error: {e}")
                retry_count += 1
                if retry_count >= max_retries:
                    print("Multiple Spotify API failures. Waiting 30 seconds before retrying...")
                    time.sleep(30)
                    retry_count = 0
                else:
                    time.sleep(5)
            except Exception as e:
                print(f"Error in controller loop: {e}")
                time.sleep(5)

if __name__ == "__main__":
    CLIENT_ID = os.getenv('CLIENT_ID')
    CLIENT_SECRET = os.getenv('CLIENT_SECRET')
    
    try:
        controller = SpotifyPlaybackController(CLIENT_ID, CLIENT_SECRET)
        controller.run()
    except Exception as e:
        print(f"Failed to start controller: {e}")
        print("\nTroubleshooting steps:")
        print("1. Make sure you've added exactly 'http://localhost:8888/callback' (no URL encoding) to your Spotify app's redirect URIs")
        print("2. Verify your CLIENT_ID and CLIENT_SECRET are correct")
        print("3. Try clearing the .spotify_cache_controller file if it exists")
        print("4. Check if you can access the Spotify Developer Dashboard")