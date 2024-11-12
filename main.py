import pandas as pd
from spotdl import Spotdl
from pydub import AudioSegment
import librosa
import numpy as np
import os

class IncrementalSongProcessor:
    def __init__(self, output_filename="ed_sheeran_mega_mix.wav"):
        self.spot = Spotdl(
            client_id="1e7160661b5849e7a50f41de5b8f9ef1",
            client_secret="6c04a0251cda402688b667a8a4df52ec"
        )
        self.output_filename = output_filename
        
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

    def add_to_mix(self, new_segment, crossfade_duration=5000):
        """
        Add a new segment to the existing mix with crossfading
        """
        try:
            # If mix doesn't exist yet, create it
            if not os.path.exists(self.output_filename):
                print(f"Creating new mix file: {self.output_filename}")
                new_segment.export(self.output_filename, format="wav")
                return True

            # Load existing mix
            current_mix = AudioSegment.from_wav(self.output_filename)
            
            print("\nAdding to existing mix:")
            print(f"  Current mix length: {len(current_mix)/1000:.2f}s")
            print(f"  New segment length: {len(new_segment)/1000:.2f}s")
            
            # Add new segment with crossfade
            final_mix = current_mix.append(new_segment, crossfade=crossfade_duration)
            
            # Normalize and add fade out
            final_mix = final_mix.normalize()
            final_mix = final_mix.fade_out(2000)
            
            # Save the updated mix
            final_mix.export(self.output_filename, format="wav")
            
            print(f"  Updated mix length: {len(final_mix)/1000:.2f}s")
            return True
            
        except Exception as e:
            print(f"Error adding to mix: {e}")
            return False

    def clean_up_files(self, *files):
        """
        Delete temporary files
        """
        for file in files:
            try:
                if os.path.exists(file):
                    os.remove(file)
                    print(f"Cleaned up: {file}")
            except Exception as e:
                print(f"Error deleting {file}: {e}")

def main():
    try:
        df = pd.read_excel('ed_sheeran_songs.xlsx')
    except Exception as e:
        print(f"Error reading Excel file: {e}")
        return

    processor = IncrementalSongProcessor()

    for _, row in df.iterrows():
        song_name = row['song_name']
        artist = row['artist']
        
        print(f"\nProcessing: {song_name} by {artist}")
        
        # Download song
        song_path, song_title = processor.download_song(song_name, artist)
        if not song_path:
            continue

        try:
            # Process the song
            audio = AudioSegment.from_mp3(song_path)
            chorus_start = processor.detect_chorus(audio)
            
            if chorus_start is not None:
                # Extract chorus
                chorus = processor.extract_chorus(audio, chorus_start)
                
                if chorus is not None:
                    # Add to mix
                    success = processor.add_to_mix(chorus)
                    
                    if success:
                        print("✓ Successfully added to mix!")
                    else:
                        print("× Failed to add to mix")
            
            # Clean up downloaded song file
            processor.clean_up_files(song_path)
            
        except Exception as e:
            print(f"Error processing {song_path}: {e}")
            # Clean up in case of error
            processor.clean_up_files(song_path)
            continue

        # Print current mix file size
        if os.path.exists(processor.output_filename):
            file_size = os.path.getsize(processor.output_filename) / (1024 * 1024)
            print(f"Current mix file size: {file_size:.2f} MB")

    print("\nProcessing complete!")

if __name__ == "__main__":
    main()